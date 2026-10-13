"""
SRM Student Portal Direct Scraper (sp.srmist.edu.in/srmiststudentportal)
========================================================================
Implements Ratio-D's direct Student Portal client + TinyOCR CRNN CAPTCHA auto-solver:
- Solves the 175x45 Student Portal CAPTCHA in ~40ms using Ratio-D's trained TinyCRNN weights
  in pure NumPy (zero PyTorch/ONNX dependency).
- Fetches live Attendance, Component-wise Internal Marks, Timetable, Courses, and Profile
  in parallel directly from sp.srmist.edu.in.
"""

import base64
import concurrent.futures
import io
import json
import math
import os
import random
import re
import time
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image

from academia_direct_scraper import calculate_bunk_margin_and_needed, get_course_credit, SRM_PERIOD_TIMES

LOGIN_URL = "https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp"
BASE_URL = "https://sp.srmist.edu.in/srmiststudentportal"
HRD_URL = BASE_URL + "/students/template/HRDSystem.jsp"
ATT_URL = BASE_URL + "/students/report/studentAttendanceDetails.jsp"
MARKS_URL = BASE_URL + "/students/report/studentInternalMarkDetails.jsp"
INNER_MARKS_URL = BASE_URL + "/students/report/studentInternalMarkDetailsInner.jsp"
TIMETABLE_URL = BASE_URL + "/students/report/studentTimeTableDetails.jsp"
PROFILE_URL = BASE_URL + "/students/report/studentPersonalDetails.jsp"
LOGIN_SERVLET = BASE_URL + "/LoginServlet"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": LOGIN_URL,
    "Origin": "https://sp.srmist.edu.in",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

VOCAB = "0123456789abcdefghijklmnopqrstuvwxyz"
_WEIGHTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha_crnn.npz")
_CRNN_WEIGHTS = None


def _get_crnn_weights():
    global _CRNN_WEIGHTS
    if _CRNN_WEIGHTS is None and os.path.exists(_WEIGHTS_PATH):
        raw = np.load(_WEIGHTS_PATH)
        folded = {}
        for idx in range(5):
            w = raw[f"cnn.{idx}.0.weight"]
            bn_w = raw[f"cnn.{idx}.1.weight"]
            bn_b = raw[f"cnn.{idx}.1.bias"]
            bn_mean = raw[f"cnn.{idx}.1.running_mean"]
            bn_var = raw[f"cnn.{idx}.1.running_var"]
            scale = bn_w / np.sqrt(bn_var + 1e-5)
            folded[f"conv_w_{idx}"] = (w * scale[:, None, None, None]).astype(np.float32)
            folded[f"conv_b_{idx}"] = (bn_b - bn_mean * scale).astype(np.float32)
        for k in [
            "lstm.weight_ih_l0", "lstm.weight_hh_l0", "lstm.bias_ih_l0", "lstm.bias_hh_l0",
            "lstm.weight_ih_l0_reverse", "lstm.weight_hh_l0_reverse", "lstm.bias_ih_l0_reverse", "lstm.bias_hh_l0_reverse",
            "classifier.weight", "classifier.bias"
        ]:
            folded[k] = raw[k].astype(np.float32)
        _CRNN_WEIGHTS = folded
    return _CRNN_WEIGHTS


def _conv3x3_relu(x: np.ndarray, w_folded: np.ndarray, b_folded: np.ndarray, stride: int = 1) -> np.ndarray:
    B, Cin, H, W = x.shape
    Cout = w_folded.shape[0]
    x_pad = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)), mode="constant")
    H_out = (H + 2 - 3) // stride + 1
    W_out = (W + 2 - 3) // stride + 1
    out = np.broadcast_to(b_folded[None, :, None, None], (B, Cout, H_out, W_out)).copy()
    for kh in range(3):
        for kw in range(3):
            patch = x_pad[:, :, kh:kh + H_out * stride:stride, kw:kw + W_out * stride:stride]
            out += np.einsum("bchw,oc->bohw", patch, w_folded[:, :, kh, kw], optimize=True)
    return np.maximum(out, 0.0)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50.0, 50.0)))


def _run_lstm_dir(x: np.ndarray, w_ih: np.ndarray, w_hh: np.ndarray, b_ih: np.ndarray, b_hh: np.ndarray, reverse: bool = False) -> np.ndarray:
    B, T, _ = x.shape
    H = 128
    h = np.zeros((B, H), dtype=np.float32)
    c = np.zeros((B, H), dtype=np.float32)
    bias = b_ih + b_hh
    x_proj = x @ w_ih.T + bias
    out = np.zeros((B, T, H), dtype=np.float32)
    steps = range(T - 1, -1, -1) if reverse else range(T)
    for t in steps:
        gates = x_proj[:, t, :] + h @ w_hh.T
        i = _sigmoid(gates[:, 0:H])
        f = _sigmoid(gates[:, H:2 * H])
        g = np.tanh(gates[:, 2 * H:3 * H])
        o = _sigmoid(gates[:, 3 * H:4 * H])
        c = f * c + i * g
        h = o * np.tanh(c)
        out[:, t, :] = h
    return out


def solve_captcha_bytes(image_bytes: bytes) -> Optional[str]:
    """Solves SRM Student Portal CAPTCHA image bytes using Ratio-D TinyCRNN."""
    try:
        w = _get_crnn_weights()
        if not w:
            return None
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        if img.size != (175, 45):
            img = img.resize((175, 45), Image.Resampling.BILINEAR)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        arr = (arr - 0.5) / 0.5
        x = arr[None, None, :, :]

        strides = [1, 2, 1, 2, 1]
        for idx, s in enumerate(strides):
            x = _conv3x3_relu(x, w[f"conv_w_{idx}"], w[f"conv_b_{idx}"], stride=s)

        x = x.mean(axis=2).transpose(0, 2, 1)
        fwd = _run_lstm_dir(x, w["lstm.weight_ih_l0"], w["lstm.weight_hh_l0"], w["lstm.bias_ih_l0"], w["lstm.bias_hh_l0"], reverse=False)
        rev = _run_lstm_dir(x, w["lstm.weight_ih_l0_reverse"], w["lstm.weight_hh_l0_reverse"], w["lstm.bias_ih_l0_reverse"], w["lstm.bias_hh_l0_reverse"], reverse=True)
        lstm_out = np.concatenate([fwd, rev], axis=-1)
        logits = lstm_out @ w["classifier.weight"].T + w["classifier.bias"]

        seq = logits.argmax(axis=2)[0]
        collapsed = []
        prev = 0
        for idx in seq:
            idx_int = int(idx)
            if idx_int != prev:
                collapsed.append(idx_int)
            prev = idx_int
        text = "".join(VOCAB[i - 1] for i in collapsed if i != 0)
        return text if text else None
    except Exception as e:
        print(f"[PORTAL-OCR] Error solving captcha: {e}")
        return None


def _telemetry_payload() -> Dict[str, Any]:
    now = int(time.time() * 1000)
    start = now - random.randint(3000, 8000)
    return {
        "startTime": start,
        "currentDomain": "sp.srmist.edu.in",
        "timezoneOffset": -330,
        "screenWidth": 1366,
        "screenHeight": 768,
        "colorDepth": 24,
        "devicePixelRatio": 1,
        "platform": "Win32",
        "userAgent": HEADERS["User-Agent"],
        "language": "en-US",
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
        "touchSupport": False,
        "webdriver": False,
        "mouseClicks": random.randint(2, 6),
        "mouseMovements": random.randint(5, 20),
        "keystrokeCount": 0,
        "typingSpeedMs": 0,
        "canvasHash": format(random.randint(0, 0x7FFFFFFF), "06x"),
        "submitTime": now,
        "timeOnPageMs": now - start,
    }


class SRMPortalSession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        proxy = os.environ.get("PORTAL_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})
        self.nonce = None
        self.login_form_fields = {}
        self.domain_field_name = "dtoken_x"
        self.captcha_field_name = "cptoken_x"
        self.random_delimiter = "0000"
        self.captcha_bytes = None
        self.load_ms = None

    def load_captcha(self) -> bool:
        r = self.session.get(LOGIN_URL, timeout=10)
        text = r.text
        m = re.search(r"window\.SECURE_CONFIG\s*=\s*\{[^}]*?nonce\s*:\s*'([^']+)'", text)
        if not m:
            m = re.search(r"window\.SECURE_CONFIG\.nonce\s*=\s*'([^']+)'", text)
        if not m:
            m = re.search(r'id="fpNonce"\s*value="([^"]+)"', text)
        self.nonce = m.group(1) if m else ""

        df = re.search(r'domainFieldName\s*=\s*[\'"]([^\'"]+)[\'"]', text)
        cf = re.search(r'captchaFieldName\s*=\s*[\'"]([^\'"]+)[\'"]', text)
        self.domain_field_name = df.group(1) if df else "dtoken_x"
        self.captcha_field_name = cf.group(1) if cf else "cptoken_x"

        m_delim = re.search(r"randomDelimiter\s*=\s*'([^']+)'", text)
        self.random_delimiter = m_delim.group(1) if m_delim else "0000"

        fields = {}
        for inp in re.finditer(r"<input[^>]*name=['\"]([^'\"]+)['\"][^>]*>", text):
            fields[inp.group(1)] = ""
        self.login_form_fields = fields

        m_cap = re.search(r"SCaptchaServlet[^'\" ]*", text)
        if not m_cap:
            return False
        seg = m_cap.group(0)
        captcha_url = BASE_URL + "/" + seg if not seg.startswith("/") else "https://sp.srmist.edu.in" + seg
        proof = base64.b64encode(f"{self.nonce}:sp.srmist.edu.in".encode()).decode()
        cr = self.session.get(
            captcha_url,
            headers={
                "X-Domain-Proof": proof,
                "Accept": "image/png, image/jpeg, image/svg+xml, image/*",
                "Referer": LOGIN_URL,
            },
            timeout=10,
        )
        if cr.status_code == 200 and cr.content:
            self.captcha_bytes = cr.content
            self.load_ms = int(time.time() * 1000)
            return True
        return False

    def login_attempt(self, netid: str, password: str, captcha_code: str) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        calc_elapsed = max(0, int((now_ms - (self.load_ms or now_ms)) / 1000))
        elapsed_sec = max(random.randint(3, 5), calc_elapsed)
        dtoken = base64.b64encode("sp.srmist.edu.in"[::-1].encode()).decode()
        trap_payload = str(elapsed_sec) + (self.random_delimiter or "0000") + "3"
        cptoken = base64.b64encode(trap_payload.encode()).decode()
        fp_payload = base64.b64encode(json.dumps({"fp": "", "nonce": self.nonce, "ts": now_ms}).encode()).decode()
        payload = base64.b64encode(json.dumps(_telemetry_payload()).encode()).decode()

        fp_body = dict(self.login_form_fields)
        fp_body.update({
            "username": netid,
            "password": password,
            "captcha": captcha_code,
            "fpPayload": fp_payload,
            "fpToken": "",
            "recaptchaToken": "",
            "telemetryPayload": payload,
        })
        fp_body[self.domain_field_name] = dtoken
        fp_body[self.captcha_field_name] = cptoken

        resp = self.session.post(LOGIN_SERVLET, data=fp_body, timeout=12)
        body = resp.text or ""
        self.last_status = resp.status_code
        self.last_url = str(resp.url)
        self.last_body = body
        url_lower = str(resp.url).lower()

        if "logout.jsp" in url_lower or "attendance" in url_lower or "hrdsystem" in url_lower:
            att_html = self.get_attendance_html()
            if att_html:
                return {"ok": True, "att_html": att_html}
        else:
            att_html = self.get_attendance_html()
            if att_html:
                return {"ok": True, "att_html": att_html}

        return self._classify_failure(body)

    @staticmethod
    def _classify_failure(body: str) -> Dict[str, Any]:
        soup = BeautifulSoup(body, "html.parser")
        alert_el = soup.find(class_=lambda c: c and ("alert" in c or "error" in c))
        if alert_el:
            alert_text = alert_el.get_text(separator=" ", strip=True)
            if alert_text.lower().startswith("alert"):
                alert_text = alert_text[5:].strip()
            blob = alert_text.lower()
            if any(k in blob for k in ["captcha", "code", "verification", "security"]):
                return {"ok": False, "reason": "wrong_captcha", "message": alert_text}
            if "locked" in blob:
                return {"ok": False, "reason": "account_locked", "message": alert_text}
            if any(k in blob for k in ["invalid", "attempts remaining", "unsuccessful", "user id or password", "password", "credential"]):
                return {"ok": False, "reason": "invalid_credentials", "message": alert_text}
            return {"ok": False, "reason": "login_failed", "message": alert_text}
        return {"ok": False, "reason": "login_failed", "message": "Student Portal login failed"}

    def get_attendance_html(self) -> Optional[str]:
        try:
            r = self.session.get(ATT_URL, timeout=10)
            url_l = str(r.url).lower()
            txt_l = r.text.lower()
            if (
                r.status_code != 200
                or "youlogin" in url_l
                or "login" in url_l
                or "loginform" in txt_l
                or "login_form" in txt_l
                or "thegr8loginloader" in txt_l
            ):
                return None
            return r.text
        except Exception:
            return None

    def get_marks_html(self) -> Optional[str]:
        try:
            r = self.session.get(MARKS_URL, timeout=10)
            if r.status_code == 200 and "table" in r.text.lower():
                return r.text
        except Exception:
            pass
        return None

    def get_inner_marks_html(self, subject_id: str, status: str = "2") -> Optional[str]:
        try:
            payload = {"iden": "1", "hdnSubjectId": subject_id, "status": status}
            r = self.session.post(INNER_MARKS_URL, data=payload, timeout=8)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        return None

    def get_timetable_html(self) -> Optional[str]:
        try:
            payload = {
                "iden": "10",
                "filter": "",
                "hdnFormDetails": "1",
                "csrfPreventionSalt": "",
            }
            r = self.session.post(TIMETABLE_URL, data=payload, timeout=10)
            if r.status_code == 200 and "table" in r.text.lower() and "day 1" in r.text.lower():
                return r.text
        except Exception:
            pass
        return None

    def get_profile_html(self) -> Optional[str]:
        try:
            r = self.session.get(PROFILE_URL, timeout=10)
            if r.status_code == 200 and "student name" in r.text.lower():
                return r.text
        except Exception:
            pass
        return None


def _parse_portal_profile(html_content: Optional[str], netid: str) -> Dict[str, Any]:
    profile = {
        "name": "",
        "reg_no": netid.upper(),
        "program": "",
        "department": "",
        "section": "",
        "semester": "",
        "batch": "1",
        "mobile": "",
        "email": f"{netid.lower()}@srmist.edu.in",
    }
    if not html_content:
        return profile
    soup = BeautifulSoup(html_content, "html.parser")
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) >= 2:
            label = re.sub(r"\s+", " ", tds[0].get_text(strip=True)).lower()
            val = re.sub(r"\s+", " ", tds[1].get_text(strip=True))
            if not val or val.upper() in ("N/A", "--", "-"):
                continue
            if "student name" in label:
                profile["name"] = val
            elif "register no" in label or "registration" in label:
                profile["reg_no"] = val
            elif "institution" in label or "department" in label:
                profile["department"] = val
            elif "program" in label:
                profile["program"] = val
            elif "batch" in label:
                profile["batch"] = val
            elif "semester" in label:
                profile["semester"] = val
            elif "section" in label:
                profile["section"] = val
            elif "mobile" in label:
                profile["mobile"] = val
    return profile


def _parse_portal_timetable_and_courses(html_content: Optional[str]) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    final_tt = {"1": [], "2": [], "3": [], "4": [], "5": []}
    courses_list = []
    if not html_content:
        return final_tt, courses_list

    soup = BeautifulSoup(html_content, "html.parser")
    courses_map = {}

    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
        if any("course code" in h for h in headers) and any("faculty" in h for h in headers):
            for row in table.find_all("tr"):
                cols = [td.get_text(" ", strip=True) for td in row.find_all("td")]
                if len(cols) >= 5:
                    c_code = cols[0].strip()
                    c_name = cols[1].strip()
                    c_credits_str = cols[2].strip()
                    c_slot = cols[3].strip()
                    c_faculty = cols[4].strip()
                    building = cols[5].strip() if len(cols) > 5 else ""
                    raw_room = cols[7].strip() if len(cols) > 7 else ""

                    try:
                        c_credit = float(c_credits_str)
                        if c_credit.is_integer():
                            c_credit = int(c_credit)
                    except Exception:
                        c_credit = get_course_credit(c_code, c_name)

                    clean_room = re.split(r"[,/]|(?:\s+(?:Drafting|Lab|Room|Hall))", raw_room, flags=re.I)[0].strip() if raw_room else ""
                    m_abbr = re.search(r"\(([^)]+)\)", building)
                    b_abbr = m_abbr.group(1).strip().upper() if m_abbr else ""
                    if clean_room and b_abbr and not clean_room.upper().startswith(b_abbr):
                        full_room = f"{b_abbr} {clean_room}"
                    else:
                        full_room = clean_room or b_abbr or "TBA"

                    slots = [s.strip().upper() for s in c_slot.split(",") if s.strip()]
                    is_lab = bool(re.search(r"\b(lab|practical)\b", c_name, flags=re.I)) or any(s.startswith("P") for s in slots)
                    ctype = "Practical" if is_lab else "Theory"

                    c_info = {
                        "code": c_code,
                        "title": c_name,
                        "credit": c_credit,
                        "category": ctype,
                        "type": ctype,
                        "faculty": c_faculty or "TBA",
                        "slot": c_slot,
                        "room": full_room,
                    }
                    courses_list.append(c_info)
                    if c_code not in courses_map:
                        courses_map[c_code] = c_info

    # Find day order grid table
    for table in soup.find_all("table"):
        day_rows = {}
        for row in table.find_all("tr"):
            cols = [td.get_text(" ", strip=True) for td in row.find_all("td")]
            if not cols:
                continue
            m_day = re.search(r"^Day\s*([1-5])$", cols[0].strip(), re.I)
            if m_day:
                day_rows[m_day.group(1)] = cols[1:]

        if not day_rows:
            continue

        # Check if this grid contains course codes
        sample_vals = [v.strip() for r in day_rows.values() for v in r if v.strip() and v.strip() not in ("-", "--")]
        if not any(v in courses_map for v in sample_vals):
            continue

        for day_num, cell_codes in day_rows.items():
            for idx, raw_code in enumerate(cell_codes):
                if idx >= len(SRM_PERIOD_TIMES):
                    break
                code = raw_code.strip()
                if not code or code in ("-", "--"):
                    continue
                pt = SRM_PERIOD_TIMES[idx]
                c_info = courses_map.get(code, {
                    "code": code,
                    "title": code,
                    "type": "Theory",
                    "room": "TBA",
                    "faculty": "TBA",
                    "slot": "",
                })
                entry = {
                    "time": f"{pt['start']} - {pt['end']}",
                    "time_from": pt["start"],
                    "time_to": pt["end"],
                    "subject": c_info["title"],
                    "code": code,
                    "room": c_info.get("room", "TBA"),
                    "faculty": c_info.get("faculty", "TBA"),
                    "type": c_info.get("type", "Theory"),
                    "slot": c_info.get("slot", ""),
                    "period": pt["period"],
                    "period_end": pt["period"],
                }
                last = final_tt[day_num][-1] if final_tt[day_num] else None
                if (
                    last
                    and last["code"] == entry["code"]
                    and last["period_end"] + 1 == pt["period"]
                ):
                    last["time"] = f"{last['time_from']} - {pt['end']}"
                    last["time_to"] = pt["end"]
                    last["period_end"] = pt["period"]
                else:
                    final_tt[day_num].append(entry)
        break

    return final_tt, courses_list


def _parse_portal_attendance(html_content: Optional[str], courses_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    att_list = []
    if not html_content:
        return att_list

    soup = BeautifulSoup(html_content, "html.parser")
    course_lookup = {c["code"]: c for c in courses_list if c.get("code")}

    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 6:
            continue
        code = cells[0].strip()
        if not re.match(r"^[A-Z0-9]{6,12}$", code):
            continue
        try:
            conducted = int(cells[2])
            present = int(cells[3])
            absent = int(cells[4])
            percent = float(cells[5])
        except ValueError:
            continue

        title = cells[1].strip()
        c_meta = course_lookup.get(code, {})
        credit = get_course_credit(code, title, courses_list)
        safe_margin, classes_needed, status_badge = calculate_bunk_margin_and_needed(percent, conducted, absent)

        att_list.append({
            "courseTitle": title,
            "courseCode": code,
            "category": c_meta.get("category", "THEORY"),
            "faculty": c_meta.get("faculty", ""),
            "slot": c_meta.get("slot", ""),
            "room": c_meta.get("room", ""),
            "conducted": conducted,
            "absent": absent,
            "present": present,
            "attended": percent,
            "credit": credit,
            "bunk_margin": safe_margin,
            "classes_needed": classes_needed,
            "status_badge": status_badge,
            "classes_per_cycle": 1,
        })
    return att_list


def _parse_portal_marks(portal: SRMPortalSession, marks_html: Optional[str], courses_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    marks_list = []
    if not marks_html:
        return marks_list

    soup = BeautifulSoup(marks_html, "html.parser")
    raw_subjects = []

    for row in soup.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        code = cols[0].get_text(strip=True)
        if not re.match(r"^[A-Z0-9]{6,12}$", code):
            continue
        title = cols[1].get_text(" ", strip=True)
        score_str = cols[2].get_text(strip=True)

        got_val, max_val = None, None
        if "/" in score_str:
            parts = score_str.split("/", 1)
            try:
                got_val = float(parts[0].strip())
                max_val = float(parts[1].strip())
            except ValueError:
                pass

        subject_id = None
        status = "2"
        btn = row.find(["button", "a"], onclick=True)
        if btn:
            onclick_text = btn.get("onclick", "")
            m = re.search(
                r"funViewComponentWiseMarks\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*([0-9]+)\s*\)",
                onclick_text,
            )
            if m:
                subject_id = m.group(1)
                status = m.group(4)

        raw_subjects.append({
            "code": code,
            "title": title,
            "got_val": got_val,
            "max_val": max_val,
            "subject_id": subject_id,
            "status": status,
        })

    def fetch_inner(subj):
        sid = subj.get("subject_id")
        if not sid:
            return []
        inner_html = portal.get_inner_marks_html(sid, subj.get("status", "2"))
        if not inner_html:
            return []
        inner_soup = BeautifulSoup(inner_html, "html.parser")
        tests = []
        for tr in inner_soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 3:
                comp_name = tds[1].get_text(" ", strip=True)
                mark_str = tds[2].get_text(strip=True)
                if "/" in mark_str:
                    p = mark_str.split("/", 1)
                    try:
                        g_v = float(p[0].strip())
                        m_v = float(p[1].strip())
                        tests.append({
                            "test_name": comp_name,
                            "max": m_v,
                            "obtained": g_v,
                        })
                    except ValueError:
                        pass
        return tests

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_inner, s): s for s in raw_subjects}
        for fut in concurrent.futures.as_completed(futures):
            s = futures[fut]
            try:
                s["tests"] = fut.result()
            except Exception:
                s["tests"] = []

    for s in raw_subjects:
        code = s["code"]
        title = s["title"]
        tests = s.get("tests") or []
        if not tests and s["got_val"] is not None and s["max_val"] is not None and s["max_val"] > 0:
            tests = [{
                "test_name": "Internal",
                "max": s["max_val"],
                "obtained": s["got_val"],
            }]

        perf_strings = [f"{t['test_name']}/{t['max']:.2f} | {t['obtained']:.2f}" for t in tests]
        perf_formatted = "   ".join(perf_strings) if perf_strings else "No tests available."
        credit = get_course_credit(code, title, courses_list)

        marks_list.append({
            "courseTitle": title,
            "courseCode": code,
            "courseType": "Theory",
            "performance": perf_formatted,
            "Test Performance": perf_formatted,
            "tests": tests,
            "credit": credit,
        })

    return marks_list


def fetch_portal_data(username: str, password: str) -> Dict[str, Any]:
    """
    Logs into sp.srmist.edu.in using Ratio-D's TinyOCR CAPTCHA solver and fetches
    Attendance, Component-wise Internal Marks, Timetable, Courses, and Profile.
    """
    start_ts = time.time()
    netid = (username or "").strip().split("@")[0].strip()
    password = (password or "").strip()
    if not netid or not password:
        return {"success": False, "error": "Missing Student Portal credentials"}

    import re
    if re.match(r'^\d{2}[-/.]\d{2}[-/.]\d{4}$', password):
        password = re.sub(r'[-/.]', '', password)

    att_html = None
    active_portal = None

    for attempt in range(1, 5):
        portal = SRMPortalSession()
        try:
            if not portal.load_captcha() or not portal.captcha_bytes:
                continue
            solved = solve_captcha_bytes(portal.captcha_bytes)
            if not solved:
                continue
            print(f"[{netid}] [PORTAL-OCR] Attempt {attempt}/4 predicted captcha: '{solved}'")
            res = portal.login_attempt(netid, password, solved)
            if res.get("ok"):
                att_html = res.get("att_html")
                active_portal = portal
                print(f"[{netid}] [PORTAL] Login succeeded on attempt {attempt} in {time.time() - start_ts:.2f}s!")
                break
            reason = res.get("reason", "")
            if reason in ("invalid_credentials", "account_locked"):
                msg = res.get("message", "Invalid Student Portal credentials")
                print(f"[{netid}] [PORTAL] Auth stopped ({reason}): {msg}")
                return {"success": False, "error": msg, "reason": reason}
        except Exception as e:
            print(f"[{netid}] [PORTAL] Attempt {attempt} error: {e}")
            break

    if not active_portal or not att_html:
        return {"success": False, "error": "Could not authenticate with SRM Student Portal"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        f_marks = ex.submit(active_portal.get_marks_html)
        f_tt = ex.submit(active_portal.get_timetable_html)
        f_prof = ex.submit(active_portal.get_profile_html)

        marks_html = f_marks.result()
        tt_html = f_tt.result()
        prof_html = f_prof.result()

    timetable, courses_list = _parse_portal_timetable_and_courses(tt_html)
    att_list = _parse_portal_attendance(att_html, courses_list)
    marks_list = _parse_portal_marks(active_portal, marks_html, courses_list)
    profile = _parse_portal_profile(prof_html, netid)

    print(
        f"[{netid}] [PORTAL] Completed in {time.time() - start_ts:.2f}s "
        f"(Att: {len(att_list)}, Marks: {len(marks_list)}, Courses: {len(courses_list)})"
    )
    return {
        "success": True,
        "data": att_list,
        "marks": marks_list,
        "timetable": timetable,
        "courses": courses_list,
        "profile": profile,
        "is_mock_attendance": False,
        "source": "srm_portal",
    }
