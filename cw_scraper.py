import requests
import cloudscraper

def scrape_campusweb(netid, pwd):
    try:
        # CampusWeb API requires strictly the NetID prefix, not the full email.
        if '@' in netid:
            netid = netid.split('@')[0]
            
        session = cloudscraper.create_scraper()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        })
        
        # 1. Attempt session establishment on campusapi
        try:
            login_res = session.post(
                'https://api.campusweb.in/api/student-portal/login',
                json={'net_id': netid, 'password': pwd},
                timeout=10
            )
            if login_res.status_code != 200:
                try:
                    err_msg = login_res.json().get('message', 'CampusWeb login failed')
                except:
                    err_msg = 'CampusWeb login failed'
                return {"success": False, "error": err_msg}
        except Exception:
            pass

        import concurrent.futures
        
        def fetch_att():
            try:
                res = session.post(
                    'https://api.campusweb.in/api/student-portal/attendance',
                    json={'net_id': netid, 'password': pwd},
                    timeout=12
                )
                if res.status_code == 200:
                    return res.json()
            except Exception:
                pass
            return {}
            
        def fetch_marks():
            try:
                res = session.post(
                    'https://api.campusweb.in/api/student-portal/marks',
                    json={'net_id': netid, 'password': pwd},
                    timeout=12
                )
                if res.status_code == 200:
                    return res.json()
            except Exception:
                pass
            return {}
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_att = executor.submit(fetch_att)
            future_marks = executor.submit(fetch_marks)
            
            att_json = future_att.result()
            marks_json = future_marks.result()
            
        if not att_json or att_json.get('status') != 'success':
            return {"success": False, "error": (att_json or {}).get('message', 'CampusWeb API unavailable')}
            
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
            
            att_data.append({
                "courseTitle": item.get('subjectdesc', ''),
                "courseCode": item.get('subjectcode', ''),
                "category": "THEORY",
                "conducted": float(item.get('total', 0)),
                "absent": float(item.get('absent', 0)),
                "attended": float(item.get('presentpercentage', 0)),
                "credit": credit
            })
        
        marks_data = []
        marked_courses = set()
        
        if marks_json.get('status') == 'success':
            for item in marks_json.get('testPerformances', []):
                ccode = item.get('courseCode', '')
                marked_courses.add(ccode)
                
                tests = item.get('tests', {})
                perf_parts = []
                for test_name, test_data in tests.items():
                    if test_name.lower() in ['internal marks', 'total', 'overall', 'internal']: continue
                    got = test_data.get('got', 0)
                    total = test_data.get('total', 0)
                    if float(total) > 0:
                        perf_parts.append(f"{test_name}/{total} | {got}")
                
                if not perf_parts and 'Internal Marks' in tests:
                    got = tests['Internal Marks'].get('got', 0)
                    total = tests['Internal Marks'].get('total', 0)
                    perf_parts.append(f"Internal/{total} | {got}")
                
                if perf_parts:
                    perfString = "  ".join(perf_parts)
                else:
                    perfString = "Internal/100 | 0"
                    
                credit = 3.0
                for a in att_data:
                    if a.get('courseCode', '').upper() == ccode.upper():
                        credit = a.get('credit', 3.0)
                        break

                marks_data.append({
                    "courseTitle": item.get('courseName', ''),
                    "courseCode": ccode,
                    "marks": perfString,
                    "credit": credit
                })
        
        # Merge missing courses from attendance into marks_data so they show up
        for att in att_data:
            if att["courseCode"] not in marked_courses:
                marks_data.append({
                    "courseTitle": att["courseTitle"],
                    "courseCode": att["courseCode"],
                    "marks": "No tests conducted yet",
                    "credit": att.get("credit", 3.0)
                })
                
        return {"success": True, "attendance": att_data, "marks": marks_data}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
