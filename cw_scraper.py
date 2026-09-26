import requests

def scrape_campusweb(netid, pwd):
    try:
        # CampusWeb API requires strictly the NetID prefix, not the full email.
        if '@' in netid:
            netid = netid.split('@')[0]
            
        import concurrent.futures
        
        def fetch_att():
            return requests.post('https://campusapi.fly.dev/api/student-portal/attendance', json={'net_id': netid, 'password': pwd}, timeout=25).json()
            
        def fetch_marks():
            return requests.post('https://campusapi.fly.dev/api/student-portal/marks', json={'net_id': netid, 'password': pwd}, timeout=25).json()
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_att = executor.submit(fetch_att)
            future_marks = executor.submit(fetch_marks)
            
            att_json = future_att.result()
            marks_json = future_marks.result()
            
        if att_json.get('status') != 'success':
            return {"success": False, "error": att_json.get('message', 'Invalid Credentials or Academia Down')}
            
        att_data = []
        for item in att_json.get('attendance', []):
            code = (item.get('subjectcode', '') or '').strip().upper()
            title = (item.get('subjectdesc', '') or '').strip().upper()
            credit = 3.0
            if code.endswith('J'): credit = 4.0
            elif code.endswith('P') or code.endswith('L') or 'LAB' in title or 'PRACTICAL' in title: credit = 2.0 if code.endswith('P') else 1.5
            elif 'PROJECT' in title or 'SEMINAR' in title: credit = 3.0
            elif 'VALUE' in title or 'SKILL' in title or 'CONSTITUTION' in title: credit = 1.0
            
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
