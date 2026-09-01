import time
import queue
import re
from playwright.sync_api import sync_playwright
import ddddocr

# Initialize ddddocr once
ocr = ddddocr.DdddOcr(show_ad=False)

def sync_sp_portal(net_id, password):
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
            page = context.new_page()
            
            # --- 1. Login ---
            page.goto("https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp")
            
            # Max 3 retries for Captcha
            logged_in = False
            for attempt in range(3):
                # Wait for Captcha image
                page.wait_for_selector("img#secure_captcha", timeout=10000)
                
                # Take screenshot of the captcha element
                captcha_element = page.locator("img#secure_captcha")
                # Add a small delay to ensure the image is fully loaded before screenshotting
                page.wait_for_timeout(500) 
                captcha_bytes = captcha_element.screenshot()
                
                # Solve using ddddocr
                captcha_text = ocr.classification(captcha_bytes)
                print(f"[SP] Attempt {attempt+1}: Solved Captcha as -> {captcha_text}")
                
                # Fill form
                page.fill("input#username", net_id)
                page.fill("input#password", password)
                page.fill("input#captcha", captcha_text)
                
                # Submit
                page.click("button#btnLogin")
                
                # Wait for navigation or error
                try:
                    # If invalid captcha or password, an alert or error div might show
                    # Or it navigates to HRDSystem.jsp
                    page.wait_for_url("**/HRDSystem.jsp*", timeout=8000)
                    logged_in = True
                    print("[SP] Login successful!")
                    break
                except Exception:
                    # Check for invalid captcha alert/text and retry
                    print(f"[SP] Login failed on attempt {attempt+1}. Retrying...")
                    # Reload page to get fresh captcha
                    page.goto("https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp")
                    
            if not logged_in:
                result_data['error'] = 'Invalid NetID, Password, or failed to solve CAPTCHA.'
                browser.close()
                return result_data
                
            page.wait_for_timeout(2000) # Let dashboard fully load

            # --- 2. Extract Attendance ---
            try:
                # Click on 'Attendance Details' in the sidebar menu
                page.click("text='Attendance Details'")
                page.wait_for_timeout(2000) # wait for content to load via ajax/iframe
                
                # Extract attendance table
                # We'll just grab the outerHTML of the table that appears and parse it later or here
                # Assuming there's a table with 'Course Code' etc.
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
                                # Calculate percentage
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
                                marks_raw = cols[2].inner_text().strip() # e.g. "4.10 / 5.00"
                                
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

if __name__ == "__main__":
    # Test script if executed directly
    print("Testing SP scraper...")
    # res = sync_sp_portal("xx1234", "yourpassword")
    # print(res)
