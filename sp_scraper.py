import time
import requests
import base64
from bs4 import BeautifulSoup

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
        # Use the SAME session (via JSESSIONID cookie) that fetched the captcha
        session = requests.Session()
        session.verify = False
        session.cookies.set('JSESSIONID', jsessionid, domain='sp.srmist.edu.in', path='/')
        
        # --- 1. Login via POST (same session, no new page load) ---
        login_url = "https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp"
        form_data = {
            'username': net_id,
            'password': password,
            'captcha': captcha_text,
            'fpPayload': '',
            'fpToken': ''
        }
        
        r_login = session.post(login_url, data=form_data, verify=False, timeout=15, allow_redirects=True)
        print(f"[SP] Login POST status: {r_login.status_code}, URL: {r_login.url}")
        
        if "HRDSystem" not in r_login.url and "HRDSystem" not in r_login.text:
            # Check for specific error messages
            if "Invalid Captcha" in r_login.text:
                result_data['error'] = "Invalid CAPTCHA. Please try again."
            elif "Invalid credentials" in r_login.text or "invalid" in r_login.text.lower():
                result_data['error'] = "Invalid credentials"
            else:
                result_data['error'] = "Login failed. Please check your NetID, Password, and CAPTCHA."
            return result_data
        
        print("[SP] Login successful!")
        
        # --- 2. Navigate to Attendance page ---
        try:
            att_url = "https://sp.srmist.edu.in/srmiststudentportal/students/template/Aborview.jsp"
            r_att = session.get(att_url, verify=False, timeout=15)
            
            if r_att.status_code == 200:
                soup = BeautifulSoup(r_att.text, 'html.parser')
                tables = soup.find_all('table')
                
                for table in tables:
                    table_html = str(table)
                    if any(kw in table_html for kw in ["Total Class", "Attended", "Percentage", "Max Hours"]):
                        rows = table.find_all('tr')
                        for row in rows[1:]:  # skip header
                            cols = row.find_all('td')
                            if len(cols) >= 6:
                                course_code = cols[0].get_text(strip=True)
                                course_title = cols[1].get_text(strip=True)
                                category = cols[2].get_text(strip=True)
                                max_hours = cols[4].get_text(strip=True)
                                att_hours = cols[5].get_text(strip=True)
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
                                    'absent_hours': str(int(float(max_hours) - float(att_hours))) if max_hours.replace('.','',1).isdigit() and att_hours.replace('.','',1).isdigit() else "0",
                                    'percentage': str(percent)
                                })
                        break
        except Exception as e:
            print(f"[SP] Error fetching attendance: {e}")

        # --- 3. Navigate to Marks page ---
        try:
            marks_url = "https://sp.srmist.edu.in/srmiststudentportal/students/template/MarksView.jsp"
            r_marks = session.get(marks_url, verify=False, timeout=15)
            
            if r_marks.status_code == 200:
                soup = BeautifulSoup(r_marks.text, 'html.parser')
                tables = soup.find_all('table')
                
                for table in tables:
                    table_html = str(table)
                    if any(kw in table_html for kw in ["Mark", "Description", "Max. Mark"]):
                        rows = table.find_all('tr')
                        for row in rows[1:]:  # skip header
                            cols = row.find_all('td')
                            if len(cols) >= 3:
                                code = cols[0].get_text(strip=True)
                                title = cols[1].get_text(strip=True)
                                marks_raw = cols[2].get_text(strip=True)
                                
                                result_data['marks'].append({
                                    'course_code': code,
                                    'course_title': title,
                                    'performance': [{'test_name': 'Total Internal', 'marks': marks_raw}]
                                })
                        break
        except Exception as e:
            print(f"[SP] Error fetching marks: {e}")

        result_data['success'] = True
        return result_data
            
    except Exception as e:
        result_data['error'] = f"System Error: {str(e)}"
        return result_data
