import time
import base64
import threading
import uuid
import re
from playwright.sync_api import sync_playwright
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://sp.srmist.edu.in/srmiststudentportal"
LOGIN_PAGE = BASE_URL + "/students/loginManager/youLogin.jsp"

# ACTIVE_SESSIONS will store dictionaries containing Events and shared data
ACTIVE_SESSIONS = {}

def sp_worker(session_id, stop_event, data_dict):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            # 1. Go to login page
            page.goto(LOGIN_PAGE, wait_until="networkidle")
            
            # 2. Extract CAPTCHA image
            cap_elem = page.locator("#secure_captcha")
            cap_elem.wait_for(state="visible", timeout=10000)
            
            # Wait for data-src to populate
            page.wait_for_function("document.getElementById('secure_captcha').getAttribute('data-src') !== null")
            data_src = cap_elem.get_attribute("data-src")
            
            # Fetch the actual image using Playwright's API context
            img_resp = context.request.get(f"https://sp.srmist.edu.in{data_src}")
            img_bytes = img_resp.body()
            captcha_b64 = base64.b64encode(img_bytes).decode('utf-8')
            
            # Get the session ID
            jsessionid = ""
            for c in context.cookies():
                if c['name'] == 'JSESSIONID':
                    jsessionid = c['value']
            
            # Pass CAPTCHA back to main thread
            data_dict['captcha_b64'] = captcha_b64
            data_dict['jsessionid'] = jsessionid
            data_dict['ready_event'].set()
            
            # 3. Wait for user to submit credentials (up to 120 seconds)
            submitted = data_dict['submit_event'].wait(timeout=120)
            if not submitted:
                browser.close()
                return
                
            # 4. Fill form
            page.fill("input[name='username']", data_dict['username'])
            page.fill("input[name='password']", data_dict['password'])
            page.fill("input[name='captcha']", data_dict['captcha'])
            
            # Click login and wait for navigation
            with page.expect_navigation(timeout=30000):
                page.click("button#btnLogin")
                
            # Check if login failed
            if "youLogin.jsp" in page.url or "Invalid captcha" in page.content():
                data_dict['result'] = {"success": False, "error": "Invalid credentials or CAPTCHA."}
                data_dict['done_event'].set()
                browser.close()
                return
                
            # 5. Success! Navigate to attendance
            print(f"[SP] Login successful! Fetching attendance and marks...")
            page.goto("https://sp.srmist.edu.in/srmiststudentportal/students/template/StudentMain.jsp", wait_until="networkidle")
            
            attendance_data = []
            marks_data = []
            
            try:
                page.wait_for_selector("#divFilterStudentAttendance table", timeout=10000)
                rows = page.locator("#divFilterStudentAttendance table tbody tr").all()
                for row in rows:
                    cols = row.locator("td").all_inner_texts()
                    if len(cols) >= 8:
                        att_pct = cols[7].replace("%", "").strip()
                        attendance_data.append({
                            "courseCode": cols[0].strip(),
                            "courseTitle": cols[1].strip(),
                            "category": cols[2].strip(),
                            "facultyName": cols[3].strip(),
                            "maxHours": cols[5].strip(),
                            "attendedHours": cols[6].strip(),
                            "attendancePercentage": att_pct,
                            "color": "green" if float(att_pct) >= 75 else "red"
                        })
            except Exception as e:
                print(f"[SP] Attendance scrape error: {e}")
                
            try:
                # Click marks tab
                page.click("a#studentMarkTab")
                page.wait_for_selector("#markTab table", timeout=10000)
                rows = page.locator("#markTab table tbody tr").all()
                for row in rows:
                    cols = row.locator("td").all_inner_texts()
                    if len(cols) >= 5:
                        marks_data.append({
                            "courseCode": cols[0].strip(),
                            "courseTitle": cols[1].strip(),
                            "testName": cols[2].strip(),
                            "maxMarks": cols[3].strip(),
                            "scoredMarks": cols[4].strip()
                        })
            except Exception as e:
                print(f"[SP] Marks scrape error: {e}")

            data_dict['result'] = {
                "success": True,
                "attendance": attendance_data,
                "marks": marks_data
            }
            data_dict['done_event'].set()
            browser.close()
            
    except Exception as e:
        print(f"[SP] Playwright worker error: {e}")
        data_dict['result'] = {"success": False, "error": str(e)}
        if 'ready_event' in data_dict:
            data_dict['ready_event'].set()
        if 'done_event' in data_dict:
            data_dict['done_event'].set()

def get_sp_captcha():
    # Cleanup old sessions
    now = time.time()
    for k in list(ACTIVE_SESSIONS.keys()):
        if now - ACTIVE_SESSIONS[k]['time'] > 300:
            if 'submit_event' in ACTIVE_SESSIONS[k]['data']:
                ACTIVE_SESSIONS[k]['data']['submit_event'].set()
            del ACTIVE_SESSIONS[k]

    session_id = str(uuid.uuid4())
    data_dict = {
        'ready_event': threading.Event(),
        'submit_event': threading.Event(),
        'done_event': threading.Event(),
        'result': None
    }
    
    t = threading.Thread(target=sp_worker, args=(session_id, None, data_dict), daemon=True)
    t.start()
    
    # Wait for CAPTCHA
    if not data_dict['ready_event'].wait(timeout=20):
        return {"success": False, "error": "Timeout fetching CAPTCHA."}
        
    if data_dict.get('result') and not data_dict['result'].get('success'):
        return data_dict['result']
        
    ACTIVE_SESSIONS[session_id] = {'time': time.time(), 'data': data_dict}
    
    return {
        "success": True,
        "captcha_b64": data_dict['captcha_b64'],
        "jsessionid": session_id,  # We use the UUID as the reference now!
        "captcha_field": "",
        "domain_field": "",
        "delimiter": "",
        "ph_name": ""
    }

def sync_sp_portal(net_id, password, captcha_text, jsessionid, *args, **kwargs):
    session_info = ACTIVE_SESSIONS.get(jsessionid)
    if not session_info:
        return {"success": False, "error": "Session expired or invalid. Please refresh the page."}
        
    data_dict = session_info['data']
    data_dict['username'] = net_id
    data_dict['password'] = password
    data_dict['captcha'] = captcha_text
    
    # Signal worker to proceed
    data_dict['submit_event'].set()
    
    # Wait for completion
    if not data_dict['done_event'].wait(timeout=60):
        del ACTIVE_SESSIONS[jsessionid]
        return {"success": False, "error": "Timeout during login and scraping."}
        
    del ACTIVE_SESSIONS[jsessionid]
    return data_dict.get('result', {"success": False, "error": "Unknown error occurred."})
