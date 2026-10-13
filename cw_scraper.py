import re
import cloudscraper
from academia_direct_scraper import calculate_bunk_margin_and_needed

def scrape_campusweb(netid, pwd):
    try:
        # CampusWeb API requires strictly the NetID prefix, not the full email.
        clean_id = (netid or "").strip()
        if '@' in clean_id:
            clean_id = clean_id.split('@')[0].strip()
        pwd = (pwd or "").strip()
            
        session = cloudscraper.create_scraper()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        })
        
        # 1. Establish session on campusweb API
        try:
            login_res = session.post(
                'https://api.campusweb.in/api/student-portal/login',
                json={'net_id': clean_id, 'password': pwd},
                timeout=12
            )
            if login_res.status_code != 200:
                try:
                    err_msg = login_res.json().get('message', 'Student Portal login failed')
                except Exception:
                    err_msg = 'Student Portal login failed'
                return {"success": False, "error": err_msg}
        except Exception as e:
            return {"success": False, "error": f"CampusWeb connection error: {e}"}

        # 2. Sequential fetching of attendance, marks, profile (fast, robust, avoids race conditions)
        att_json = {}
        marks_json = {}
        prof_json = {}

        try:
            r = session.post('https://api.campusweb.in/api/student-portal/attendance', json={'net_id': clean_id, 'password': pwd}, timeout=12)
            if r.status_code == 200:
                att_json = r.json()
        except Exception as e:
            print(f"[{clean_id}] CampusWeb attendance fetch warning: {e}")

        try:
            r = session.post('https://api.campusweb.in/api/student-portal/marks', json={'net_id': clean_id, 'password': pwd}, timeout=12)
            if r.status_code == 200:
                marks_json = r.json()
        except Exception as e:
            print(f"[{clean_id}] CampusWeb marks fetch warning: {e}")

        try:
            r = session.post('https://api.campusweb.in/api/student-portal/profile', json={'net_id': clean_id, 'password': pwd}, timeout=10)
            if r.status_code == 200:
                prof_json = r.json()
        except Exception as e:
            print(f"[{clean_id}] CampusWeb profile fetch warning: {e}")
            
        if not att_json or att_json.get('status') != 'success':
            return {"success": False, "error": (att_json or {}).get('message', 'CampusWeb API unavailable')}
            
        # Parse attendance
        att_data = []
        for item in att_json.get('attendance', []):
            code = (item.get('subjectcode', '') or '').strip().upper()
            title = (item.get('subjectdesc', '') or '').strip().upper()
            credit = 3.0
            if (code.startswith('21MAB') or code.startswith('18MAB') or 'MAB' in code or
                'MATHEMATICS' in title or 'TRANSFORMS' in title or 'BOUNDARY VALUE' in title or
                'CALCULUS' in title or 'LINEAR ALGEBRA' in title or 'PROBABILITY' in title or
                'FOURIER' in title or 'NUMERICAL METHODS' in title or 'DISCRETE' in title or
                'DIFFERENTIAL EQUATIONS' in title):
                credit = 4.0
            elif code.endswith('J'):
                credit = 4.0
            elif code.endswith('P') or code.endswith('L') or 'LAB' in title or 'PRACTICAL' in title:
                credit = 2.0 if code.endswith('P') else 1.5
            elif 'PROJECT' in title or 'SEMINAR' in title or 'CAPSTONE' in title:
                credit = 3.0
            elif ('VALUE ADDED' in title or 'VALUE EDUCATION' in title or 'UNIVERSAL HUMAN VALUES' in title or
                  'UHV' in title or 'SKILL' in title or 'CONSTITUTION' in title or 'APTITUDE' in title):
                credit = 1.0
            
            conducted = int(float(item.get('total', 0)))
            absent = int(float(item.get('absent', 0)))
            present = int(conducted - absent)
            percent = float(item.get('presentpercentage', 0))
            safe_margin, classes_needed, status_badge = calculate_bunk_margin_and_needed(percent, conducted, absent)

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
                "bunk_margin": safe_margin,
                "classes_needed": classes_needed,
                "status_badge": status_badge,
                "classes_per_cycle": 1
            })
        
        # Parse marks
        marks_data = []
        marked_courses = set()
        
        if marks_json.get('status') == 'success':
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
                    
                credit = 3.0
                for a in att_data:
                    if a.get('courseCode', '').upper() == ccode:
                        credit = a.get('credit', 3.0)
                        break

                marks_data.append({
                    "courseTitle": item.get('courseName', ''),
                    "courseCode": ccode,
                    "courseType": item.get('courseType', 'Theory'),
                    "performance": perfString,
                    "Test Performance": perfString,
                    "marks": perfString,
                    "tests": tests_list,
                    "credit": credit
                })
        
        # Merge missing courses from attendance into marks_data so all registered courses are listed
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
                    "credit": att.get("credit", 3.0)
                })
                
        profile_raw = (prof_json or {}).get('profile', {}) if isinstance(prof_json, dict) else {}

        def parse_advisor_str(adv_str):
            if not adv_str or not isinstance(adv_str, str):
                return {"name": "", "email": ""}
            m = re.search(r'\[([^\]]+)\]', adv_str)
            email = m.group(1).strip() if m else ""
            name = re.sub(r'\[.*?\]', '', adv_str).strip()
            name = re.sub(r'\s+', ' ', name)
            return {"name": name, "email": email}

        fa_info = parse_advisor_str(profile_raw.get('faculty_advisor'))
        aa_info = parse_advisor_str(profile_raw.get('academic_advisor'))

        profile_data = {
            "name": (profile_raw.get('student_name') or '').strip(),
            "regNo": (profile_raw.get('registration_number') or '').strip() or clean_id.upper(),
            "course": (profile_raw.get('program') or '').strip() or 'SRM University',
            "semester": (profile_raw.get('semester') or '').strip(),
            "section": (profile_raw.get('section') or '').strip(),
            "batch": (profile_raw.get('batch') or '').strip(),
            "fa_name": fa_info["name"],
            "fa_email": fa_info["email"],
            "fa_phone": "",
            "aa_name": aa_info["name"],
            "aa_email": aa_info["email"],
            "aa_phone": "",
            "advisor": fa_info["name"] or aa_info["name"]
        }
        return {"success": True, "attendance": att_data, "marks": marks_data, "profile": profile_data}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
