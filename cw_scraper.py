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
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except Exception:
    HAS_CLOUDSCRAPER = False

try:
    from curl_cffi import requests as c_requests
    HAS_CURL_CFFI = True
except Exception:
    HAS_CURL_CFFI = False
    import requests as c_requests

from academia_direct_scraper import calculate_bunk_margin_and_needed, get_course_credit

CW_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Origin': 'https://campusweb.in',
    'Referer': 'https://campusweb.in/',
    'X-Client': 'web',
    'X-Device-Platform': 'Windows',
    'X-Device-Name': 'Chrome',
    'X-Device-Model': 'Chrome 131.0.0.0',
    'X-App-Version': '2026.10.08-sessions.3',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
    'Sec-Fetch-Site': 'same-site',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'Accept-Language': 'en-US,en;q=0.9',
}


def _create_session(preferred='cloudscraper'):
    """
    Creates an HTTP session configured to bypass Cloudflare WAF on datacenter/cloud IPs.
    Primary: cloudscraper (pure Python SSL/TLS engine, highly resilient on Linux/Render).
    Secondary: curl_cffi (browser TLS fingerprint impersonation).
    Fallback: requests.Session with browser headers.
    """
    if preferred == 'cloudscraper' and HAS_CLOUDSCRAPER:
        try:
            return cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        except Exception:
            pass
    if HAS_CURL_CFFI:
        try:
            return c_requests.Session(impersonate='chrome120')
        except Exception:
            pass
    if HAS_CLOUDSCRAPER:
        try:
            return cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        except Exception:
            pass
    import requests
    s = requests.Session()
    s.headers.update(CW_HEADERS)
    return s


def _post_with_fallback(session, alt_session, url, headers, json_payload, timeout=15):
    """
    Executes a POST request with automatic engine fallback if 403 unsupported_client is encountered.
    """
    try:
        r = session.post(url, headers=headers, json=json_payload, timeout=timeout)
        if r.status_code == 403 and alt_session and 'unsupported_client' in r.text:
            print(f"[CAMPUSWEB] Primary session got 403 unsupported_client, trying secondary engine on {url}...")
            return alt_session.post(url, headers=headers, json=json_payload, timeout=timeout)
        return r
    except Exception as e:
        if alt_session:
            print(f"[CAMPUSWEB] Primary session notice ({e}), trying secondary engine on {url}...")
            return alt_session.post(url, headers=headers, json=json_payload, timeout=timeout)
        raise


def scrape_campusweb(netid: str, portal_pwd: str = "", acad_pwd: str = None):
    """
    Scrapes live SRM Student Portal attendance and internal marks via CampusWeb API (campusweb.in).
    Uses browser TLS fingerprint impersonation to bypass Cloudflare WAF on datacenter/cloud IPs.
    Supports authentication via Student Portal credentials, Academia credentials, or both.
    """
    clean_id = (netid or "").strip()
    if '@' in clean_id:
        clean_id = clean_id.split('@')[0].strip().lower()
    else:
        clean_id = clean_id.lower()

    portal_pwd = (portal_pwd or "").strip()
    acad_pwd = (acad_pwd or "").strip()

    if not clean_id or (not portal_pwd and not acad_pwd):
        return {'success': False, 'error': 'Missing credentials for CampusWeb sync', 'reason': 'missing_credentials'}

    session = _create_session('cloudscraper')
    alt_session = _create_session('curl_cffi')
    headers = dict(CW_HEADERS)
    headers['X-Net-ID'] = clean_id

    has_auth = False
    working_portal_pwd = None

    # Step 1: Direct Student Portal authentication (candidates)
    cand_portal_pwds = []
    if portal_pwd:
        cand_portal_pwds.append(portal_pwd)
    if acad_pwd and acad_pwd not in cand_portal_pwds:
        cand_portal_pwds.append(acad_pwd)

    for cand_pwd in cand_portal_pwds:
        try:
            sp_res = _post_with_fallback(
                session, alt_session,
                'https://api.campusweb.in/api/student-portal/login',
                headers=headers,
                json_payload={'net_id': clean_id, 'password': cand_pwd},
                timeout=12,
            )
            print(f"[{clean_id}] CampusWeb direct Student Portal login attempt: status={sp_res.status_code}")
            if sp_res.status_code == 200:
                sp_data = sp_res.json()
                if sp_data.get('status') == 'success' and sp_data.get('session_token'):
                    headers['X-Session-Token'] = sp_data['session_token']
                    has_auth = True
                    working_portal_pwd = cand_pwd
                    print(f"[{clean_id}] CampusWeb direct Student Portal login succeeded!")
                    break
            elif sp_res.status_code == 429:
                print(f"[{clean_id}] CampusWeb direct portal login rate limited, falling back to Academia auth...")
        except Exception as e:
            print(f"[{clean_id}] CampusWeb direct portal login notice: {e}")

    # Step 2: Academia authentication via /api/auth/login
    cand_acad_pwds = []
    if acad_pwd:
        cand_acad_pwds.append(acad_pwd)
    if portal_pwd and portal_pwd not in cand_acad_pwds:
        cand_acad_pwds.append(portal_pwd)

    for cand_pwd in cand_acad_pwds:
        try:
            auth_res = _post_with_fallback(
                session, alt_session,
                'https://api.campusweb.in/api/auth/login',
                headers=headers,
                json_payload={'username': f'{clean_id}@srmist.edu.in', 'password': cand_pwd},
                timeout=12,
            )
            print(f"[{clean_id}] CampusWeb Academia auth attempt: status={auth_res.status_code}")
            if auth_res.status_code == 200:
                auth_data = auth_res.json()
                if auth_data.get('Status') == 'success':
                    session_token = auth_data.get('sessionToken')
                    cookies_str = auth_data.get('Cookies')
                    if cookies_str:
                        headers['X-CSRF-Token'] = cookies_str
                    if session_token:
                        if not headers.get('X-Session-Token'):
                            headers['X-Session-Token'] = session_token
                        has_auth = True
                    print(f"[{clean_id}] CampusWeb Academia auth succeeded!")
                    break
        except Exception as ae:
            print(f"[{clean_id}] CampusWeb Academia auth notice: {ae}")

    if not has_auth:
        return {
            'success': False,
            'error': 'Invalid NetID or password. You can reset your password at https://ssp.srmist.edu.in/resetpassword/',
            'reason': 'invalid_credentials'
        }

    # Step 3: Fetch Attendance & Marks sequentially (robust payload fallback)
    payload_with_pwd = {'net_id': clean_id, 'password': working_portal_pwd or portal_pwd or acad_pwd}
    payload_no_pwd = {'net_id': clean_id}

    att_payloads = [payload_no_pwd]
    if working_portal_pwd:
        att_payloads.insert(0, payload_with_pwd)
    elif portal_pwd:
        att_payloads.append(payload_with_pwd)

    att_json = {}
    for p in att_payloads:
        try:
            r = _post_with_fallback(
                session, alt_session,
                'https://api.campusweb.in/api/student-portal/attendance',
                headers=headers,
                json_payload=p,
                timeout=15,
            )
            print(f"[{clean_id}] [CAMPUSWEB] Attendance attempt with {list(p.keys())}: status={r.status_code}, len={len(r.text)}")
            if r.status_code == 200:
                res_j = r.json()
                if res_j.get('attendance') or res_j.get('data'):
                    att_json = res_j
                    break
        except Exception as e:
            print(f"[{clean_id}] CampusWeb att fetch notice: {e}")

    marks_payloads = [payload_no_pwd]
    if working_portal_pwd:
        marks_payloads.insert(0, payload_with_pwd)
    elif portal_pwd:
        marks_payloads.append(payload_with_pwd)

    marks_json = {}
    for p in marks_payloads:
        try:
            r = _post_with_fallback(
                session, alt_session,
                'https://api.campusweb.in/api/student-portal/marks',
                headers=headers,
                json_payload=p,
                timeout=15,
            )
            print(f"[{clean_id}] [CAMPUSWEB] Marks attempt with {list(p.keys())}: status={r.status_code}, len={len(r.text)}")
            if r.status_code == 200:
                res_j = r.json()
                if res_j.get('testPerformances') or res_j.get('status') == 'success':
                    marks_json = res_j
                    break
        except Exception as e:
            print(f"[{clean_id}] CampusWeb marks fetch notice: {e}")

    raw_att_list = []
    if isinstance(att_json, dict):
        raw_att_list = att_json.get('attendance') or att_json.get('data') or []

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

    if not att_data and not marks_data:
        return {'success': False, 'error': 'No academic records returned from Student Portal', 'reason': 'empty_data'}

    print(f"[{clean_id}] [CAMPUSWEB] Scraped: {len(att_data)} attendance, {len(marks_data)} marks")
    return {
        'success': True,
        'data': att_data,
        'marks': marks_data,
        'profile': {},
        'source': 'campusweb_api',
    }
