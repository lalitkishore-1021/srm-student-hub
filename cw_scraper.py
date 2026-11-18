import concurrent.futures
import json
import re
import socket
import urllib3.util.connection as urllib3_cn

import requests

from academia_direct_scraper import calculate_bunk_margin_and_needed, get_course_credit

# Force IPv4 socket resolution to prevent Cloudflare IPv6 handshake timeouts on Windows/Linux
try:
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

CW_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
    'Origin': 'https://campusweb.in',
    'Referer': 'https://campusweb.in/',
    'X-Client': 'web',
    'X-Device-Platform': 'Windows',
    'X-Device-Name': 'Chrome',
    'X-Device-Model': 'Chrome 126.0.0.0',
    'X-App-Version': '2026.10.08-sessions.3',
}


def scrape_campusweb(netid: str, portal_pwd: str, acad_pwd: str = None):
    """
    Scrapes live SRM Student Portal attendance and internal marks via CampusWeb API.
    Uses CampusWeb session tokens without requiring fragile client-side CAPTCHA solving.
    """
    clean_id = (netid or "").strip()
    if '@' in clean_id:
        clean_id = clean_id.split('@')[0].strip().lower()
    else:
        clean_id = clean_id.lower()

    portal_pwd = (portal_pwd or "").strip()
    acad_pwd = (acad_pwd or "").strip() or portal_pwd

    if not clean_id or not portal_pwd:
        return {'success': False, 'error': 'Missing credentials for CampusWeb sync', 'reason': 'missing_credentials'}

    session = requests.Session()
    session.headers.update(CW_HEADERS)

    # 1. Establish session on CampusWeb auth endpoint (uses Academia credentials)
    cookies_str = None
    session_token = None
    try:
        auth_resp = session.post(
            'https://api.campusweb.in/api/auth/login',
            json={'username': f'{clean_id}@srmist.edu.in', 'password': acad_pwd},
            timeout=15,
        )
        if auth_resp.status_code == 200:
            auth_data = auth_resp.json()
            if auth_data.get('Status') == 'success':
                cookies_str = auth_data.get('Cookies')
                session_token = auth_data.get('sessionToken')
    except Exception as ae:
        print(f"[{clean_id}] CampusWeb auth warning: {ae}")

    # Fallback: if auth/login failed with acad_pwd and portal_pwd differs, try portal_pwd for auth
    if not session_token and portal_pwd != acad_pwd:
        try:
            auth_resp2 = session.post(
                'https://api.campusweb.in/api/auth/login',
                json={'username': f'{clean_id}@srmist.edu.in', 'password': portal_pwd},
                timeout=12,
            )
            if auth_resp2.status_code == 200:
                auth_data2 = auth_resp2.json()
                if auth_data2.get('Status') == 'success':
                    cookies_str = auth_data2.get('Cookies')
                    session_token = auth_data2.get('sessionToken')
        except Exception:
            pass

    # 2. Authenticate with Student Portal via CampusWeb
    sp_headers = dict(CW_HEADERS)
    if cookies_str:
        sp_headers['X-CSRF-Token'] = cookies_str
    sp_headers['X-Net-ID'] = clean_id
    if session_token:
        sp_headers['X-Session-Token'] = session_token

    session.headers.update(sp_headers)

    try:
        sp_res = session.post(
            'https://api.campusweb.in/api/student-portal/login',
            json={'net_id': clean_id, 'password': portal_pwd},
            timeout=22,
        )
        if sp_res.status_code != 200:
            err_msg = 'Invalid NetID or Student Portal password'
            try:
                err_msg = sp_res.json().get('message', err_msg)
            except Exception:
                pass
            if sp_res.status_code == 429 or 'too many attempts' in err_msg.lower():
                return {
                    'success': False,
                    'error': 'SRM Student Portal security rate limit reached. Please wait a few minutes before trying again.',
                    'reason': 'rate_limited'
                }
            return {'success': False, 'error': err_msg, 'reason': 'invalid_credentials'}

        sp_data = sp_res.json()
        if sp_data.get('status') != 'success':
            err_msg = sp_data.get('message', 'Student Portal login rejected')
            if 'too many attempts' in err_msg.lower():
                return {
                    'success': False,
                    'error': 'SRM Student Portal security rate limit reached. Please wait a few minutes before trying again.',
                    'reason': 'rate_limited'
                }
            return {'success': False, 'error': err_msg, 'reason': 'invalid_credentials'}

        sp_token = sp_data.get('session_token')
        if sp_token:
            session.headers.update({'X-Session-Token': sp_token})

    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'CampusWeb timed out waiting for Student Portal. Please try again.', 'reason': 'timeout'}
    except Exception as e:
        return {'success': False, 'error': f'CampusWeb connection error: {e}', 'reason': 'network_error'}

    # 3. Parallel fetching of Attendance, Marks, Profile
    att_json = {}
    marks_json = {}
    prof_json = {}

    def fetch_att():
        try:
            r = session.post(
                'https://api.campusweb.in/api/student-portal/attendance',
                json={'net_id': clean_id, 'password': portal_pwd},
                timeout=18,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"[{clean_id}] CampusWeb attendance warning: {e}")
        return {}

    def fetch_marks():
        try:
            r = session.post(
                'https://api.campusweb.in/api/student-portal/marks',
                json={'net_id': clean_id, 'password': portal_pwd},
                timeout=18,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"[{clean_id}] CampusWeb marks warning: {e}")
        return {}

    def fetch_profile():
        try:
            r = session.post(
                'https://api.campusweb.in/api/student-portal/profile',
                json={'net_id': clean_id, 'password': portal_pwd},
                timeout=18,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"[{clean_id}] CampusWeb profile warning: {e}")
        return {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        f_att = pool.submit(fetch_att)
        f_marks = pool.submit(fetch_marks)
        f_prof = pool.submit(fetch_profile)

        att_json = f_att.result()
        marks_json = f_marks.result()
        prof_json = f_prof.result()

    raw_att_list = att_json.get('attendance') if isinstance(att_json, dict) else []
    if not raw_att_list:
        return {'success': False, 'error': 'No attendance records returned from Student Portal', 'reason': 'empty_data'}

    # 4. Parse Attendance with Ratio-D metrics
    att_data = []
    for item in raw_att_list:
        code = (item.get('subjectcode', '') or '').strip().upper()
        title = (item.get('subjectdesc', '') or '').strip().upper()
        conducted = int(float(item.get('total', 0)))
        absent = int(float(item.get('absent', 0)))
        present = int(conducted - absent)
        percent = float(item.get('presentpercentage', 0))
        safe_margin, classes_needed, status_badge = calculate_bunk_margin_and_needed(percent, conducted, absent)
        credit = get_course_credit(code, title)

        att_data.append({
            "courseTitle": item.get('subjectdesc', ''),
            "courseCode": code,
            "category": "THEORY",
            "faculty": "",
            "slot": "",
            "room": "",
            "conducted": conducted,
            "absent": absent,
            "present": present,
            "attended": percent,
            "credit": credit,
            "credits": credit,
            "bunk_margin": safe_margin,
            "classes_needed": classes_needed,
            "status_badge": status_badge,
            "classes_per_cycle": 1,
        })

    # 5. Parse Marks with individual test breakdowns
    marks_data = []
    marked_courses = set()
    if isinstance(marks_json, dict) and marks_json.get('status') == 'success':
        for item in marks_json.get('testPerformances', []):
            ccode = (item.get('courseCode', '') or '').strip().upper()
            marked_courses.add(ccode)

            tests_dict = item.get('tests', {}) if isinstance(item.get('tests'), dict) else {}
            tests_list = []
            perf_parts = []
            for test_name, test_data in tests_dict.items():
                if test_name.lower() in ['internal marks', 'total', 'overall', 'internal']:
                    continue
                got = float(test_data.get('got', 0))
                total = float(test_data.get('total', 0))
                if total > 0:
                    tests_list.append({
                        "test_name": test_name,
                        "testName": test_name,
                        "max": total,
                        "obtained": got,
                    })
                    perf_parts.append(f"{test_name}/{total:.2f} | {got:.2f}")

            if not perf_parts and 'totalMarks' in item and float(item.get('totalMarks', 0)) > 0:
                tot_m = float(item.get('totalMarks', 0))
                got_m = float(item.get('totalMarkGot', 0))
                tests_list.append({
                    "test_name": "Internal",
                    "testName": "Internal",
                    "max": tot_m,
                    "obtained": got_m,
                })
                perf_parts.append(f"Internal/{tot_m:.2f} | {got_m:.2f}")

            perfString = "   ".join(perf_parts) if perf_parts else "No tests conducted yet"
            credit = get_course_credit(ccode, item.get('courseName', ''))

            marks_data.append({
                "courseTitle": item.get('courseName', ''),
                "courseCode": ccode,
                "courseType": item.get('courseType', 'Theory'),
                "performance": perfString,
                "Test Performance": perfString,
                "marks": perfString,
                "tests": tests_list,
                "credit": credit,
                "credits": credit,
            })

    # Merge missing courses from attendance into marks_data
    for att in att_data:
        if att["courseCode"].upper() not in marked_courses:
            marks_data.append({
                "courseTitle": att["courseTitle"],
                "courseCode": att["courseCode"],
                "courseType": "Theory",
                "performance": "No tests conducted yet",
                "Test Performance": "No tests conducted yet",
                "marks": "No tests conducted yet",
                "tests": [],
                "credit": att.get("credit", 3.0),
                "credits": att.get("credit", 3.0),
            })

    # 6. Parse Profile
    profile_raw = (prof_json or {}).get('profile', {}) if isinstance(prof_json, dict) else {}

    def parse_advisor(adv_str):
        if not adv_str or not isinstance(adv_str, str):
            return {"name": "", "email": ""}
        m = re.search(r'\[([^\]]+)\]', adv_str)
        email = m.group(1).strip() if m else ""
        name = re.sub(r'\[.*?\]', '', adv_str).strip()
        name = re.sub(r'\s+', ' ', name)
        return {"name": name, "email": email}

    fa_info = parse_advisor(profile_raw.get('faculty_advisor'))
    aa_info = parse_advisor(profile_raw.get('academic_advisor'))

    profile_data = {
        "name": (profile_raw.get('student_name') or '').strip(),
        "regNo": (profile_raw.get('registration_number') or '').strip() or clean_id.upper(),
        "course": (profile_raw.get('program') or '').strip() or 'SRM University',
        "semester": str(profile_raw.get('semester') or '').strip(),
        "section": (profile_raw.get('section') or '').strip(),
        "batch": str(profile_raw.get('batch') or '1').strip(),
        "fa_name": fa_info["name"],
        "fa_email": fa_info["email"],
        "fa_phone": "",
        "aa_name": aa_info["name"],
        "aa_email": aa_info["email"],
        "aa_phone": "",
        "advisor": fa_info["name"] or aa_info["name"],
    }

    print(f"[{clean_id}] [CAMPUSWEB] Scraped: {len(att_data)} attendance, {len(marks_data)} marks")
    return {
        "success": True,
        "attendance": att_data,
        "data": att_data,
        "marks": marks_data,
        "profile": profile_data,
        "source": "campusweb_api",
    }
