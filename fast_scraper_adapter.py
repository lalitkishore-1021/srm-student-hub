import json
import traceback

# Import the logic from the open-source repo
from studentinfo_scrap import AcademiaClient
from tools.retry_fetch_failed_login import fetch_all_data_with_retry
from tools.fallback_mock_attendance_data import generate_mock_attendance_from_timetable

import re

BATCH_TIMETABLES = {
    "1": {
        "time_slots": [
            "08:00 - 08:50", "08:50 - 09:40", "09:45 - 10:35", "10:40 - 11:30",
            "11:35 - 12:25", "12:25 - 01:25", "01:25 - 02:15", "02:20 - 03:10",
            "03:15 - 04:05", "04:05 - 04:55", "04:55 - 05:45", "05:45 - 06:30"
        ],
        "schedule": {
            "1": ["A", "A / X", "F / X", "F", "G", "LUNCH", "P6", "P7", "P8", "P9", "P10", "L11", "L12"],
            "2": ["P11", "P12/X", "P13/X", "P14", "P15", "LUNCH", "B", "B", "G", "G", "A", "L21", "L22"],
            "3": ["C", "C / X", "A / X", "D", "B", "LUNCH", "P26", "P27", "P28", "P29", "P30", "L31", "L32"],
            "4": ["P31", "P32/X", "P33/X", "P34", "P35", "LUNCH", "D", "D", "B", "E", "C", "L41", "L42"],
            "5": ["E", "E / X", "C / X", "F", "D", "LUNCH", "P46", "P47", "P48", "P49", "P50", "L51", "L52"]
        }
    },
    "2": {
        "time_slots": [
            "08:00 - 08:50", "08:50 - 09:40", "09:45 - 10:35", "10:40 - 11:30",
            "11:35 - 12:25", "12:25 - 01:25", "01:25 - 02:15", "02:20 - 03:10",
            "03:15 - 04:05", "04:05 - 04:55", "04:55 - 05:45", "05:45 - 06:30"
        ],
        "schedule": {
            "1": ["P1", "P2/X", "P3/X", "P4", "P5", "LUNCH", "A", "A", "F", "F", "G", "L11", "L12"],
            "2": ["B", "B / X", "G / X", "G", "A", "LUNCH", "P16", "P17", "P18", "P19", "P20", "L21", "L22"],
            "3": ["P21", "P22/X", "P23/X", "P24", "P25", "LUNCH", "C", "C", "A", "D", "B", "L31", "L32"],
            "4": ["D", "D / X", "B / X", "E", "C", "LUNCH", "P36", "P37", "P38", "P39", "P40", "L41", "L42"],
            "5": ["P41", "P42/X", "P43/X", "P44", "P45", "LUNCH", "E", "E", "C", "F", "D", "L51", "L52"]
        }
    }
}

def detect_student_batch(courses, reported_batch="1"):
    m = re.search(r'[12]', str(reported_batch))
    batch_hint = m.group() if m else "1"
    b1_hits, b2_hits = 0, 0
    for c in courses:
        s_str = str(c.get('slot', '')).upper()
        # Morning labs for Batch 2
        for s in ['P1', 'P2', 'P3', 'P4', 'P5', 'P21', 'P22', 'P23', 'P24', 'P25', 'P41', 'P42', 'P43', 'P44', 'P45']:
            if re.search(r'\b' + s + r'\b', s_str): b2_hits += 1
        # Afternoon labs for Batch 1
        for s in ['P6', 'P7', 'P8', 'P9', 'P10', 'P26', 'P27', 'P28', 'P29', 'P30', 'P46', 'P47', 'P48', 'P49', 'P50']:
            if re.search(r'\b' + s + r'\b', s_str): b1_hits += 1
    if b2_hits > b1_hits: return "2"
    if b1_hits > b2_hits: return "1"
    return batch_hint

def get_course_for_slot(slot, courses):
    if not slot or slot == "LUNCH" or slot == "X":
        return None
    slot_options = [s.strip() for s in slot.split('/')]
    
    for course in courses:
        course_slot = course.get('slot', '').strip().rstrip('-').strip()
        if '-' in course_slot:
            parts = [p.strip() for p in course_slot.split('-') if p.strip()]
            for p in parts:
                if p in slot_options:
                    return {
                        'subject': course.get('course_title', '') + " (" + course.get('course_code', '') + ")",
                        'room': course.get('room_no', 'TBA'),
                        'code': course.get('course_code', ''),
                        'type': course.get('course_type', '')
                    }
        else:
            if course_slot in slot_options:
                return {
                    'subject': course.get('course_title', '') + " (" + course.get('course_code', '') + ")",
                    'room': course.get('room_no', 'TBA'),
                    'code': course.get('course_code', ''),
                    'type': course.get('course_type', '')
                }
    return None

def build_timetable(student_batch, courses):
    actual_batch = detect_student_batch(courses, student_batch)
    batch_data = BATCH_TIMETABLES.get(str(actual_batch), BATCH_TIMETABLES["1"])
    time_slots = batch_data['time_slots']
    schedule = batch_data['schedule']
    
    final_tt = {}
    
    for day in ["1", "2", "3", "4", "5"]:
        final_tt[day] = []
        day_slots = schedule[day]
        for i, slot_code in enumerate(day_slots):
            if i >= len(time_slots) or slot_code == "LUNCH":
                continue
            
            course_info = get_course_for_slot(slot_code, courses)
            if course_info:
                time_range = time_slots[i]
                start_t, end_t = time_range.split(' - ') if ' - ' in time_range else (time_range, '')
                entry = {
                    "time": time_range,
                    "start_time": start_t,
                    "end_time": end_t,
                    "subject": course_info['subject'],
                    "room": course_info['room'],
                    "slot": slot_code,
                    "code": course_info['code'],
                    "type": course_info.get('type', '')
                }
                
                # Merge consecutive periods for the same course and room
                if final_tt[day]:
                    last = final_tt[day][-1]
                    if last.get('code') == entry.get('code') and last.get('room') == entry.get('room'):
                        last['end_time'] = entry['end_time']
                        last['time'] = f"{last['start_time']} - {last['end_time']}"
                        last['slot'] = f"{last['slot']}, {entry['slot']}"
                        continue
                        
                final_tt[day].append(entry)
    return final_tt

def get_course_credit(code, title, timetable_courses=None):
    clean_code = (code or '').upper().strip()
    clean_title = (title or '').upper().strip()
    
    # Check timetable courses first
    if timetable_courses:
        base_code = ''.join(ch for ch in clean_code if ch.isalnum())
        for tc in timetable_courses:
            tc_code = ''.join(ch for ch in str(tc.get('course_code', '')).upper() if ch.isalnum())
            if tc_code and (tc_code == base_code or tc_code.startswith(base_code[:8]) or base_code.startswith(tc_code[:8])):
                cred = tc.get('credit')
                if cred and float(cred) > 0:
                    return float(cred)
            tc_title = str(tc.get('course_title', '')).upper().strip()
            if tc_title and tc_title == clean_title:
                cred = tc.get('credit')
                if cred and float(cred) > 0:
                    return float(cred)

    # Standard SRM University credit heuristics
    clean_code_upper = clean_code.upper()
    clean_title_upper = clean_title.upper()

    # 1. Engineering Mathematics courses are strictly 4.0 credits in SRM
    if (clean_code_upper.startswith('21MAB') or clean_code_upper.startswith('18MAB') or 'MAB' in clean_code_upper or
        'MATHEMATICS' in clean_title_upper or 'TRANSFORMS' in clean_title_upper or 'BOUNDARY VALUE' in clean_title_upper or
        'CALCULUS' in clean_title_upper or 'LINEAR ALGEBRA' in clean_title_upper or 'PROBABILITY' in clean_title_upper or
        'FOURIER' in clean_title_upper or 'NUMERICAL METHODS' in clean_title_upper or 'DISCRETE' in clean_title_upper or
        'DIFFERENTIAL EQUATIONS' in clean_title_upper):
        return 4.0

    # 2. Integrated Theory & Practical courses (ends with J)
    if clean_code_upper.endswith('J'):
        return 4.0
    elif clean_code_upper.endswith('P') or clean_code_upper.endswith('L') or 'LAB' in clean_title_upper or 'PRACTICAL' in clean_title_upper:
        return 2.0 if clean_code_upper.endswith('P') else 1.5
    elif 'PROJECT' in clean_title_upper or 'SEMINAR' in clean_title_upper or 'CAPSTONE' in clean_title_upper:
        return 3.0
    elif ('VALUE ADDED' in clean_title_upper or 'VALUE EDUCATION' in clean_title_upper or 'UNIVERSAL HUMAN VALUES' in clean_title_upper or
          'UHV' in clean_title_upper or 'SKILL' in clean_title_upper or 'CONSTITUTION' in clean_title_upper or 'APTITUDE' in clean_title_upper):
        return 1.0
    elif clean_code_upper.endswith('T') or 'THEORY' in clean_title_upper:
        return 3.0
    return 3.0

def adapt_attendance(attendance_data, timetable_courses=None):
    if not attendance_data:
        return []
        
    courses = attendance_data.get("courses")
    if not courses and isinstance(attendance_data.get("attendance"), dict):
        courses = attendance_data["attendance"].get("courses")
    if not courses:
        return []
    adapted = []
    
    for key, c in courses.items():
        clean_code = key.replace("RegularTheory", "").replace("RegularPractical", "").strip()
        course_title = c.get("course_title", "").strip()
        credit = get_course_credit(clean_code, course_title, timetable_courses)
        
        # Match our expected output format exactly
        adapted.append({
            "courseTitle": course_title,
            "courseCode": clean_code,
            "category": c.get("category", ""),
            "faculty": c.get("faculty_name", ""),
            "slot": c.get("slot", ""),
            "room": c.get("room_no", ""),
            "conducted": c.get("hours_conducted", 0),
            "absent": c.get("hours_absent", 0),
            "attended": c.get("attendance_percentage", 0.0),
            "credit": credit,
            "classes_per_cycle": 1
        })
    return adapted

def adapt_marks(marks_data, courses_data, timetable_courses=None):
    if not marks_data:
        return []
    
    if timetable_courses is None:
        timetable_courses = []
    
    adapted = []
    for key, m in marks_data.items():
        actual_title = key
        
        # Try finding in attendance courses
        for c_key, c_val in courses_data.items():
            base_c_key = ''.join(e for e in c_key.upper() if e.isalnum())
            base_m_key = ''.join(e for e in key.upper() if e.isalnum())
            if base_c_key.startswith(base_m_key[:8]) or base_m_key.startswith(base_c_key[:8]):
                actual_title = c_val.get('course_title', '')
                break
                
        # If still just the course code (meaning attendance was empty), try timetable courses
        if actual_title == key:
            base_m_key = ''.join(e for e in key.upper() if e.isalnum())
            for t_course in timetable_courses:
                t_code = ''.join(e for e in str(t_course.get('course_code', '')).upper() if e.isalnum())
                if t_code and (t_code.startswith(base_m_key[:8]) or base_m_key.startswith(t_code[:8])):
                    actual_title = t_course.get('course_title', actual_title)
                    break
        
        credit = get_course_credit(key, actual_title, timetable_courses)

        tests = m.get("tests", [])
        if tests:
            perf_list = []
            for t in tests:
                perf_list.append(f"{t.get('test_name', '')}/{t.get('max_marks', '')} | {t.get('obtained_marks', '')}")
            perf_string = "   ".join(perf_list)
        else:
            perf_string = "No tests available."
            
        adapted.append({
            "courseTitle": actual_title,
            "performance": perf_string,
            "courseCode": key,
            "credit": credit
        })
    return adapted

def run_fast_scraper(email, password, out_queue):
    clean_email = email.strip()
    if "@" not in clean_email:
        clean_email += "@srmist.edu.in"
    print(f"[{clean_email}] Starting FAST scraper...")
    try:
        client = AcademiaClient(clean_email, password)
        
        lookup = client.lookup_user()
        if not lookup:
            print(f"[{clean_email}] Lookup failed.")
            out_queue.put({'success': False, 'error': 'Wrong NetID/Email or Password. Please check your credentials.'})
            return
            
        login_res = client.login()
        if not login_res.get("success"):
            err_msg = str(login_res.get("message", ""))
            err_type = str(login_res.get("type", ""))
            print(f"[{clean_email}] Academia login failed ({err_type}): {err_msg}")
            out_queue.put({'success': False, 'error': 'Wrong NetID/Email or Password. Please check your credentials.'})
            return
            
        print(f"[{email}] Login successful. Fetching timetable & courses...")
        
        timetable_data = client.get_timetable() or {}
        day_order = client.get_day_order() or 1
        
        student_info = timetable_data.get('student_info', {})
        student_batch = student_info.get('batch', '1')
        courses_list = timetable_data.get('courses', [])
        final_tt = build_timetable(student_batch, courses_list)
        
        advisors = timetable_data.get('advisors', {})
        fa = advisors.get('faculty_advisor', {})
        aa = advisors.get('academic_advisor', {})
        
        clean_net_id = email.split('@')[0].upper()
        profile = {
            "name": student_info.get("name") or clean_net_id,
            "reg_no": student_info.get("registration_number") or clean_net_id,
            "program": student_info.get("program", ""),
            "department": student_info.get("department", ""),
            "semester": student_info.get("semester", ""),
            "batch": student_info.get("batch", ""),
            "fa_name": fa.get("name", ""),
            "fa_email": fa.get("email", ""),
            "fa_phone": fa.get("phone", ""),
            "aa_name": aa.get("name", ""),
            "aa_email": aa.get("email", ""),
            "aa_phone": aa.get("phone", "")
        }
        
        total_classes = sum(len(v) for v in final_tt.values())
        print(f"[{email}] Scraping complete! Courses: {len(courses_list)}, TT classes: {total_classes}")
        
        out_queue.put({
            'success': True,
            'data': [],
            'marks': [],
            'timetable': final_tt,
            'courses': courses_list,
            'profile': profile,
            'day_order': day_order,
            'is_mock_attendance': False,
            'cookie_dump': json.dumps(client.get_session_data())
        })
        
    except Exception as e:
        print(f"[{email}] ERROR: {traceback.format_exc()}")
        out_queue.put({'success': False, 'error': str(e)})

