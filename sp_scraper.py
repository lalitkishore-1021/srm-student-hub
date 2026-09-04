import time
import base64
import threading
import uuid
from playwright.sync_api import sync_playwright

BASE_URL = "https://sp.srmist.edu.in/srmiststudentportal"
LOGIN_PAGE = BASE_URL + "/students/loginManager/youLogin.jsp"

ACTIVE_SESSIONS = {}

def sp_worker(session_id, data_dict):
    """Background thread: opens a real Chromium browser, loads login page,
    extracts CAPTCHA, waits for user input, fills & submits, scrapes data."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-dev-shm-usage', 
                    '--disable-gpu',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            # Add stealth scripts to bypass secure2.js telemetry
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            """)

            # 1. Navigate to login
            page.goto(LOGIN_PAGE, wait_until="networkidle")
            time.sleep(1)  # Let guardlogin.js fully initialize

            # 2. Extract CAPTCHA image (the SVG rendered by guardlogin.js)
            cap_elem = page.locator("#secure_captcha")
            cap_elem.wait_for(state="visible", timeout=15000)

            # Screenshot the CAPTCHA element directly
            # This avoids making a duplicate request that invalidates the session
            img_bytes = cap_elem.screenshot(type='png')
            captcha_b64 = base64.b64encode(img_bytes).decode('utf-8')

            # Signal ready
            data_dict['captcha_b64'] = captcha_b64
            data_dict['ready_event'].set()

            # 3. Wait for user credentials (up to 120 seconds)
            if not data_dict['submit_event'].wait(timeout=120):
                print("[SP] Session timed out waiting for user input")
                browser.close()
                return

            # 4. Fill the form fields realistically to trigger keydown events
            page.click("input[name='username']")
            page.keyboard.type(data_dict['username'], delay=50)
            
            page.click("input[name='password']")
            page.keyboard.type(data_dict['password'], delay=50)
            
            page.click("input[name='captcha']")
            page.keyboard.type(data_dict['captcha'], delay=50)

            # Simulate minimal human interaction (guardlogin.js tracks this)
            page.mouse.move(200, 300)
            page.mouse.move(400, 400)
            time.sleep(0.3)

            # 5. Click login - guardlogin.js will inject the hidden fields
            print("[SP] Clicking login button...")
            try:
                with page.expect_navigation(timeout=30000):
                    page.click("#btnLogin")
            except Exception as nav_err:
                data_dict['result'] = {
                    "success": False,
                    "attendance": [],
                    "marks": [],
                    "error": f"Login navigation error: {str(nav_err)}"
                }
                data_dict['done_event'].set()
                browser.close()
                return

            # 6. Check login result
            content = page.content()
            current_url = page.url

            if "HRDSystem" not in content and "HRDSystem" not in current_url:
                # Login failed
                if "Invalid captcha" in content or "Invalid Captcha" in content:
                    error_msg = "Invalid CAPTCHA. Please refresh and try again."
                elif "Invalid credentials" in content:
                    error_msg = "Invalid credentials. Please check your NetID and Password."
                else:
                    error_msg = "Login failed. Please check your credentials and CAPTCHA."
                data_dict['result'] = {
                    "success": False, "attendance": [], "marks": [],
                    "error": error_msg
                }
                data_dict['done_event'].set()
                browser.close()
                return

            # 7. Login successful! Scrape attendance & marks
            print("[SP] Login successful! Scraping data...")

            from bs4 import BeautifulSoup

            attendance_data = []
            marks_data = []

            # Get CSRF token from the logged-in page
            soup_main = BeautifulSoup(content, "html.parser")
            salt_el = soup_main.find("input", id="csrfPreventionSalt")
            salt_val = salt_el.get("value", "") if salt_el else ""
            details_el = soup_main.find("input", id="hdnFormDetails")
            details_val = details_el.get("value", "1") if details_el else "1"

            # Fetch attendance
            try:
                ATT_URL = BASE_URL + "/students/report/studentAttendanceDetails.jsp"
                page.goto(ATT_URL, wait_until="networkidle")
                time.sleep(1)
                att_html = page.content()
                soup_att = BeautifulSoup(att_html, "html.parser")
                tables = soup_att.find_all("table")
                if tables:
                    for row in tables[0].find_all("tr")[1:]:
                        cols = [td.get_text(" ", strip=True) for td in row.find_all(["th", "td"])]
                        if len(cols) >= 6:
                            code = cols[0]
                            desc = cols[1]
                            max_h = cols[2]
                            att_h = cols[3]
                            abs_h = cols[4]
                            pct = cols[5]
                            try:
                                pct_float = float(pct.replace('%', '').strip())
                                color = "green" if pct_float >= 75 else "red"
                            except:
                                pct_float = 0
                                color = "green"
                            attendance_data.append({
                                "courseCode": code,
                                "course_code": code,
                                "courseTitle": desc,
                                "course_title": desc,
                                "category": "Theory",
                                "facultyName": "",
                                "maxHours": max_h,
                                "max_hours": max_h,
                                "attendedHours": att_h,
                                "attended_hours": att_h,
                                "absentHours": abs_h,
                                "absent_hours": abs_h,
                                "attendancePercentage": pct.replace('%', '').strip(),
                                "attendance_percentage": pct.replace('%', '').strip(),
                                "color": color
                            })
            except Exception as e:
                print(f"[SP] Attendance scrape error: {e}")

            # Fetch marks
            try:
                MARKS_URL = BASE_URL + "/students/report/studentInternalMarkDetails.jsp"
                page.goto(MARKS_URL, wait_until="networkidle")
                time.sleep(1)
                marks_html = page.content()
                soup_m = BeautifulSoup(marks_html, "html.parser")
                tables_m = soup_m.find_all("table")
                if tables_m:
                    for row in tables_m[0].find_all("tr")[1:]:
                        cols = [td.get_text(" ", strip=True) for td in row.find_all(["th", "td"])]
                        if len(cols) >= 3:
                            code = cols[0]
                            desc = cols[1]
                            mark_str = cols[2]
                            marks_data.append({
                                "courseTitle": desc,
                                "course_title": desc,
                                "courseCode": code,
                                "course_code": code,
                                "marks": mark_str,
                                "performance": [{"test_name": "Internal", "marks": mark_str}]
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
        import traceback
        traceback.print_exc()
        data_dict['result'] = {
            "success": False, "attendance": [], "marks": [],
            "error": str(e)
        }
        if 'ready_event' in data_dict:
            data_dict['ready_event'].set()
        if 'done_event' in data_dict:
            data_dict['done_event'].set()


def get_sp_captcha():
    """Start a Playwright browser session, fetch the CAPTCHA, return it."""
    # Cleanup old sessions
    now = time.time()
    for k in list(ACTIVE_SESSIONS.keys()):
        if now - ACTIVE_SESSIONS[k]['time'] > 300:
            try:
                ACTIVE_SESSIONS[k]['data']['submit_event'].set()
            except:
                pass
            del ACTIVE_SESSIONS[k]

    session_id = str(uuid.uuid4())
    data_dict = {
        'ready_event': threading.Event(),
        'submit_event': threading.Event(),
        'done_event': threading.Event(),
        'result': None
    }

    t = threading.Thread(target=sp_worker, args=(session_id, data_dict), daemon=True)
    t.start()

    # Wait for CAPTCHA to be extracted
    if not data_dict['ready_event'].wait(timeout=25):
        return {"success": False, "error": "Timeout fetching CAPTCHA from Student Portal."}

    if data_dict.get('result') and not data_dict['result'].get('success', True):
        return data_dict['result']

    ACTIVE_SESSIONS[session_id] = {'time': time.time(), 'data': data_dict}

    return {
        "success": True,
        "captcha_b64": data_dict['captcha_b64'],
        "jsessionid": session_id,
        "captcha_field": "",
        "domain_field": "",
        "delimiter": "",
        "ph_name": ""
    }


def sync_sp_portal(net_id, password, captcha_text, jsessionid, *args, **kwargs):
    """Send credentials to the waiting Playwright browser and get the scraped data."""
    session_info = ACTIVE_SESSIONS.get(jsessionid)
    if not session_info:
        return {
            "success": False, "attendance": [], "marks": [],
            "error": "Session expired or invalid. Please refresh the page and try again."
        }

    data_dict = session_info['data']
    data_dict['username'] = net_id
    data_dict['password'] = password
    data_dict['captcha'] = captcha_text

    # Signal the worker thread to proceed with login
    data_dict['submit_event'].set()

    # Wait for the worker to finish scraping
    if not data_dict['done_event'].wait(timeout=90):
        try:
            del ACTIVE_SESSIONS[jsessionid]
        except:
            pass
        return {
            "success": False, "attendance": [], "marks": [],
            "error": "Timeout during login. The Student Portal may be slow. Please try again."
        }

    try:
        del ACTIVE_SESSIONS[jsessionid]
    except:
        pass

    return data_dict.get('result', {
        "success": False, "attendance": [], "marks": [],
        "error": "Unknown error occurred."
    })
