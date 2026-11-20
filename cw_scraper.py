import concurrent.futures
import json
import re
import socket
import urllib3.util.connection as urllib3_cn

# Force IPv4 socket resolution to prevent Cloudflare IPv6 handshake timeouts on Windows/Linux
try:
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

try:
    from curl_cffi import requests as c_requests
    HAS_CURL_CFFI = True
except Exception:
    HAS_CURL_CFFI = False
    import requests as c_requests

from academia_direct_scraper import calculate_bunk_margin_and_needed, get_course_credit

CW_HEADERS = {
    'Origin': 'https://campusweb.in',
    'Referer': 'https://campusweb.in/',
    'X-Client': 'web',
    'X-Device-Platform': 'Windows',
    'X-Device-Name': 'Chrome',
    'X-Device-Model': 'Chrome 131.0.0.0',
    'X-App-Version': '2026.10.08-sessions.3',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
}


def _create_session():
    if HAS_CURL_CFFI:
        return c_requests.Session(impersonate='chrome120')
    import requests
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    })
    return s


def scrape_campusweb(netid: str, portal_pwd: str, acad_pwd: str = None):
    """
    Scrapes live SRM Student Portal attendance and internal marks via CampusWeb API (campusweb.in).
    Uses browser TLS fingerprint impersonation to bypass Cloudflare WAF on datacenter/cloud IPs.
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

    session = _create_session()
    headers = dict(CW_HEADERS)
    headers['X-Net-ID'] = clean_id

    sp_token = None
    cookies_str = None
    session_token = None

    # Step 1: Direct Student Portal authentication
    try:
        sp_res = session.post(
            'https://api.campusweb.in/api/student-portal/login',
            headers=headers,
            json={'net_id': clean_id, 'password': portal_pwd},
            timeout=20,
        )
        if sp_res.status_code == 200:
            sp_data = sp_res.json()
            if sp_data.get('status') == 'success':
                sp_token = sp_data.get('session_token')
        elif sp_res.status_code == 401:
            err_msg = 'Invalid NetID or Student Portal password'
            try:
                err_msg = sp_res.json().get('message', err_msg)
            except Exception:
                pass
            return {'success': False, 'error': err_msg, 'reason': 'invalid_credentials'}
        elif sp_res.status_code == 429:
            return {
                'success': False,
                'error': 'SRM Student Portal security rate limit reached. Please wait a few minutes before trying again.',
                'reason': 'rate_limited'
            }
    except Exception as e:
        print(f"[{clean_id}] CampusWeb direct portal login notice: {e}")

    # Step 2: Fallback via Academia /api/auth/login if direct SP login did not yield token
    if not sp_token:
        try:
            auth_res = session.post(
                'https://api.campusweb.in/api/auth/login',
                headers=headers,
                json={'username': f'{clean_id}@srmist.edu.in', 'password': acad_pwd},
                timeout=15,
            )
            if auth_res.status_code == 200:
                auth_data = auth_res.json()
                if auth_data.get('Status') == 'success':
                    cookies_str = auth_data.get('Cookies')
                    session_token = auth_data.get('sessionToken')
                    if cookies_str:
                        headers['X-CSRF-Token'] = cookies_str
                    if session_token:
                        headers['X-Session-Token'] = session_token

                    # Retry portal login with session tokens
                    sp_res2 = session.post(
                        'https://api.campusweb.in/api/student-portal/login',
                        headers=headers,
                        json={'net_id': clean_id, 'password': portal_pwd},
                        timeout=20,
                    )
                    if sp_res2.status_code == 200:
                        sp_data2 = sp_res2.json()
                        if sp_data2.get('status') == 'success':
                            sp_token = sp_data2.get('session_token')
                    elif sp_res2.status_code == 401:
                        return {'success': False, 'error': 'Invalid NetID or Student Portal password', 'reason': 'invalid_credentials'}
                    elif sp_res2.status_code == 429:
                        return {
                            'success': False,
                            'error': 'SRM Student Portal security rate limit reached. Please wait a few minutes before trying again.',
                            'reason': 'rate_limited'
                        }
        except Exception as ae:
            print(f"[{clean_id}] CampusWeb auth fallback notice: {ae}")

    if not sp_token:
        return {
            'success': False,
            'error': 'Could not authenticate with SRM Student Portal. Please verify your password.',
            'reason': 'portal_login_failed'
        }

    headers['X-Session-Token'] = sp_token

    # Step 3: Parallel fetch of Attendance, Marks, Profile
    att_json = {}
    marks_json = {}
    prof_json = {}

    def fetch_att():
        try:
            r = session.post(
                'https://api.campusweb.in/api/student-portal/attendance',
                headers=headers,
                json={'net_id': clean_id, 'password': portal_pwd},
                timeout=18,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"[{clean_id}] CampusWeb attendance fetch warning: {e}")
        return {}

    def fetch_marks():
        try:
            r = session.post(
                'https://api.campusweb.in/api/student-portal/marks',
                headers=headers,
                json={'net_id': clean_id, 'password': portal_pwd},
                timeout=18,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"[{clean_id}] CampusWeb marks fetch warning: {e}")
        return {}

    def fetch_profile():
        try:
            r = session.post(
                'https://api.campusweb.in/api/student-portal/profile',
                headers=headers,
                json={'net_id': clean_id, 'password': portal_pwd},
                timeout=18,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"[{clean_id}] CampusWeb profile fetch warning: {e}")
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
        present = int(float(item.get('present', conducted - absent)))
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

    # 5. Parse Marks with exact test breakdowns
    marks_data = []
    marked_courses = set()
    if isinstance(marks_json, dict) and (marks_json.get('status') == 'success' or marks_json.get('testPerformances')):
        for item in marks_json.get('testPerformances', []):
            ccode = (item.get('courseCode', '') or '').strip().upper()
            marked_courses.add(ccode)

            tests_dict = item.get('tests', {}) if isinstance(item.get('tests'), dict) else {}
            test_list = []
            for test_name, test_info in tests_dict.items():
                if not isinstance(test_info, dict):
                    continue
                scored = float(test_info.get('got', 0) if test_info.get('got') is not None else test_info.get('scored', 0) or 0)
                max_marks = float(test_info.get('total', 0) if test_info.get('total') is not None else test_info.get('max', 0) or 0)
                pct = float(test_info.get('percentage', 0) or 0)
                test_list.append({
                    'name': test_name,
                    'scored': round(scored, 2),
                    'max': round(max_marks, 2),
                    'percentage': round(pct, 2)
                })

            total_got = float(item.get('totalMarkGot', 0) if item.get('totalMarkGot') is not None else item.get('totalScored', 0) or 0)
            total_max = float(item.get('totalMarks', 0) if item.get('totalMarks') is not None else item.get('totalMax', 0) or 0)
            ctitle = (item.get('courseName') or item.get('courseTitle') or ccode).strip()

            marks_data.append({
                'courseCode': ccode,
                'courseTitle': ctitle,
                'tests': test_list,
                'totalScored': round(total_got, 2),
                'totalMax': round(total_max, 2),
                'credit': get_course_credit(ccode, ctitle),
            })

    # Add entries for attendance courses that do not yet have tests
    for a_item in att_data:
        ac = (a_item.get('courseCode') or '').strip().upper()
        if ac and ac not in marked_courses:
            marks_data.append({
                'courseCode': ac,
                'courseTitle': a_item.get('courseTitle', ac),
                'tests': [],
                'totalScored': 0.0,
                'totalMax': 0.0,
                'credit': a_item.get('credit', 0),
            })

    # 6. Parse Profile
    profile = {}
    if isinstance(prof_json, dict):
        raw_prof = prof_json.get('profile') or prof_json.get('studentDetails') or prof_json
        if isinstance(raw_prof, dict):
            profile = {
                'name': raw_prof.get('student_name') or raw_prof.get('studentName') or raw_prof.get('name', ''),
                'reg_no': raw_prof.get('registration_number') or raw_prof.get('registerNo') or raw_prof.get('reg_no', ''),
                'net_id': clean_id,
                'email': f'{clean_id}@srmist.edu.in',
                'program': raw_prof.get('program', ''),
                'department': raw_prof.get('department', ''),
                'semester': str(raw_prof.get('semester', '')),
                'section': raw_prof.get('section', ''),
                'fa_name': raw_prof.get('faculty_advisor', ''),
                'aa_name': raw_prof.get('academic_advisor', ''),
            }

    print(f"[{clean_id}] [CAMPUSWEB] Scraped: {len(att_data)} attendance, {len(marks_data)} marks")
    return {
        'success': True,
        'data': att_data,
        'marks': marks_data,
        'profile': profile,
        'source': 'campusweb_api',
    }
