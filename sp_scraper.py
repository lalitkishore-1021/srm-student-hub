import time
import requests
import base64
from playwright.sync_api import sync_playwright

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_sp_captcha():
    session = requests.Session()
    session.verify = False
    try:
        session.get("https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp", verify=False, timeout=10)
        r_cap = session.get("https://sp.srmist.edu.in/srmiststudentportal/SCaptchaServlet", verify=False, timeout=10)
        
        b64_img = base64.b64encode(r_cap.content).decode('utf-8')
        jsessionid = session.cookies.get('JSESSIONID', '')
        
        return {
            'success': True,
            'captcha_b64': b64_img,
            'jsessionid': jsessionid
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def sync_sp_portal(net_id, password, captcha_text, jsessionid):
    result_data = {
        'attendance': [],
        'marks': [],
        'success': False,
        'error': None
    }
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(ignore_https_errors=True, viewport={'width': 1280, 'height': 800})
            
            context.add_cookies([{
                'name': 'JSESSIONID',
                'value': jsessionid,
                'domain': 'sp.srmist.edu.in',
                'path': '/'
            }])
            
            page = context.new_page()
            
            # --- 1. Login ---
            page.goto("https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp")
            page.wait_for_selector("input#username", timeout=10000)
            
            page.fill("input#username", net_id)
            page.fill("input#password", password)
            page.fill("input#captcha", captcha_text)
            page.click("button#btnLogin")
            
            try:
                page.wait_for_url("**/HRDSystem.jsp*", timeout=8000)
                print("[SP] Login successful!")
            except Exception:
                err = "Invalid NetID, Password, or CAPTCHA."
                try:
                    alert = page.locator(".alert").first.inner_text(timeout=2000)
                    if alert: err = alert.strip()
                except:
                    pass
                result_data['error'] = err
                browser.close()
                return result_data
                
            page.wait_for_timeout(2000)

            # --- 2. Extract Attendance ---
            try:
                page.click("text='Attendance Details'")
                page.wait_for_timeout(2000)
                
                att_tables = page.query_selector_all("table")
                for table in att_tables:
                    html = table.inner_html()
                    if "Total Class" in html or "Attended" in html or "Percentage" in html:
                        rows = table.query_selector_all("tbody tr")
                        for row in rows:
                            cols = row.query_selector_all("td")
                            if len(cols) >= 6:
                                course_code = cols[0].inner_text().strip()
                                course_title = cols[1].inner_text().strip()
                                category = cols[2].inner_text().strip()
                                max_hours = cols[4].inner_text().strip()
                                att_hours = cols[5].inner_text().strip()
                                try:
                                    percent = round((float(att_hours) / float(max_hours)) * 100, 2)
                                except:
                                    percent = 0.0
                                    
                                result_data['attendance'].append({
                                    'course_code': course_code,
                                    'course_title': course_title,
                                    'category': category,
                                    'max_hours': max_hours,
                                    'attended_hours': att_hours,
                                    'absent_hours': str(int(float(max_hours) - float(att_hours))) if max_hours.isdigit() and att_hours.isdigit() else "0",
                                    'percentage': str(percent)
                                })
                        break
            except Exception as e:
                print(f"[SP] Error fetching attendance: {e}")

            # --- 3. Extract Marks ---
            try:
                page.click("text='Internal Mark Details'")
                page.wait_for_timeout(2000)
                
                mark_tables = page.query_selector_all("table")
                for table in mark_tables:
                    html = table.inner_html()
                    if "Mark / Max. Mark" in html or "Description" in html:
                        rows = table.query_selector_all("tbody tr")
                        for row in rows:
                            cols = row.query_selector_all("td")
                            if len(cols) >= 3:
                                code = cols[0].inner_text().strip()
                                title = cols[1].inner_text().strip()
                                marks_raw = cols[2].inner_text().strip()
                                
                                result_data['marks'].append({
                                    'course_code': code,
                                    'course_title': title,
                                    'performance': [{'test_name': 'Total Internal', 'marks': marks_raw}]
                                })
                        break
            except Exception as e:
                print(f"[SP] Error fetching marks: {e}")

            result_data['success'] = True
            browser.close()
            return result_data
            
    except Exception as e:
        result_data['error'] = f"System Error: {str(e)}"
        return result_data
