import json
import traceback

# Import the logic from the open-source repo
from studentinfo_scrap import AcademiaClient
from tools.retry_fetch_failed_login import fetch_all_data_with_retry
from tools.fallback_mock_attendance_data import generate_mock_attendance_from_timetable

BATCH_TIMETABLES = {
    "1": {
        "time_slots": [
            "08:00 - 08:50", "08:50 - 09:40", "09:45 - 10:35", "10:40 - 11:30",
            "11:35 - 12:25", "12:30 - 01:20", "01:25 - 02:15", "02:20 - 03:10",
            "03:10 - 04:00", "04:00 - 04:50", "04:50 - 05:30", "05:30 - 06:10"
        ],
        "schedule": {
            "1": ["A", "A / X", "F / X", "F", "G", "P6", "P7", "P8", "P9", "P10", "L11", "L12"],
            "2": ["P11", "P12/X", "P13/X", "P14", "P15", "B", "B", "G", "G", "A", "L21", "L22"],
            "3": ["C", "C / X", "A / X", "D", "B", "P26", "P27", "P28", "P29", "P30", "L31", "L32"],
            "4": ["P31", "P32/X", "P33/X", "P34", "P35", "D", "D", "B", "E", "C", "L41", "L42"],
            "5": ["E", "E / X", "C / X", "F", "D", "P46", "P47", "P48", "P49", "P50", "L51", "L52"]
        }
    },
    "2": {
        "time_slots": [
            "08:00 - 08:50", "08:50 - 09:40", "09:45 - 10:35", "10:40 - 11:30",
            "11:35 - 12:25", "12:30 - 01:20", "01:25 - 02:15", "02:20 - 03:10",
            "03:10 - 04:00", "04:00 - 04:50", "04:50 - 05:30", "05:30 - 06:10"
        ],
        "schedule": {
            "1": ["P1", "P2/X", "P3/X", "P4", "P5", "A", "A", "F", "F", "G", "L11", "L12"],
            "2": ["B", "B / X", "G / X", "G", "A", "P16", "P17", "P18", "P19", "P20", "L21", "L22"],
            "3": ["P21", "P22/X", "P23/X", "P24", "P25", "C", "C", "A", "D", "B", "L31", "L32"],
            "4": ["D", "D / X", "B / X", "E", "C", "P36", "P37", "P38", "P39", "P40", "L41", "L42"],
            "5": ["P41", "P42/X", "P43/X", "P44", "P45", "E", "E", "C", "F", "D", "L51", "L52"]
        }
    }
}

def get_course_for_slot(slot, courses):
    slot_options = [s.strip() for s in slot.split('/')]
    
    for course in courses:
        # course['slot'] might be something like "A1-A2" or "A"
        course_slot = course.get('slot', '').strip()
        # Remove trailing hyphens
        course_slot = course_slot.rstrip('-').strip()
        
        if '-' in course_slot:
            parts = [p.strip() for p in course_slot.split('-') if p.strip()]
            for p in parts:
                if p in slot_options:
                    return {
                        'subject': course.get('course_title', '') + " (" + course.get('course_code', '') + ")",
                        'room': course.get('room_no', 'TBA'),
                        'code': course.get('course_code', '')
                    }
        else:
            if course_slot in slot_options:
                return {
                    'subject': course.get('course_title', '') + " (" + course.get('course_code', '') + ")",
                    'room': course.get('room_no', 'TBA'),
                    'code': course.get('course_code', '')
                }
    return None

def build_timetable(student_batch, courses):
    # Fallback to batch 1 if unknown
    if str(student_batch) not in BATCH_TIMETABLES:
        student_batch = "1"
        
    batch_data = BATCH_TIMETABLES[str(student_batch)]
    time_slots = batch_data['time_slots']
    schedule = batch_data['schedule']
    
    final_tt = {}
    
    for day in ["1", "2", "3", "4", "5"]:
        final_tt[day] = []
        day_slots = schedule[day]
        for i, slot_code in enumerate(day_slots):
            if i >= len(time_slots):
                break
            
            course_info = get_course_for_slot(slot_code, courses)
            if course_info:
                final_tt[day].append({
                    "time": time_slots[i],
                    "subject": course_info['subject'],
                    "room": course_info['room'],
                    "slot": slot_code,
                    "code": course_info['code']
                })
    return final_tt

def adapt_attendance(attendance_data):
    if not attendance_data or "courses" not in attendance_data:
        return []
        
    courses = attendance_data["courses"]
    adapted = []
    
    for key, c in courses.items():
        # Match our expected output format exactly
        adapted.append({
            "courseTitle": c.get("course_title", ""),
            "courseCode": key.replace("RegularTheory", "").replace("RegularPractical", ""), # Approximated
            "category": c.get("category", ""),
            "faculty": c.get("faculty_name", ""),
            "slot": c.get("slot", ""),
            "room": c.get("room_no", ""),
            "conducted": c.get("hours_conducted", 0),
            "absent": c.get("hours_absent", 0),
            "attended": c.get("attendance_percentage", 0.0),
            "classes_per_cycle": 1 # Used for target calc in frontend
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
            "courseCode": key
        })
    return adapted

def run_fast_scraper(email, password, out_queue):
    print(f"[{email}] Starting FAST scraper...")
    try:
        client = AcademiaClient(email, password)
        
        lookup = client.lookup_user()
        if not lookup:
            out_queue.put({'success': False, 'error': 'You entered a wrong email ID or password. Please make sure your email ends with @srmist.edu.in'})
            return
            
        login_res = client.login()
        if not login_res.get("success"):
            out_queue.put({'success': False, 'error': 'You entered a wrong email ID or password. Please make sure your email ends with @srmist.edu.in'})
            return
            
        print(f"[{email}] Login successful. Fetching data...")
        
        result = fetch_all_data_with_retry(client, max_retries=2, save_debug_html=False)
        if not result.get("success"):
            out_queue.put({'success': False, 'error': result.get("error", "Failed to fetch data")})
            return
            
        day_order = result.get('day_order', 0)
        attendance_data = result.get('attendance_data')
        timetable_data = result.get('timetable_data')
        
        if attendance_data is None or (isinstance(attendance_data, dict) and attendance_data.get("error")):
            print(f"[{email}] Attendance invalid, using fallback...")
            attendance_data = generate_mock_attendance_from_timetable(timetable_data)
            if attendance_data is None:
                attendance_data = {}
        
        student_info = attendance_data.get('student_info', {}) if attendance_data else {}
        if not student_info and timetable_data:
            student_info = timetable_data.get('student_info', {})
        student_batch = student_info.get('batch', '1')
        
        # Build Day 1-5 Timetable exactly as requested by user
        courses_list = timetable_data.get('courses', []) if timetable_data else []
        final_tt = build_timetable(student_batch, courses_list)
        
        # Adapt to frontend format
        attList = adapt_attendance(attendance_data)
        marksList = adapt_marks(attendance_data.get('marks', {}), attendance_data.get('courses', {}), courses_list)
        
        advisors = timetable_data.get('advisors', {}) if timetable_data else {}
        fa = advisors.get('faculty_advisor', {})
        aa = advisors.get('academic_advisor', {})
        
        profile = {
            "name": student_info.get("name", "Student"),
            "reg_no": student_info.get("registration_number", ""),
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
        
        print(f"[{email}] Scraping complete!")
        
        out_queue.put({
            'success': True,
            'data': attList,
            'marks': marksList,
            'timetable': final_tt,
            'profile': profile,
            'day_order': day_order,
            'cookie_dump': json.dumps(client.get_session_data())
        })
        
    except Exception as e:
        print(f"[{email}] ERROR: {traceback.format_exc()}")
        out_queue.put({'success': False, 'error': str(e)})

