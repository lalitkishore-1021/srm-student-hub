import concurrent.futures
import json
import os
import re
import socket
import urllib3.util.connection as urllib3_cn

# Force IPv4 socket resolution to prevent Cloudflare IPv6 handshake timeouts on Windows/Linux
try:
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
    urllib3_cn.HAS_IPV6 = False
except Exception:
    pass

import requests

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


def _create_session():
    """
    Creates a resilient HTTP session with browser headers and IPv4 enforcement.
    """
    s = requests.Session()
    s.headers.update(CW_HEADERS)
    return s


def scrape_campusweb(netid: str, portal_pwd: str = "", acad_pwd: str = None):
    """
    Scrapes live SRM Student Portal attendance and internal marks via CampusWeb API (campusweb.in).
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

    session = _create_session()
    headers = dict(CW_HEADERS)
    headers['X-Net-ID'] = clean_id.upper()

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
            sp_res = session.post(
                'https://api.campusweb.in/api/student-portal/login',
                headers=headers,
                json={'net_id': clean_id, 'password': cand_pwd},
                timeout=6,
            )
            resp_snippet = (sp_res.text or "").strip()[:150]
            print(f"[{clean_id}] CampusWeb direct Student Portal login attempt: status={sp_res.status_code}, resp={resp_snippet}")
            if sp_res.status_code == 200:
                sp_data = sp_res.json()
                if sp_data.get('status') == 'success' and sp_data.get('session_token'):
                    headers['X-Session-Token'] = sp_data['session_token']
                    headers['X-CSRF-Token'] = 'sp_session=http_only'
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

    if not has_auth or not working_portal_pwd:
        for cand_pwd in cand_acad_pwds:
            try:
                auth_res = session.post(
                    'https://api.campusweb.in/api/auth/login',
                    headers=headers,
                    json={'username': f'{clean_id}@srmist.edu.in', 'password': cand_pwd},
                    timeout=6,
                )
                resp_snippet = (auth_res.text or "").strip()[:150]
                print(f"[{clean_id}] CampusWeb Academia auth attempt: status={auth_res.status_code}, resp={resp_snippet}")
                if auth_res.status_code == 200:
                    auth_data = auth_res.json()
                    if auth_data.get('Status') == 'success':
                        session_token = auth_data.get('sessionToken')
                        cookies_str = auth_data.get('Cookies')
                        if cookies_str:
                            headers['X-CSRF-Token'] = cookies_str
                        if session_token:
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

    att_payloads = [payload_with_pwd] if working_portal_pwd else [payload_no_pwd, payload_with_pwd]

    att_json = {}
    for p in att_payloads:
        try:
            r = session.post(
                'https://api.campusweb.in/api/student-portal/attendance',
                headers=headers,
                json=p,
                timeout=6,
            )
            print(f"[{clean_id}] [CAMPUSWEB] Attendance attempt with {list(p.keys())}: status={r.status_code}, len={len(r.text)}")
            if r.status_code == 200:
                res_j = r.json()
                if res_j.get('attendance') or res_j.get('data'):
                    att_json = res_j
                    break
        except Exception as e:
            print(f"[{clean_id}] CampusWeb att fetch notice: {e}")

    marks_payloads = [payload_with_pwd] if working_portal_pwd else [payload_no_pwd, payload_with_pwd]

    marks_json = {}
    for p in marks_payloads:
        try:
            r = session.post(
                'https://api.campusweb.in/api/student-portal/marks',
                headers=headers,
                json=p,
                timeout=6,
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
        return {'success': False, 'error': 'No academic records found for this account', 'reason': 'empty_data'}

    print(f"[{clean_id}] [CAMPUSWEB] Scraped: {len(att_data)} attendance, {len(marks_data)} marks")
    return {
        'success': True,
        'data': att_data,
        'marks': marks_data,
        'profile': {},
        'source': 'campusweb_api',
    }
