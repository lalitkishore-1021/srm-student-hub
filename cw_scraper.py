import requests

def scrape_campusweb(netid, pwd):
    try:
        # Fetch Attendance
        att_resp = requests.post(
            'https://campusapi.fly.dev/api/student-portal/attendance',
            json={'net_id': netid, 'password': pwd},
            timeout=30
        )
        att_json = att_resp.json()
        
        if att_json.get('status') != 'success':
            return {"success": False, "error": att_json.get('message', 'Invalid Credentials or Academia Down')}
            
        att_data = []
        for item in att_json.get('attendance', []):
            att_data.append({
                "courseTitle": item.get('subjectdesc', ''),
                "courseCode": item.get('subjectcode', ''),
                "category": "THEORY", # Default since API doesn't provide category explicitly
                "conducted": float(item.get('total', 0)),
                "absent": float(item.get('absent', 0)),
                "attended": float(item.get('presentpercentage', 0))
            })
            
        # Fetch Marks
        marks_resp = requests.post(
            'https://campusapi.fly.dev/api/student-portal/marks',
            json={'net_id': netid, 'password': pwd},
            timeout=30
        )
        marks_json = marks_resp.json()
        
        marks_data = []
        if marks_json.get('status') == 'success':
            for item in marks_json.get('testPerformances', []):
                tests = item.get('tests', {})
                internal = tests.get('Internal Marks')
                if internal:
                    got = internal.get('got', 0)
                    total = internal.get('total', 0)
                    perfString = f"Internal/{total} | {got}"
                else:
                    perfString = "Internal/100 | 0"
                    
                marks_data.append({
                    "courseTitle": item.get('courseName', ''),
                    "courseCode": item.get('courseCode', ''),
                    "marks": perfString
                })
                
        return {"success": True, "attendance": att_data, "marks": marks_data}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
