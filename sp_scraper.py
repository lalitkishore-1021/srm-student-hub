import requests
from bs4 import BeautifulSoup
import re
import json
import uuid
from datetime import datetime, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SP_BASE = "https://sp.srmist.edu.in/srmiststudentportal"

# In-memory session storage mapped by tempId or sessionId
# Each entry: {'session': requests.Session(), 'expires_at': datetime}
live_sessions = {}

def cleanup_sessions():
    now = datetime.now()
    expired = [k for k, v in live_sessions.items() if v['expires_at'] < now]
    for k in expired:
        del live_sessions[k]

def get_captcha():
    cleanup_sessions()
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*"
    })
    
    # 1. Hit HRDSystem to initialize cookies and get redirect to youLogin.jsp
    session.get(f"{SP_BASE}/students/template/HRDSystem.jsp", verify=False)
    
    # 2. Hit youLogin.jsp to get the captcha image URL
    res = session.get(f"{SP_BASE}/students/loginManager/youLogin.jsp", verify=False)
    soup = BeautifulSoup(res.text, "html.parser")
    captcha_img = soup.select_one("img[src*='SCaptchaServlet'], img[src*='captcha']")
    
    if not captcha_img:
        raise Exception("Captcha image not found in login page.")
        
    captcha_src = captcha_img['src']
    if not captcha_src.startswith("http"):
        captcha_src = f"{SP_BASE}/students/loginManager/" + captcha_src.lstrip("/")
        
    # 3. Fetch the captcha image
    img_res = session.get(captcha_src, verify=False)
    import base64
    b64_img = base64.b64encode(img_res.content).decode('utf-8')
    content_type = img_res.headers.get("content-type", "image/png")
    
    temp_id = str(uuid.uuid4())
    live_sessions[temp_id] = {
        'session': session,
        'expires_at': datetime.now() + timedelta(minutes=10)
    }
    
    return {
        'captchaImage': f"data:{content_type};base64,{b64_img}",
        'tempId': temp_id
    }

def sp_login(username, password, captcha, temp_id):
    if temp_id not in live_sessions:
        raise Exception("Session expired. Please reload the captcha.")
        
    session = live_sessions[temp_id]['session']
    
    # Post to LoginServlet
    payload = {
        "username": username,
        "password": password,
        "captcha": captcha,
        "fpPayload": "",
        "fpToken": "",
        "recaptchaToken": ""
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"{SP_BASE}/students/loginManager/youLogin.jsp",
        "Origin": "https://sp.srmist.edu.in"
    }
    
    res = session.post(f"{SP_BASE}/LoginServlet", data=payload, headers=headers, verify=False, allow_redirects=False)
    
    # It should redirect on success
    if res.status_code == 302 or (res.headers.get("Location") and "HRDSystem" in res.headers.get("Location")):
        pass
    else:
        soup = BeautifulSoup(res.text, "html.parser")
        err = soup.select_one(".alert, .error, #error")
        err_msg = err.text.strip() if err else "Login failed - Check credentials or captcha"
        raise Exception(err_msg)
        
    # Fetch profile
    profile_res = session.post(
        f"{SP_BASE}/students/template/studentProfile.jsp",
        data="iden=1&hdnPageAction=0",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=False
    )
    
    soup = BeautifulSoup(profile_res.text, "html.parser")
    profile = {}
    for row in soup.select("table tr"):
        cells = row.select("td")
        if len(cells) >= 2:
            label = cells[0].text.strip()
            val = cells[1].text.strip()
            if "Name" in label: profile['name'] = val
            if "Register No" in label: profile['regNo'] = val
            if "Batch" in label: profile['batch'] = val
            if "Program" in label: profile['course'] = val
            if "Section" in label: profile['section'] = val
            
    session_id = str(uuid.uuid4())
    live_sessions[session_id] = {
        'session': session,
        'profile': profile,
        'expires_at': datetime.now() + timedelta(hours=24)
    }
    
    del live_sessions[temp_id]
    
    return {
        'token': session_id,
        'profile': profile
    }

def get_all_data(session_id):
    if session_id not in live_sessions:
        raise Exception("Session expired. Please log in again.")
        
    session = live_sessions[session_id]['session']
    profile = live_sessions[session_id]['profile']
    
    # 1. Fetch Attendance
    att_res = session.post(
        f"{SP_BASE}/students/report/studentAttendanceDetails.jsp",
        data="iden=9&filter=&hdnFormDetails=1&csrfPreventionSalt=",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=False
    )
    soup = BeautifulSoup(att_res.text, "html.parser")
    subjects = []
    for row in soup.select("table tbody tr"):
        cells = row.select("td")
        if len(cells) >= 3:
            code = cells[0].text.strip()
            title = cells[1].text.strip()
            try:
                pct = float(cells[2].text.strip())
                subjects.append({
                    "code": code,
                    "title": title,
                    "attendancePercent": pct
                })
            except:
                pass
                
    # 2. Fetch Marks
    marks = []
    try:
        marks_res = session.post(
            f"{SP_BASE}/students/report/studentMarksDetails.jsp",
            data="iden=10&filter=&hdnFormDetails=1&csrfPreventionSalt=",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=False
        )
        m_soup = BeautifulSoup(marks_res.text, "html.parser")
        for row in m_soup.select("table tbody tr"):
            cells = row.select("td")
            if len(cells) >= 2:
                code = cells[0].text.strip()
                if code and len(code) >= 6:
                    marks.append({"code": code, "type": "Theory", "tests": []})
    except Exception as e:
        print("Marks error:", e)
        
    overall = sum([s['attendancePercent'] for s in subjects]) / len(subjects) if subjects else 0
    
    return {
        "profile": profile,
        "subjects": subjects,
        "marks": marks,
        "overallAttendance": overall
    }
