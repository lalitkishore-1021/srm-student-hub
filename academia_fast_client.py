"""
Academia Direct Fast Client
===========================
Direct HTTP client for academia.srmist.edu.in using Zoho signin.ac endpoint:
- Instant login (~1.6s)
- Fast failure detection on wrong credentials (~1.5s)
- Decodes Zoho HTML to parse:
  * Registered Courses (Code, Title, Credits, Faculty, Slot, Room)
  * Student Profile & Advisors
  * 5-day Timetable mapped from Unified Grid
- Total elapsed time: ~2.5 - 3.5s!
"""

import html
import re
import time
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import requests

SRM_PERIOD_TIMES = [
    {"period": 1, "start": "08:00", "end": "08:50", "time": "08:00 - 08:50"},
    {"period": 2, "start": "08:50", "end": "09:40", "time": "08:50 - 09:40"},
    {"period": 3, "start": "09:45", "end": "10:35", "time": "09:45 - 10:35"},
    {"period": 4, "start": "10:40", "end": "11:30", "time": "10:40 - 11:30"},
    {"period": 5, "start": "11:35", "end": "12:25", "time": "11:35 - 12:25"},
    {"period": 6, "start": "01:25", "end": "02:15", "time": "01:25 - 02:15"},
    {"period": 7, "start": "02:20", "end": "03:10", "time": "02:20 - 03:10"},
    {"period": 8, "start": "03:15", "end": "04:05", "time": "03:15 - 04:05"},
    {"period": 9, "start": "04:05", "end": "04:55", "time": "04:05 - 04:55"},
    {"period": 10, "start": "04:55", "end": "05:45", "time": "04:55 - 05:45"},
]

def clean_text(text: Any) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', str(text)).strip()

def smart_extract_zoho(raw_html: str) -> Optional[str]:
    if not raw_html:
        return None
    m = re.search(r"pageSanitizer\.sanitize\('(.+?)'\)", raw_html)
    if m:
        try:
            return m.group(1).encode('utf-8').decode('unicode_escape').replace(r'\-', '-').replace(r'\/', '/')
        except Exception:
            pass
    soup = BeautifulSoup(raw_html, 'html.parser')
    hidden = soup.find('div', class_='zc-pb-embed-placeholder-content')
    if hidden and hidden.has_attr('zmlvalue'):
        return html.unescape(hidden['zmlvalue']).replace(r'\-', '-').replace(r'\/', '/')
    return None

def fetch_academia_fast(email: str, password: str) -> Dict[str, Any]:
    t0 = time.time()
    clean_user = email.strip()
    if '@' not in clean_user:
        clean_user += '@srmist.edu.in'

    session = requests.Session()
    headers = {
        'Origin': 'https://academia.srmist.edu.in',
        'Referer': 'https://academia.srmist.edu.in/',
        'User-Agent': 'Mozilla/5.0'
    }

    login_url = 'https://academia.srmist.edu.in/accounts/signin.ac'
    payload = {
        'username': clean_user,
        'password': password,
        'client_portal': 'true',
        'portal': '10002227248',
        'servicename': 'ZohoCreator',
        'serviceurl': 'https://academia.srmist.edu.in/',
        'is_ajax': 'true',
        'grant_type': 'password',
        'service_language': 'en'
    }

    try:
        r = session.post(login_url, data=payload, headers=headers, timeout=20)
    except Exception as e:
        return {'success': False, 'error': f'Network error contacting Academia: {str(e)}'}

    try:
        resp_json = r.json()
    except Exception:
        return {'success': False, 'error': 'Academia returned an unexpected response. Please try again.'}

    if resp_json.get('status') == 'fail' or 'error' in resp_json:
        err = resp_json.get('error', {})
        msg = err.get('password') or err.get('msg') or err.get('username') or 'Invalid Academia email or password.'
        return {'success': False, 'error': f'{msg}. Make sure this is your Academia password!'}

    token_data = resp_json.get('data', {})
    token = token_data.get('access_token')
    redirect_url = token_data.get('oauthorize_uri')
    if not token or not redirect_url:
        return {'success': False, 'error': 'Failed to obtain Academia access token.'}

    # Exchange access token for session cookie with allow_redirects=False (instant ~300ms)
    auth_url = f'{redirect_url}&access_token={token}'
    try:
        session.get(auth_url, headers=headers, allow_redirects=False, timeout=20)
    except Exception as e:
        return {'success': False, 'error': f'Academia authorization failed: {str(e)}'}

    print(f"[{clean_user}] Logged into Academia in {time.time()-t0:.2f}s!", flush=True)

    # 1. Fetch My_Time_Table page (Student Profile, Registered Courses, Advisors)
    tt_url = 'https://academia.srmist.edu.in/srm_university/academia-academic-services/page/My_Time_Table_2023_24'
    prof_html = None
    try:
        r_prof = session.get(tt_url, headers=headers, timeout=25)
        prof_html = smart_extract_zoho(r_prof.text)
    except Exception as e:
        print(f"[{clean_user}] Profile fetch error: {e}", flush=True)

    if not prof_html:
        for alt in ['My_Time_Table_2024_25', 'My_Time_Table_2025_26', 'My_Time_Table']:
            try:
                r_alt = session.get(f'https://academia.srmist.edu.in/srm_university/academia-academic-services/page/{alt}', headers=headers, timeout=10)
                prof_html = smart_extract_zoho(r_alt.text)
                if prof_html:
                    break
            except Exception:
                pass

    if not prof_html:
        return {'success': False, 'error': 'Could not extract timetable data from Academia.'}

    soup_p = BeautifulSoup(prof_html, 'html.parser')
    tables = soup_p.find_all('table')

    clean_net_id = clean_user.split('@')[0].upper()
    profile = {
        'name': '',
        'reg_no': clean_net_id,
        'program': '',
        'department': '',
        'semester': '',
        'batch': '1',
        'section': '',
        'fa_name': '',
        'fa_email': '',
        'fa_phone': '',
        'aa_name': '',
        'aa_email': '',
        'aa_phone': ''
    }

    def get_element_by_label(label_text):
        label_node = soup_p.find(string=lambda text: text and label_text.lower() in text.lower())
        if label_node:
            label_td = label_node.find_parent("td")
            if label_td:
                value_td = label_td.find_next_sibling("td")
                if value_td:
                    found = value_td.find("strong") or value_td.find("div")
                    return found if found else value_td
        return None

    el = get_element_by_label("Registration Number") or get_element_by_label("Register No")
    if el: profile["reg_no"] = clean_text(el.get_text())

    el = get_element_by_label("Student Name") or get_element_by_label("Name")
    if el: profile["name"] = clean_text(el.get_text())

    el = get_element_by_label("Program")
    if el: profile["program"] = clean_text(el.get_text())

    el = get_element_by_label("Semester")
    if el: profile["semester"] = clean_text(el.get_text())

    el = get_element_by_label("Combo / Batch") or get_element_by_label("Batch")
    if el:
        val = clean_text(el.get_text())
        m_b = re.search(r'\b([12])\b', val)
        if m_b:
            profile["batch"] = m_b.group(1)

    el = get_element_by_label("Department") or get_element_by_label("Institution")
    if el:
        full = clean_text(el.get_text())
        profile["department"] = full
        font = el.find("font")
        if font:
            sec = clean_text(font.get_text())
            profile["section"] = sec
            profile["department"] = full.replace(sec, "").rstrip("-").strip()

    # Parse Advisors
    for td in soup_p.find_all('td'):
        txt = td.get_text(separator='\n')
        if 'Faculty Advisor' in txt:
            lines = [l.strip() for l in txt.split('\n') if l.strip()]
            for i, l in enumerate(lines):
                if 'Faculty Advisor' in l and i > 0:
                    profile['fa_name'] = lines[i-1]
            em = re.search(r'[\w\.-]+@srmist\.edu\.in', txt)
            if em: profile['fa_email'] = em.group(0)
            ph = re.search(r'\b\d{10}\b', txt)
            if ph: profile['fa_phone'] = ph.group(0)

        if 'Academic Advisor' in txt:
            lines = [l.strip() for l in txt.split('\n') if l.strip()]
            for i, l in enumerate(lines):
                if 'Academic Advisor' in l and i > 0:
                    profile['aa_name'] = lines[i-1]
            em = re.search(r'[\w\.-]+@srmist\.edu\.in', txt)
            if em: profile['aa_email'] = em.group(0)
            ph = re.search(r'\b\d{10}\b', txt)
            if ph: profile['aa_phone'] = ph.group(0)

    # Parse Registered Courses
    course_map = {}
    registered_courses = []
    course_table = None
    for t in tables:
        if "Course Code" in t.get_text():
            course_table = t
            break

    if course_table:
        all_cells = course_table.find_all('td')
        COL_COUNT = 11
        start_index = 0
        for i, cell in enumerate(all_cells):
            txt = clean_text(cell.get_text())
            if txt == "1":
                if i+1 < len(all_cells):
                    next_txt = clean_text(all_cells[i+1].get_text())
                    if re.match(r'^\d+', next_txt) or len(next_txt) > 4:
                        start_index = i
                        break
        curr = start_index
        while curr + 10 < len(all_cells):
            try:
                cols = all_cells[curr: curr + COL_COUNT]
                c_code = clean_text(cols[1].get_text())
                c_name = clean_text(cols[2].get_text())
                c_credits = clean_text(cols[3].get_text())
                c_type_raw = clean_text(cols[6].get_text())
                c_faculty = clean_text(cols[7].get_text())
                c_slot_raw = clean_text(cols[8].get_text())
                c_room = clean_text(cols[9].get_text())

                if not c_code or len(c_code) < 3:
                    curr += COL_COUNT
                    continue
                if "Lab Based" in c_faculty:
                    c_faculty = "Unknown"

                credit_val = float(c_credits) if c_credits and c_credits.replace('.','',1).isdigit() else 3.0
                c_data = {
                    "code": c_code,
                    "course_code": c_code,
                    "title": c_name,
                    "course_title": c_name,
                    "credit": credit_val,
                    "credits": credit_val,
                    "type": c_type_raw,
                    "faculty": c_faculty,
                    "room": c_room,
                    "slot": c_slot_raw
                }
                registered_courses.append(c_data)

                clean_slots = [s.strip() for s in c_slot_raw.replace('-', ' ').replace('/', ' ').replace(',', ' ').replace('+', ' ').split() if s.strip()]
                for s in clean_slots:
                    if s:
                        is_prac = s.upper().startswith('P') or s.upper().startswith('L') or s.upper() == 'LAB'
                        fd = c_data.copy()
                        fd["type"] = "Practical" if is_prac else "Theory"
                        course_map[s] = fd

                curr += COL_COUNT
            except IndexError:
                break

    # 2. Fetch Unified Timetable Grid for student's batch
    batch_num = profile.get("batch", "1")
    if batch_num not in ("1", "2"):
        batch_num = "1"

    grid_url = f"https://academia.srmist.edu.in/srm_university/academia-academic-services/page/Unified_Time_Table_2025_Batch_{batch_num}"
    grid_html = None
    try:
        r_grid = session.get(grid_url, headers=headers, timeout=25)
        grid_html = smart_extract_zoho(r_grid.text)
    except Exception:
        pass

    if not grid_html:
        try:
            grid_url = f"https://academia.srmist.edu.in/srm_university/academia-academic-services/page/Unified_Time_Table_2025_batch_{batch_num}"
            r_grid = session.get(grid_url, headers=headers, timeout=15)
            grid_html = smart_extract_zoho(r_grid.text)
        except Exception:
            pass

    final_tt = {"1": [], "2": [], "3": [], "4": [], "5": []}
    if grid_html and course_map:
        soup_g = BeautifulSoup(grid_html, 'html.parser')
        grid_table = None
        for t in soup_g.find_all('table'):
            txt = t.get_text().lower()
            if "day 1" in txt and ("08:00" in txt or "from" in txt):
                grid_table = t
                break

        if grid_table:
            rows = grid_table.find_all('tr')
            time_headers = []
            for row in rows:
                row_txt = clean_text(row.get_text())
                if 'FROM' in row_txt.upper() or '08:00' in row_txt:
                    cells = row.find_all(['td', 'th'])
                    for c in cells[1:]:
                        t_txt = clean_text(c.get_text())
                        if ':' in t_txt and 'day' not in t_txt.lower():
                            time_headers.append(t_txt)
                    if time_headers:
                        break

            if not time_headers or len(time_headers) < 10:
                time_headers = [
                    "08:00 - 08:50", "08:50 - 09:40", "09:45 - 10:35", "10:40 - 11:30",
                    "11:35 - 12:25", "12:25 - 01:25", "01:25 - 02:15", "02:20 - 03:10",
                    "03:15 - 04:05", "04:05 - 04:55", "04:55 - 05:45", "05:45 - 06:30"
                ]

            for row in rows:
                cols = row.find_all('td')
                if not cols:
                    continue
                day_text = clean_text(cols[0].get_text())
                day_match = re.search(r'Day\s*(\d+)', day_text, re.I)
                if not day_match:
                    continue
                day_num = day_match.group(1)
                if day_num not in final_tt:
                    continue

                for i, cell in enumerate(cols[1:]):
                    if i >= len(time_headers):
                        break
                    raw_slot = clean_text(cell.get_text())
                    slot_code = raw_slot.split('/')[0].strip()
                    if not slot_code or slot_code in ("-", "X", "LUNCH"):
                        continue
                    if slot_code not in course_map:
                        continue

                    details = course_map[slot_code]
                    time_header = time_headers[i]
                    times = [t.strip() for t in time_header.split('-')]
                    t_from = times[0] if len(times) > 0 else ''
                    t_to = times[1] if len(times) > 1 else ''

                    entry = {
                        "time": time_header,
                        "time_from": t_from,
                        "time_to": t_to,
                        "subject": f"{details['title']} ({details['code']})",
                        "code": details['code'],
                        "room": details.get('room', 'TBA'),
                        "faculty": details.get('faculty', ''),
                        "type": details.get('type', 'Theory'),
                        "slot": slot_code,
                        "period": i + 1,
                        "period_end": i + 1
                    }

                    last = final_tt[day_num][-1] if final_tt[day_num] else None
                    if last and last["code"] == entry["code"] and last["room"] == entry["room"] and last["period_end"] + 1 == entry["period"]:
                        last["time"] = f"{last['time_from']} - {entry['time_to']}"
                        last["time_to"] = entry["time_to"]
                        last["period_end"] = entry["period"]
                        last["slot"] = f"{last['slot']}, {entry['slot']}"
                    else:
                        final_tt[day_num].append(entry)

    total_classes = sum(len(v) for v in final_tt.values())
    print(f"[{clean_user}] Timetable extracted: {total_classes} classes across 5 days in {time.time()-t0:.2f}s!", flush=True)

    return {
        'success': True,
        'profile': profile,
        'timetable': final_tt,
        'courses': registered_courses,
        'day_order': 1,
        'elapsed': time.time() - t0
    }
