from playwright.sync_api import sync_playwright
import time
import re

def scrape_campusweb(netid, pwd):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto("https://campusweb.in/", timeout=60000)
            page.wait_for_timeout(2000)
            
            # Fill login
            page.locator('input[type="text"], input[placeholder*="Net ID"]').fill(netid)
            page.wait_for_timeout(500)
            page.locator('input[type="password"], input[placeholder*="Password"]').fill(pwd)
            page.wait_for_timeout(500)
            page.locator('button[type="submit"], button:has-text("Sign In")').click()
            
            page.wait_for_timeout(8000)
            
            # Attendance
            page.goto("https://campusweb.in/student/attendance/", timeout=60000)
            page.wait_for_timeout(6000)
            
            att_data = []
            cards = page.locator('div.rounded-xl, div[class*="theme_box_bg"], main > div > div > div, div.flex.flex-col.gap-4 > div').all_inner_texts()
            
            for card in cards:
                if "Margin" not in card and "%" not in card:
                    continue
                    
                lines = [line.strip() for line in card.split('\\n') if line.strip()]
                if len(lines) >= 2:
                    title = lines[0]
                    course_code = lines[1]
                    
                    full_text = " ".join(lines)
                    
                    present = "0"
                    absent = "0"
                    total = "0"
                    percent = "0"
                    
                    p_match = re.search(r'\\bP\\s*(\\d+(?:\\.\\d+)?)', full_text)
                    if p_match: present = p_match.group(1)
                        
                    a_match = re.search(r'\\bA\\s*(\\d+(?:\\.\\d+)?)', full_text)
                    if a_match: absent = a_match.group(1)
                        
                    t_match = re.search(r'\\bT\\s*(\\d+(?:\\.\\d+)?)', full_text)
                    if t_match: total = t_match.group(1)
                        
                    pct_match = re.search(r'(\\d+(?:\\.\\d+)?)\\s*%', full_text)
                    if pct_match: percent = pct_match.group(1)
                            
                    att_data.append({
                        "courseTitle": title,
                        "courseCode": course_code,
                        "category": course_code.split(" - ")[-1] if " - " in course_code else course_code,
                        "conducted": float(total) if total else 0,
                        "absent": float(absent) if absent else 0,
                        "attended": float(percent) if percent else 0,
                    })
                    
            # Marks
            page.goto("https://campusweb.in/student/marks/", timeout=60000)
            page.wait_for_timeout(6000)
            
            marks_data = []
            m_cards = page.locator('div.rounded-xl, div[class*="theme_box_bg"], main > div > div > div, div.flex.flex-col.gap-4 > div').all_inner_texts()
            
            for card in m_cards:
                if "No Record Found" in card:
                    continue
                    
                lines = [line.strip() for line in card.split('\\n') if line.strip()]
                if len(lines) >= 2:
                    title = lines[0]
                    course_code = lines[1]
                    
                    full_text = " ".join(lines)
                    
                    internal_match = re.search(r'Internal\\s*Marks\\s*(\\d+(?:\\.\\d+)?\\s*/\\s*\\d+(?:\\.\\d+)?)', full_text, re.IGNORECASE)
                    
                    if internal_match:
                        internal = internal_match.group(1)
                        parts = internal.split("/")
                        if len(parts) == 2:
                            obtained = parts[0].strip()
                            max_marks = parts[1].strip()
                            perfString = f"Internal/{max_marks} | {obtained}"
                        else:
                            perfString = f"Internal/100 | {internal}"
                    else:
                        perfString = "Internal/100 | 0"
                    
                    marks_data.append({
                        "courseTitle": title,
                        "courseCode": course_code.split(" - ")[0] if " - " in course_code else course_code,
                        "marks": perfString
                    })
            
            browser.close()
            return {"success": True, "attendance": att_data, "marks": marks_data}
            
        except Exception as e:
            try: browser.close()
            except: pass
            return {"success": False, "error": str(e)}
