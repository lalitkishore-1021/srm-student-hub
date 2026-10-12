import re
import json
import time
import math
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any, Tuple

# SRM Standard 10-period timetable configurations
SRM_PERIOD_TIMES = [
    {"period": 1, "start": "08:00", "end": "08:50", "time": "08:00 - 08:50"},
    {"period": 2, "start": "08:50", "end": "09:40", "time": "08:50 - 09:40"},
    {"period": 3, "start": "09:45", "end": "10:35", "time": "09:45 - 10:35"},
    {"period": 4, "start": "10:40", "end": "11:30", "time": "10:40 - 11:30"},
    {"period": 5, "start": "11:35", "end": "12:25", "time": "11:35 - 12:25"},
    # Lunch break: 12:25 - 01:25
    {"period": 6, "start": "01:25", "end": "02:15", "time": "01:25 - 02:15"},
    {"period": 7, "start": "02:20", "end": "03:10", "time": "02:20 - 03:10"},
    {"period": 8, "start": "03:15", "end": "04:05", "time": "03:15 - 04:05"},
    {"period": 9, "start": "04:05", "end": "04:55", "time": "04:05 - 04:55"},
    {"period": 10, "start": "04:55", "end": "05:45", "time": "04:55 - 05:45"},
]

BATCH_GRID = {
    "1": {
        "1": ["A", "A", "F", "F", "G", "P6", "P7", "P8", "P9", "P10"],
        "2": ["P11", "P12", "P13", "P14", "P15", "B", "B", "G", "G", "A"],
        "3": ["C", "C", "A", "D", "B", "P26", "P27", "P28", "P29", "P30"],
        "4": ["P31", "P32", "P33", "P34", "P35", "D", "D", "B", "E", "C"],
        "5": ["E", "E", "C", "F", "D", "P46", "P47", "P48", "P49", "P50"]
    },
    "2": {
        "1": ["P1", "P2", "P3", "P4", "P5", "A", "A", "F", "F", "G"],
        "2": ["B", "B", "G", "G", "A", "P16", "P17", "P18", "P19", "P20"],
        "3": ["P21", "P22", "P23", "P24", "P25", "C", "C", "A", "D", "B"],
        "4": ["D", "D", "B", "E", "C", "P36", "P37", "P38", "P39", "P40"],
        "5": ["P41", "P42", "P43", "P44", "P45", "E", "E", "C", "F", "D"]
    }
}

def convert_hex_to_html(raw_content: str) -> str:
    """Decodes JavaScript-encoded / hex-escaped HTML returned by Academia page sanitize routines"""
    if not raw_content:
        return ""
    
    # Extract inside .sanitize('...') if present
    match = re.search(r"\.sanitize\(['\"](.+?)['\"]\)", raw_content, re.DOTALL)
    if match:
        content = match.group(1)
    else:
        # Check for innerHTML = pageSanitizer.sanitize(...)
        m2 = re.search(r"sanitize\(['\"](.+?)['\"]\)", raw_content, re.DOTALL)
        content = m2.group(1) if m2 else raw_content

    # Unescape hex: \xNN -> char
    content = re.sub(
        r'\\x([0-9a-fA-F]{2})',
        lambda m: chr(int(m.group(1), 16)),
        content
    )
    # Unescape other backslashes
    content = content.replace(r'\/', '/').replace(r'\-', '-').replace(r"\'", "'").replace(r'\"', '"').replace(r'\\', '\\')
    return content

class DirectAcademiaSession:
    def __init__(self, email: str, password: str):
        self.raw_email = email.strip()
        self.email = self.raw_email if '@' in self.raw_email else f"{self.raw_email}@srmist.edu.in"
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        })
        self.is_authenticated = False

    def login(self) -> Tuple[bool, str]:
        """Direct login via https://academia.srmist.edu.in/accounts/signin.ac (Official ClassPro / goscraper endpoint)"""
        url = 'https://academia.srmist.edu.in/accounts/signin.ac'
        data = {
            'username': self.email,
            'password': self.password,
            'client_portal': 'true',
            'portal': '10002227248',
            'servicename': 'ZohoCreator',
            'serviceurl': 'https://academia.srmist.edu.in/',
            'is_ajax': 'true',
            'grant_type': 'password',
            'service_language': 'en'
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://academia.srmist.edu.in',
            'Referer': 'https://academia.srmist.edu.in/'
        }

        try:
            print(f"[{self.email}] Direct Academia login attempt...")
            resp = self.session.post(url, data=data, headers=headers, timeout=12)
            
            # Check for concurrent session termination prompt
            if "concurrent" in resp.text.lower() or "terminate" in resp.text.lower():
                print(f"[{self.email}] Concurrent session detected, auto-terminating...")
                action_match = re.search(r'action="([^"]+)"', resp.text)
                action = action_match.group(1) if action_match else url
                if not action.startswith("http"):
                    action = "https://academia.srmist.edu.in" + action
                
                # Extract hidden input fields from form
                form_fields = dict(re.findall(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"', resp.text))
                self.session.post(action, data=form_fields, headers=headers, timeout=10)
                
                # Retry login
                resp = self.session.post(url, data=data, headers=headers, timeout=12)

            res_json = {}
            try:
                res_json = resp.json()
            except Exception:
                pass

            # Fast error detection
            if res_json:
                err_dict = res_json.get('error', {})
                if isinstance(err_dict, dict) and ('password' in err_dict or 'password' in str(err_dict.get('msg', '')).lower()):
                    return False, "Wrong NetID/Email or Password. Please try again."
                if res_json.get('status') == 'fail':
                    code = res_json.get('code', '')
                    if code in ['HIP_REQUIRED', 'HIP_FAILED']:
                        return False, "Portal security check required. Please try again in 1 minute."

            inner_data = res_json.get('data', {}) if isinstance(res_json, dict) else {}
            access_token = inner_data.get('access_token')
            redirect_uri = inner_data.get('oauthorize_uri')

            if access_token and redirect_uri:
                final_auth_url = f"{redirect_uri}&access_token={access_token}"
                auth_resp = self.session.get(final_auth_url, allow_redirects=True, timeout=15)
                # Verify authenticated cookies
                cookies = self.session.cookies.get_dict()
                if 'JSESSIONID' in cookies or '_iamadt_client_10002227248' in cookies or auth_resp.status_code == 200:
                    self.is_authenticated = True
                    print(f"[{self.email}] Direct Academia authentication SUCCESS!")
                    return True, "Success"

            # If signin.ac did not give token, fallback to studentinfo_scrap.py hybrid login
            print(f"[{self.email}] Trying secondary AcademiaClient fallback...")
            from studentinfo_scrap import AcademiaClient
            fallback_client = AcademiaClient(self.email, self.password)
            if fallback_client.lookup_user():
                l_res = fallback_client.login()
                if l_res.get("success"):
                    self.session = fallback_client.session
                    self.is_authenticated = True
                    print(f"[{self.email}] Secondary AcademiaClient authentication SUCCESS!")
                    return True, "Success"
                else:
                    msg = l_res.get("message", "Invalid credentials")
                    if "password" in msg.lower():
                        return False, "Wrong NetID/Email or Password. Please try again."
                    return False, msg

            return False, "Login failed: Invalid credentials or portal unreachable."
        except requests.Timeout:
            return False, "University portal took too long to respond. Please try again."
        except Exception as e:
            return False, f"Login error: {str(e)}"

    def fetch_page(self, page_name: str) -> str:
        """Fetches an Academia page and returns decoded HTML"""
        url = f"https://academia.srmist.edu.in/srm_university/academia-academic-services/page/{page_name}"
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': 'https://academia.srmist.edu.in/',
            'X-Requested-With': 'XMLHttpRequest'
        }
        try:
            resp = self.session.get(url, headers=headers, timeout=12)
            if resp.status_code == 200 and len(resp.text) > 100:
                return convert_hex_to_html(resp.text)
        except Exception as e:
            print(f"[{self.email}] Failed to fetch page {page_name}: {e}")
        return ""

def calculate_bunk_margin_and_needed(pct: float, conducted: int, absent: int) -> Tuple[int, int, str]:
    """
    Ratio-D Attendance Formula:
    - If pct >= 75: margin = floor((present - 0.75 * conducted) / 0.75) (Classes that can be safely bunked)
    - If pct < 75: needed = increment until (present + needed) / (conducted + needed) * 100 >= 75
    - status: 'safe' (>= 85%), 'danger' (75-84%), 'cooked' (< 75%)
    """
    if conducted == 0:
        return 0, 0, "safe"

    present = max(0, conducted - absent)
    
    if pct >= 75.0:
        margin = math.floor((present - 0.75 * conducted) / 0.75)
        margin = max(0, margin)
        status = "safe" if pct >= 85.0 else "danger"
        return margin, 0, status
    else:
        needed = 0
        while (conducted + needed > 0) and (((present + needed) / (conducted + needed)) * 100.0 < 75.0):
            needed += 1
            if needed > 200:
                break
        return 0, needed, "cooked"

def get_course_credit(code: str, title: str, registered_courses: List[Dict[str, Any]] = None) -> float:
    """Accurately calculates or matches SRM course credits"""
    clean_code = (code or '').upper().strip()
    clean_title = (title or '').upper().strip()

    # 1. Match from registered course table if available
    if registered_courses:
        base_c = re.sub(r'[^A-Z0-9]', '', clean_code)
        for rc in registered_courses:
            rc_code = re.sub(r'[^A-Z0-9]', '', str(rc.get('code', '')).upper())
            if rc_code and (rc_code == base_c or rc_code.startswith(base_c[:8]) or base_c.startswith(rc_code[:8])):
                try:
                    cred = float(rc.get('credit', 0))
                    if cred > 0: return cred
                except: pass
            rc_title = str(rc.get('title', '')).upper().strip()
            if rc_title and rc_title == clean_title:
                try:
                    cred = float(rc.get('credit', 0))
                    if cred > 0: return cred
                except: pass

    # 2. Standard SRM credit heuristics
    if ('21MAB' in clean_code or '18MAB' in clean_code or 'MAB' in clean_code or
        'MATHEMATICS' in clean_title or 'TRANSFORMS' in clean_title or 'CALCULUS' in clean_title or
        'LINEAR ALGEBRA' in clean_title or 'PROBABILITY' in clean_title):
        return 4.0
    if clean_code.endswith('J'):
        return 4.0
    elif clean_code.endswith('P') or clean_code.endswith('L') or 'LAB' in clean_title or 'PRACTICAL' in clean_title:
        return 2.0 if clean_code.endswith('P') else 1.5
    elif 'PROJECT' in clean_title or 'CAPSTONE' in clean_title:
        return 3.0
    elif ('UNIVERSAL HUMAN VALUES' in clean_title or 'UHV' in clean_title or 'SKILL' in clean_title or 
          'CONSTITUTION' in clean_title or 'VALUE EDUCATION' in clean_title):
        return 1.0
    return 3.0

def parse_student_profile(soup: BeautifulSoup, raw_html: str, net_id: str) -> Dict[str, Any]:
    """Parses full student profile dynamically without any hardcoding"""
    data = {
        "name": "",
        "reg_no": "",
        "program": "",
        "department": "",
        "section": "",
        "semester": "",
        "batch": "1",
        "fa_name": "",
        "fa_email": "",
        "fa_phone": "",
        "aa_name": "",
        "aa_email": "",
        "aa_phone": ""
    }

    # Extract Reg No via Regex (RA...)
    ra_match = re.search(r'RA2\d{12}', raw_html)
    if ra_match:
        data["reg_no"] = ra_match.group(0)

    # Parse key-value cells from student tables
    for tr in soup.find_all('tr'):
        cells = tr.find_all('td')
        if len(cells) >= 2:
            for i in range(0, len(cells) - 1, 2):
                key = cells[i].get_text(separator=' ', strip=True).rstrip(':').strip().lower()
                val = cells[i + 1].get_text(separator=' ', strip=True).strip()

                if "registration number" in key and not data["reg_no"]:
                    data["reg_no"] = val
                elif key == "name" and not data["name"]:
                    data["name"] = val
                elif "program" in key and not data["program"]:
                    data["program"] = val
                elif "combo / batch" in key or key == "batch":
                    b_match = re.search(r'\b([12])\b', val)
                    if b_match:
                        data["batch"] = b_match.group(1)
                elif key == "semester" and not data["semester"]:
                    sem_num = re.search(r'\d+', val)
                    data["semester"] = sem_num.group(0) if sem_num else val
                elif "department" in key and not data["department"]:
                    # e.g. "Computer Science and Engineering - (V1 Section)" or "Mechanical Engineering"
                    if '-' in val:
                        parts = val.split('-')
                        data["department"] = parts[0].strip()
                        sec_str = parts[1].replace('(', '').replace(')', '').replace('Section', '').strip()
                        data["section"] = sec_str
                    else:
                        data["department"] = val

    # Parse Advisors (Faculty Advisor & Academic Advisor)
    for td in soup.find_all('td', {'align': 'center'}):
        text = td.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Check Faculty Advisor
        if any('Faculty Advisor' in l for l in lines):
            f_idx = next((i for i, l in enumerate(lines) if 'Faculty Advisor' in l), -1)
            if f_idx > 0:
                data["fa_name"] = lines[f_idx - 1]
            data["fa_email"] = next((l for l in lines if '@srmist.edu.in' in l), '')
            data["fa_phone"] = next((l for l in lines if re.sub(r'[\s\-+]', '', l).isdigit() and len(re.sub(r'[\s\-+]', '', l)) >= 10), '')
        
        # Check Academic Advisor
        if any('Academic Advisor' in l for l in lines):
            a_idx = next((i for i, l in enumerate(lines) if 'Academic Advisor' in l), -1)
            if a_idx > 0:
                data["aa_name"] = lines[a_idx - 1]
            data["aa_email"] = next((l for l in lines if '@srmist.edu.in' in l), '')
            data["aa_phone"] = next((l for l in lines if re.sub(r'[\s\-+]', '', l).isdigit() and len(re.sub(r'[\s\-+]', '', l)) >= 10), '')

    # Set fallbacks if name/reg_no were not found
    if not data["name"]:
        data["name"] = net_id.upper()
    if not data["reg_no"]:
        data["reg_no"] = net_id.upper()

    return data

def parse_registered_courses(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Parses course registration list (Code, Title, Credit, Category, Type, Faculty, Slot, Room)"""
    courses = []
    course_table = soup.find('table', {'class': 'course_tbl'})
    if not course_table:
        for tbl in soup.find_all('table'):
            txt = tbl.get_text()
            if 'Course Code' in txt and 'Course Title' in txt and 'Slot' in txt:
                course_table = tbl
                break

    if not course_table:
        return courses

    for tr in course_table.find_all('tr')[1:]:
        tds = tr.find_all('td')
        if len(tds) >= 9:
            texts = [td.get_text(separator=' ', strip=True) for td in tds]
            if texts[0].isdigit() and len(texts[1]) >= 3:
                code = texts[1].strip()
                title = texts[2].strip()
                credit_str = texts[3].strip()
                try:
                    credit_val = float(credit_str)
                    if credit_val.is_integer(): credit_val = int(credit_val)
                except:
                    credit_val = 0

                cat = texts[5].strip() if len(texts) > 5 else ""
                ctype = texts[6].strip() if len(texts) > 6 else ""
                faculty = texts[7].strip() if len(texts) > 7 else ""
                slot = texts[8].strip().rstrip('-').strip()
                room = texts[9].strip() if len(texts) > 9 else ""

                courses.append({
                    "code": code,
                    "title": title,
                    "credit": credit_val,
                    "category": cat,
                    "type": ctype,
                    "faculty": faculty,
                    "slot": slot,
                    "room": room
                })
    return courses

def parse_attendance_and_marks(soup: BeautifulSoup, courses: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses attendance and marks with Ratio-D metrics"""
    att_list = []
    marks_list = []

    # 1. Attendance Table
    att_table = None
    for tbl in soup.find_all('table'):
        t_text = tbl.get_text()
        if 'Course Code' in t_text and ('Hours Conducted' in t_text or 'Attn %' in t_text or 'Hours Absent' in t_text):
            att_table = tbl
            break

    if att_table:
        for tr in att_table.find_all('tr')[1:]:
            tds = tr.find_all('td')
            if len(tds) >= 8:
                raw_code = tds[0].get_text(separator=' ', strip=True)
                code_parts = raw_code.split()
                clean_code = code_parts[0] if code_parts else ""
                if not clean_code or 'course' in clean_code.lower() or 'code' in clean_code.lower():
                    continue

                clean_title = tds[1].get_text(separator=' ', strip=True)
                category = tds[2].get_text(separator=' ', strip=True)
                faculty = tds[3].get_text(separator=' ', strip=True) if len(tds) > 3 else ""
                slot = tds[4].get_text(separator=' ', strip=True) if len(tds) > 4 else ""
                room = tds[5].get_text(separator=' ', strip=True) if len(tds) > 5 else ""

                cond_m = re.search(r'\d+', tds[6].get_text(strip=True))
                abs_m = re.search(r'\d+', tds[7].get_text(strip=True))
                conducted = int(cond_m.group(0)) if cond_m else 0
                absent = int(abs_m.group(0)) if abs_m else 0
                present = max(0, conducted - absent)

                pct = 0.0
                if len(tds) >= 9:
                    pct_m = re.search(r'[\d.]+', tds[8].get_text(strip=True))
                    if pct_m: pct = float(pct_m.group(0))
                elif conducted > 0:
                    pct = round((present / conducted) * 100.0, 2)

                # Ratio-D bunk margin and recovery
                safe_margin, classes_needed, status_badge = calculate_bunk_margin_and_needed(pct, conducted, absent)
                credit = get_course_credit(clean_code, clean_title, courses)

                att_list.append({
                    "courseTitle": clean_title,
                    "courseCode": clean_code,
                    "category": category,
                    "faculty": faculty,
                    "slot": slot,
                    "room": room,
                    "conducted": conducted,
                    "absent": absent,
                    "present": present,
                    "attended": pct,
                    "credit": credit,
                    "bunk_margin": safe_margin,
                    "classes_needed": classes_needed,
                    "status_badge": status_badge,
                    "classes_per_cycle": 1
                })

    # 2. Marks Table
    marks_table = None
    for tbl in soup.find_all('table'):
        t_text = tbl.get_text()
        if 'Course Code' in t_text and ('Test Performance' in t_text or 'Assessment' in t_text):
            marks_table = tbl
            break

    if marks_table:
        for tr in marks_table.find_all('tr')[1:]:
            tds = tr.find_all('td')
            if len(tds) >= 3:
                course_code = tds[0].get_text(strip=True)
                course_type = tds[1].get_text(strip=True)

                if not re.match(r'^\d{2}[A-Z]{3}\d{3}[A-Z]$', course_code) and len(course_code) < 5:
                    continue

                # Find actual title from registered courses or attendance
                course_title = course_code
                for c in courses:
                    if c.get('code') == course_code:
                        course_title = c.get('title', course_code)
                        break
                if course_title == course_code:
                    for a in att_list:
                        if a.get('courseCode') == course_code:
                            course_title = a.get('courseTitle', course_code)
                            break

                perf_cell = tds[2]
                tests = []
                perf_strings = []

                inner_tbl = perf_cell.find('table')
                if inner_tbl:
                    for row in inner_tbl.find_all('tr'):
                        for c_cell in row.find_all('td'):
                            lines = [l.strip() for l in c_cell.get_text(separator='\n', strip=True).split('\n') if l.strip()]
                            if len(lines) >= 2 and '/' in lines[0]:
                                t_name, max_m = lines[0].split('/', 1)
                                try:
                                    max_val = float(max_m)
                                    score_val = float(lines[1])
                                    tests.append({
                                        "test_name": t_name.strip(),
                                        "max": max_val,
                                        "obtained": score_val
                                    })
                                    perf_strings.append(f"{t_name.strip()}/{max_val:.2f} | {score_val:.2f}")
                                except:
                                    pass

                perf_formatted = "   ".join(perf_strings) if perf_strings else "No tests available."
                credit = get_course_credit(course_code, course_title, courses)

                marks_list.append({
                    "courseTitle": course_title,
                    "courseCode": course_code,
                    "courseType": course_type,
                    "performance": perf_formatted,
                    "tests": tests,
                    "credit": credit
                })

    return att_list, marks_list

def expand_slot_range(slot_str: str) -> List[str]:
    """Expands slot ranges e.g. P6-P8 into ['P6', 'P7', 'P8'], or A / A into ['A']"""
    clean = (slot_str or '').strip()
    if not clean:
        return []

    # Check P-range: P6-P8, P11-P15, P1-P3
    m = re.match(r'^P(\d+)\s*[-\u2013]\s*P?(\d+)$', clean, re.IGNORECASE)
    if m:
        start_p = int(m.group(1))
        end_p = int(m.group(2))
        if start_p <= end_p and (end_p - start_p) <= 6:
            return [f"P{i}" for i in range(start_p, end_p + 1)]

    # Split by slash, comma, hyphen
    parts = [p.strip() for p in re.split(r'[/,]', clean) if p.strip()]
    res = []
    for p in parts:
        # Check sub-range
        m2 = re.match(r'^P(\d+)\s*[-\u2013]\s*P?(\d+)$', p, re.IGNORECASE)
        if m2:
            s_p = int(m2.group(1))
            e_p = int(m2.group(2))
            res.extend([f"P{i}" for i in range(s_p, e_p + 1)])
        else:
            res.append(p)
    return res if res else [clean]

def detect_batch(courses: List[Dict[str, Any]], reported_batch: str) -> str:
    """Auto-detects student batch based on lab slots"""
    b1_hits, b2_hits = 0, 0
    for c in courses:
        slot_str = str(c.get('slot', '')).upper()
        # Batch 2 morning labs: P1-P5, P21-P25, P41-P45
        for s in ['P1', 'P2', 'P3', 'P4', 'P5', 'P21', 'P22', 'P23', 'P24', 'P25', 'P41', 'P42', 'P43', 'P44', 'P45']:
            if re.search(r'\b' + s + r'\b', slot_str):
                b2_hits += 1
        # Batch 1 afternoon labs: P6-P10, P26-P30, P46-P50
        for s in ['P6', 'P7', 'P8', 'P9', 'P10', 'P26', 'P27', 'P28', 'P29', 'P30', 'P46', 'P47', 'P48', 'P49', 'P50']:
            if re.search(r'\b' + s + r'\b', slot_str):
                b1_hits += 1

    if b2_hits > b1_hits: return "2"
    if b1_hits > b2_hits: return "1"
    m = re.search(r'[12]', str(reported_batch))
    return m.group(0) if m else "1"

def build_student_timetable(courses: List[Dict[str, Any]], reported_batch: str) -> Dict[str, List[Dict[str, Any]]]:
    """Builds Day 1 to Day 5 timetable with accurate SRM period timings, lunch break, and lab merging"""
    batch = detect_batch(courses, reported_batch)
    schedule = BATCH_GRID.get(batch, BATCH_GRID["1"])
    
    # Pre-map all courses to their individual slots
    slot_to_course: Dict[str, Dict[str, Any]] = {}
    for c in courses:
        slot_str = c.get('slot', '')
        expanded = expand_slot_range(slot_str)
        for s in expanded:
            s_up = s.upper()
            slot_to_course[s_up] = c
            # Also map base letters (e.g. A1 -> A if not mapped)
            m_base = re.match(r'^([A-G])\d*$', s_up)
            if m_base:
                base_letter = m_base.group(1)
                if base_letter not in slot_to_course:
                    slot_to_course[base_letter] = c

    final_tt: Dict[str, List[Dict[str, Any]]] = {}

    for day in ["1", "2", "3", "4", "5"]:
        final_tt[day] = []
        day_slots = schedule.get(day, [])

        for idx, slot_code in enumerate(day_slots):
            if idx >= len(SRM_PERIOD_TIMES):
                break
            
            p_time = SRM_PERIOD_TIMES[idx]
            slot_up = slot_code.upper().strip()
            
            matched_course = slot_to_course.get(slot_up)
            if not matched_course:
                # Try matching base letter
                m_b = re.match(r'^([A-G])', slot_up)
                if m_b and m_b.group(1) in slot_to_course:
                    matched_course = slot_to_course[m_b.group(1)]

            if matched_course:
                course_title = matched_course.get('title', '')
                course_code = matched_course.get('code', '')
                room = matched_course.get('room', 'TBA')
                c_type = matched_course.get('type', '')
                
                entry = {
                    "time": p_time["time"],
                    "start_time": p_time["start"],
                    "end_time": p_time["end"],
                    "subject": f"{course_title} ({course_code})",
                    "code": course_code,
                    "room": room,
                    "slot": slot_code,
                    "type": c_type,
                    "period_start": p_time["period"],
                    "period_end": p_time["period"]
                }

                # Check if consecutive period can be merged (same subject and room, strictly sequential)
                if final_tt[day]:
                    last = final_tt[day][-1]
                    if (last.get("code") == entry["code"] and 
                        last.get("room") == entry["room"] and 
                        last.get("period_end") + 1 == entry["period_start"] and
                        last.get("period_end") != 5): # Do not merge across lunch break (period 5 to 6)
                        last["end_time"] = entry["end_time"]
                        last["time"] = f"{last['start_time']} - {last['end_time']}"
                        last["slot"] = f"{last['slot']}, {entry['slot']}"
                        last["period_end"] = entry["period_end"]
                        continue

                final_tt[day].append(entry)

    return final_tt

def fetch_academia_data(email: str, password: str) -> Dict[str, Any]:
    """
    Main complete fetch routine:
    1. Direct login to Academia (< 1-2s)
    2. Multi-page fetch (My_Time_Table and My_Attendance)
    3. Decode sanitization hex strings
    4. Parse Profile, Courses, Attendance, Marks, Timetable
    """
    session = DirectAcademiaSession(email, password)
    success, msg = session.login()
    if not success:
        return {"success": False, "error": msg}

    clean_net_id = session.email.split('@')[0].upper()

    # 1. Fetch Timetable / Course Page
    tt_html = ""
    for page in ["My_Time_Table_2024_25", "My_Time_Table_2025_26", "My_Time_Table_2023_24", "My_Time_Table"]:
        tt_html = session.fetch_page(page)
        if "course_tbl" in tt_html or "Course Code" in tt_html:
            break

    # 2. Fetch Attendance / Marks Page
    att_html = ""
    for page in ["My_Attendance", "My_Attendance_2024_25", "My_Attendance_2025_26", "My_Attendance_2023_24", "Attendance"]:
        att_html = session.fetch_page(page)
        if "Hours Conducted" in att_html or "Attn %" in att_html or "Attendance %" in att_html:
            break

    # If neither page returned data, return error
    if not tt_html and not att_html:
        return {"success": False, "error": "Academia portal returned empty academic pages."}

    # Combine soups
    tt_soup = BeautifulSoup(tt_html, 'html.parser') if tt_html else None
    att_soup = BeautifulSoup(att_html, 'html.parser') if att_html else None

    # Parse profile from whichever page is richer
    profile = {}
    if att_soup and len(att_html) > 500:
        profile = parse_student_profile(att_soup, att_html, clean_net_id)
    if not profile.get("program") and tt_soup:
        profile = parse_student_profile(tt_soup, tt_html, clean_net_id)

    # Parse courses
    courses = []
    if tt_soup:
        courses = parse_registered_courses(tt_soup)

    # Parse attendance and marks
    attendance = []
    marks = []
    if att_soup:
        attendance, marks = parse_attendance_and_marks(att_soup, courses)

    # Build timetable
    reported_batch = profile.get("batch", "1")
    timetable = build_student_timetable(courses, reported_batch)

    print(f"[{session.email}] Scraped: Profile={bool(profile.get('name'))}, Courses={len(courses)}, Att={len(attendance)}, Marks={len(marks)}, TT days={len(timetable)}")

    return {
        "success": True,
        "profile": profile,
        "courses": courses,
        "data": attendance,
        "marks": marks,
        "timetable": timetable,
        "is_mock_attendance": False
    }
