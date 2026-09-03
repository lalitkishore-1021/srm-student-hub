import time
import requests
import urllib3
import re
import json
import base64
import threading
from bs4 import BeautifulSoup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://sp.srmist.edu.in/srmiststudentportal"
LOGIN_PAGE = BASE_URL + "/students/loginManager/youLogin.jsp"
LOGIN_SERVLET = BASE_URL + "/LoginServlet"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def _extract(html, key):
    for pattern in [
        key + r"\s*=\s*'([^']+)'",
        key + r'\s*=\s*"([^"]+)"',
        key + r"\s*:\s*'([^']+)'",
        key + r'\s*:\s*"([^"]+)"',
    ]:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    return None

ACTIVE_SESSIONS = {}

def keep_alive_task(jsessionid, session, stop_event):
    while not stop_event.is_set():
        try:
            session.get("https://sp.srmist.edu.in/srmiststudentportal/resources/Image/srmist.jpg", timeout=3)
        except Exception:
            pass
        for _ in range(6):
            if stop_event.is_set():
                break
            time.sleep(0.5)

def get_sp_captcha():
    """
    Fetches the captcha from the new student portal and returns it as base64,
    along with hidden fields and tokens needed for the login POST.
    """
    try:
        # Cleanup old sessions
        now = time.time()
        for k in list(ACTIVE_SESSIONS.keys()):
            if now - ACTIVE_SESSIONS[k]['time'] > 300:
                if 'stop_event' in ACTIVE_SESSIONS[k]:
                    ACTIVE_SESSIONS[k]['stop_event'].set()
                del ACTIVE_SESSIONS[k]
                
        session = requests.Session()
        session.verify = False
        session.headers.update(HEADERS)
        
        r_page = session.get(LOGIN_PAGE, timeout=10)
        jsessionid = session.cookies.get("JSESSIONID", "")
        
        stop_event = threading.Event()
        t = threading.Thread(target=keep_alive_task, args=(jsessionid, session, stop_event), daemon=True)
        t.start()
        
        ACTIVE_SESSIONS[jsessionid] = {'session': session, 'time': now, 'stop_event': stop_event}
        
        config = {}
        for key in ["captchaFieldName", "domainFieldName", "randomDelimiter", "nonce"]:
            config[key] = _extract(r_page.text, key)
            
        soup = BeautifulSoup(r_page.text, "html.parser")
        cap_img = soup.find(id="secure_captcha")
        cap_url = "https://sp.srmist.edu.in" + cap_img.get("data-src") if cap_img else ""
        
        ph_input = soup.find("input", id=re.compile(r"^ph_"))
        ph_name = ph_input.get("name") if ph_input else ""
        
        cap_headers = session.headers.copy()
        if config.get("nonce"):
            cap_headers['X-Domain-Proof'] = base64.b64encode(f"{config['nonce']}:sp.srmist.edu.in".encode()).decode()
        cap_headers['Accept'] = 'image/png, image/jpeg, image/svg+xml, image/*'
        cap_headers['Referer'] = LOGIN_PAGE
        
        r_cap = session.get(cap_url, headers=cap_headers, timeout=10)
        b64_img = base64.b64encode(r_cap.content).decode("utf-8")
        
        # Clean up old sessions
        now = time.time()
        for k in list(ACTIVE_SESSIONS.keys()):
            if now - ACTIVE_SESSIONS[k]['time'] > 300:
                del ACTIVE_SESSIONS[k]
                
        ACTIVE_SESSIONS[jsessionid] = {'session': session, 'time': now}
        
        return {
            "success": True,
            "captcha_b64": b64_img,
            "jsessionid": jsessionid,
            "captcha_field": config.get("captchaFieldName", ""),
            "domain_field": config.get("domainFieldName", ""),
            "delimiter": config.get("randomDelimiter", ""),
            "ph_name": ph_name
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def sync_sp_portal(net_id, password, captcha_text, jsessionid,
                   captcha_field="", domain_field="", delimiter="", ph_name=""):
    result_data = {"attendance": [], "marks": [], "success": False, "error": None}
    try:
        session_data = ACTIVE_SESSIONS.get(jsessionid)
        if session_data:
            session = session_data['session']
            if 'stop_event' in session_data:
                session_data['stop_event'].set()
                # Wait for the background thread to release the socket back to the urllib3 pool
                time.sleep(0.6)
            del ACTIVE_SESSIONS[jsessionid]
        else:
            session = requests.Session()
            session.verify = False
            session.headers.update(HEADERS)

        time_elapsed_sec = 18
        interact_count = 12
        trap_payload = f"{time_elapsed_sec}{delimiter}{interact_count}"
        
        cptoken_val = base64.b64encode(trap_payload.encode("utf-8")).decode("utf-8")
        dtoken_val = base64.b64encode("ni.ude.tsimrs.ps".encode("utf-8")).decode("utf-8")
        
        fp = {
            "startTime": int(time.time()*1000) - 18000,
            "currentDomain": "sp.srmist.edu.in",
            "timezoneOffset": 0,
            "screenWidth": 1920,
            "screenHeight": 1080,
            "colorDepth": 24,
            "devicePixelRatio": 1,
            "platform": "Linux x86_64",
            "userAgent": HEADERS["User-Agent"],
            "language": "en-US",
            "hardwareConcurrency": 16,
            "deviceMemory": 16,
            "touchSupport": False,
            "webdriver": False,
            "mouseClicks": 2,
            "mouseMovements": 6,
            "keystrokeCount": 4,
            "typingSpeedMs": 14500,
            "canvasHash": "8a32b9c7",
            "submitTime": int(time.time()*1000),
            "timeOnPageMs": 18000
        }
        telemetry_val = base64.b64encode(json.dumps(fp).encode('utf-8')).decode('utf-8')

        # Real browser submits fields in this exact sequence with duplicated domain field
        form_data = [
            ("username", net_id),
            ("password", password),
        ]
        if ph_name:
            form_data.append((ph_name, ""))
        form_data.append(("captcha", captcha_text))
        form_data.append(("fpPayload", ""))
        form_data.append(("fpToken", ""))
        form_data.append(("telemetryPayload", telemetry_val))
        if domain_field:
            form_data.append((domain_field, dtoken_val))
        if captcha_field:
            form_data.append((captcha_field, cptoken_val))

        post_headers = {
            "Referer": LOGIN_PAGE,
            "Origin": "https://sp.srmist.edu.in",
            "Content-Type": "application/x-www-form-urlencoded",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        }

        r_login = session.post(LOGIN_SERVLET, data=form_data, timeout=15,
                               allow_redirects=True, headers=post_headers)
        print("REQUEST HEADERS SENT:")
        for k,v in r_login.request.headers.items():
            print(f"{k}: {v}")


        if "HRDSystem" not in r_login.url and "HRDSystem" not in r_login.text:
            if "Invalid captcha" in r_login.text or "Invalid Captcha" in r_login.text:
                result_data["error"] = "Invalid CAPTCHA. Please refresh and try again."
            elif "Invalid credentials" in r_login.text:
                # Debug output for invalid credentials
                debug_text = r_login.text[:500].replace('\n', ' ').replace('\r', '')
                result_data["error"] = f"Invalid credentials. Status: {r_login.status_code}. Debug: {debug_text}"
            else:
                result_data["error"] = f"Login failed. Status: {r_login.status_code}. Please check your NetID, Password, and CAPTCHA."
            return result_data

        print("[SP] Login successful! Fetching attendance and marks...")
        HRD_URL = BASE_URL + "/students/template/HRDSystem.jsp"
        ATT_REPORT_URL = BASE_URL + "/students/report/studentAttendanceDetails.jsp"
        MARKS_REPORT_URL = BASE_URL + "/students/report/studentInternalMarkDetails.jsp"

        soup_main = BeautifulSoup(r_login.text, "html.parser")
        salt = soup_main.find("input", id="csrfPreventionSalt")
        salt_val = salt.get("value", "") if salt else ""
        details = soup_main.find("input", id="hdnFormDetails")
        details_val = details.get("value", "1") if details else "1"

        ajax_headers = {
            "Referer": HRD_URL,
            "Origin": "https://sp.srmist.edu.in",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest"
        }

        # 1. Fetch Attendance
        try:
            r_att = session.post(ATT_REPORT_URL, data={
                "iden": "9",
                "filter": "",
                "hdnFormDetails": details_val,
                "csrfPreventionSalt": salt_val
            }, headers=ajax_headers, timeout=15)

            if r_att.status_code == 200:
                soup_att = BeautifulSoup(r_att.text, "html.parser")
                tables = soup_att.find_all("table")
                if tables:
                    for row in tables[0].find_all("tr")[1:]:
                        cols = [td.get_text(" ", strip=True) for td in row.find_all(["th", "td"])]
                        if len(cols) >= 6:
                            code = cols[0]
                            desc = cols[1]
                            max_h = cols[2]
                            att_h = cols[3]
                            abs_h = cols[4]
                            pct = cols[5]
                            cat = "Integrated" if code.endswith("J") else ("Practical" if code.endswith("P") else "Theory")
                            result_data["attendance"].append({
                                "courseTitle": desc,
                                "course_title": desc,
                                "courseCode": code,
                                "course_code": code,
                                "category": cat,
                                "conducted": max_h,
                                "total": max_h,
                                "max_hours": max_h,
                                "attended": pct,
                                "attended_hours": att_h,
                                "absent": abs_h,
                                "absent_hours": abs_h,
                                "percentage": pct
                            })
        except Exception as e:
            print("[SP] Attendance error: " + str(e))

        # 2. Fetch Internal Marks
        try:
            r_marks = session.post(MARKS_REPORT_URL, data={
                "iden": "13",
                "filter": "",
                "hdnFormDetails": details_val,
                "csrfPreventionSalt": salt_val
            }, headers=ajax_headers, timeout=15)

            if r_marks.status_code == 200:
                soup_marks = BeautifulSoup(r_marks.text, "html.parser")
                m_tables = soup_marks.find_all("table")
                if m_tables:
                    for row in m_tables[0].find_all("tr")[1:]:
                        cols = [td.get_text(" ", strip=True) for td in row.find_all(["th", "td"])]
                        if len(cols) >= 3:
                            code = cols[0]
                            desc = cols[1]
                            mark_str = cols[2]
                            result_data["marks"].append({
                                "courseTitle": desc,
                                "course_title": desc,
                                "courseCode": code,
                                "course_code": code,
                                "marks": mark_str,
                                "performance": [{"test_name": "Internal", "marks": mark_str}]
                            })
        except Exception as e:
            print("[SP] Marks error: " + str(e))

        result_data["success"] = True
        return result_data
    except Exception as e:
        result_data["error"] = "System Error: " + str(e)
        return result_data
