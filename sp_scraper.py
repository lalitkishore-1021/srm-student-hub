import time
import requests
import base64
import re
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://sp.srmist.edu.in/srmiststudentportal"
LOGIN_PAGE = BASE_URL + "/students/loginManager/youLogin.jsp"
CAPTCHA_URL = BASE_URL + "/SCaptchaServlet"
LOGIN_SERVLET = BASE_URL + "/LoginServlet"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

def _extract(html, key):
    for pattern in [
        key + r"\s*=\s*'([^']+)'",
        key + r'\s*=\s*"([^"]+)"',
        key + r"\s*:\s*'([^']+)'",
        key + r'\s*:\s*"([^"]+)"',
    ]:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    return None

def _parse_secure_config(html_text):
    config = {}
    for key in ["captchaFieldName", "domainFieldName", "randomDelimiter"]:
        val = _extract(html_text, key)
        if val:
            config[key] = val
    return config

def get_sp_captcha():
    """
    Use requests to load login page and CAPTCHA.
    Returns base64 CAPTCHA image + JSESSIONID + form field metadata.
    """
    session = requests.Session()
    session.verify = False
    session.headers.update(HEADERS)
    try:
        r_page = session.get(LOGIN_PAGE, timeout=10)
        jsessionid = session.cookies.get("JSESSIONID", "")
        r_cap = session.get(CAPTCHA_URL + "?ts=" + str(int(time.time()*1000)), timeout=10)
        b64_img = base64.b64encode(r_cap.content).decode("utf-8")
        config = _parse_secure_config(r_page.text)
        
        return {
            "success": True,
            "captcha_b64": b64_img,
            "jsessionid": jsessionid,
            "captcha_field": config.get("captchaFieldName", ""),
            "domain_field": config.get("domainFieldName", ""),
            "delimiter": config.get("randomDelimiter", ""),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def sync_sp_portal(net_id, password, captcha_text, jsessionid,
                   captcha_field="", domain_field="", delimiter=""):
    """
    Login using the pure requests method replicating guardlogin.js exactly.
    - Submits actual captcha_text in 'captcha' input
    - Submits trap_payload in dynamic captchaFieldName
    - Submits domain base64 in dynamic domainFieldName
    """
    result_data = {"attendance": [], "marks": [], "success": False, "error": None}
    try:
        session = requests.Session()
        session.verify = False
        session.headers.update(HEADERS)
        session.cookies.set("JSESSIONID", jsessionid, domain="sp.srmist.edu.in", path="/")

        # Replicate guardlogin.js payload
        time_elapsed_sec = 8
        interact_count = 12
        trap_payload = f"{time_elapsed_sec}{delimiter}{interact_count}"
        
        cptoken_val = base64.b64encode(trap_payload.encode("utf-8")).decode("utf-8")
        dtoken_val = base64.b64encode("sp.srmist.edu.in"[::-1].encode("utf-8")).decode("utf-8")

        form_data = {
            "username": net_id,
            "password": password,
            "captcha": captcha_text,  # Typed captcha goes here
            "fpPayload": "",
            "fpToken": ""
        }
        
        if captcha_field:
            form_data[captcha_field] = cptoken_val
        if domain_field:
            form_data[domain_field] = dtoken_val

        post_headers = {
            "Referer": LOGIN_PAGE,
            "Origin": "https://sp.srmist.edu.in",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        r_login = session.post(LOGIN_SERVLET, data=form_data, timeout=15,
                               allow_redirects=True, headers=post_headers)

        if "HRDSystem" not in r_login.url and "HRDSystem" not in r_login.text:
            if "Invalid captcha" in r_login.text or "Invalid Captcha" in r_login.text:
                result_data["error"] = "Invalid CAPTCHA. Please refresh and try again."
            elif "Invalid credentials" in r_login.text:
                result_data["error"] = "Invalid credentials. Please check your NetID and password."
            else:
                result_data["error"] = "Login failed. Please check your NetID, Password, and CAPTCHA."
            return result_data

        print("[SP] Login successful!")

        try:
            r_att = session.get(BASE_URL + "/students/template/Aborview.jsp", timeout=15)
            if r_att.status_code == 200:
                soup = BeautifulSoup(r_att.text, "html.parser")
                for table in soup.find_all("table"):
                    t_html = str(table)
                    if any(kw in t_html for kw in ["Total Class", "Attended", "Percentage", "Max Hours"]):
                        for row in table.find_all("tr")[1:]:
                            cols = row.find_all("td")
                            if len(cols) >= 6:
                                max_h = cols[4].get_text(strip=True)
                                att_h = cols[5].get_text(strip=True)
                                try:
                                    pct = round(float(att_h) / float(max_h) * 100, 2)
                                except Exception:
                                    pct = 0.0
                                result_data["attendance"].append({
                                    "course_code": cols[0].get_text(strip=True),
                                    "course_title": cols[1].get_text(strip=True),
                                    "category": cols[2].get_text(strip=True),
                                    "max_hours": max_h,
                                    "attended_hours": att_h,
                                    "absent_hours": str(int(float(max_h) - float(att_h))) if max_h.replace(".", "", 1).isdigit() and att_h.replace(".", "", 1).isdigit() else "0",
                                    "percentage": str(pct),
                                })
                        break
        except Exception as e:
            print("[SP] Attendance error: " + str(e))

        try:
            r_marks = session.get(BASE_URL + "/students/template/MarksView.jsp", timeout=15)
            if r_marks.status_code == 200:
                soup = BeautifulSoup(r_marks.text, "html.parser")
                for table in soup.find_all("table"):
                    t_html = str(table)
                    if any(kw in t_html for kw in ["Mark", "Description", "Max. Mark"]):
                        for row in table.find_all("tr")[1:]:
                            cols = row.find_all("td")
                            if len(cols) >= 3:
                                result_data["marks"].append({
                                    "course_code": cols[0].get_text(strip=True),
                                    "course_title": cols[1].get_text(strip=True),
                                    "performance": [{"test_name": "Total Internal", "marks": cols[2].get_text(strip=True)}],
                                })
                        break
        except Exception as e:
            print("[SP] Marks error: " + str(e))

        result_data["success"] = True
        return result_data
    except Exception as e:
        result_data["error"] = "System Error: " + str(e)
        return result_data
