from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import time
import os
import uuid
import base64
import threading
import queue
import subprocess

# ----- RENDER.COM CRASH FIX -----
# Render's free tier sometimes ignores render.yaml scripts and deletes the Chromium browser 
# after the container builds. This forces the Python server to download it directly into 
# the source folder every single time the container wakes up.
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
print("Starting backend... Verifying Chromium installation...")
subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=False)
print("Chromium Verification Complete.")
# --------------------------------

app = Flask(__name__)
CORS(app)

# ==========================================
# STATIC FILE ROUTING (THE RENDER FIX)
# ==========================================

@app.route("/")
def home():
    return send_file("index.html")

# 1. Tell Python it is allowed to serve your image folder!
@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory('images', filename)

# 2. Tell Python it is allowed to serve your PWA files (manifest.json, sw.js)
@app.route('/<path:filename>')
def serve_root_files(filename):
    return send_from_directory('.', filename)


# ==========================================
# SRM LIVE SYNC LOGIC
# ==========================================

active_sessions = {}
session_lock = threading.Lock()

def playwright_worker(session_id, reg_no, pwd, in_queue, out_queue):
    p = None
    browser = None
    try:
        p = sync_playwright().start()
        print(f"[{reg_no}] [Thread] Launching Chromium...")
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        print(f"[{reg_no}] [Thread] Navigating to SRM Portal...")
        page.goto("https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp")

        print(f"[{reg_no}] [Thread] Waiting for login form...")
        page.wait_for_selector('input[type="text"]', timeout=15000)
        
        print(f"[{reg_no}] [Thread] Filling credentials...")
        page.fill('input[type="text"]', reg_no)
        page.fill('input[type="password"]', pwd)
        
        # Check if it requires a CAPTCHA!
        captcha_input = page.locator('input[placeholder*="captcha" i], input[placeholder*="Captcha" i]').first
        
        if captcha_input.count() > 0:
            print(f"[{reg_no}] [Thread] Captcha DETECTED! Taking screenshot...")
            
            captcha_img = page.locator('img[src*="captcha" i], img[id*="captcha" i]').first
            if captcha_img.count() == 0:
                captcha_img = captcha_input.locator("xpath=..").locator("xpath=..")
                if captcha_img.count() == 0:
                     captcha_img = captcha_input

            time.sleep(1) 
            img_bytes = captcha_img.screenshot()
            b64_img = base64.b64encode(img_bytes).decode('utf-8')
            
            out_queue.put({
                'requires_captcha': True,
                'captcha_base64': f"data:image/png;base64,{b64_img}"
            })
            
            print(f"[{reg_no}] [Thread] Sleeping while waiting for user to solve Captcha...")
            try:
                user_msg = in_queue.get(timeout=180) 
            except queue.Empty:
                print(f"[{reg_no}] [Thread] User took too long to answer Captcha. Dying.")
                return 
                
            if user_msg.get('action') == 'kill':
                return
                
            captcha_text = user_msg.get('captcha_text')
            print(f"[{reg_no}] [Thread] Woke up! User provided CAPTCHA: '{captcha_text}'. Submitting...")
            
            captcha_input.fill(captcha_text)
            captcha_input.press('Enter')
            
        else:
            print(f"[{reg_no}] [Thread] No Captcha needed. Falling back to immediate submission...")
            page.press('input[type="password"]', 'Enter')
            out_queue.put({'requires_captcha': False})

        # --- The Shared Scraping Logic ---
        print(f"[{reg_no}] [Thread] Handling the Javascript Redirect Maze... (giving SRM up to 40 seconds to load)")
        try:
            page.wait_for_selector("text=Attendance Details, a:has-text('Attendance Details'), .navbar-brand >> visible=true", timeout=40000)
        except:
            print(f"[{reg_no}] [Thread] Dashboard didn't load in 40s. Checking for invisible portal error messages...")
            error_el = page.locator("span, td, div", has_text="Invalid").first
            if error_el.count() == 0:
                 error_el = page.locator("text=wrong, text=incorrect").first
            
            if error_el.count() > 0:
                 error_text = error_el.inner_text().strip()
                 print(f"[{reg_no}] [Thread] Found explicit Portal Error: {error_text}")
                 out_queue.put({'success': False, 'error': f'Portal Error: {error_text}'})
                 return
            
            print(f"[{reg_no}] [Thread] Dashboard load timeout. Generating debug screenshot...")
            page.screenshot(path=f"debug_playwright_{reg_no}.png", full_page=True)
            out_queue.put({'success': False, 'error': 'Playwright gave SRM 40 seconds to load but it timed out. The Captcha might have been wrong, or the portal is completely down right now.'})
            return
        
        print(f"[{reg_no}] [Thread] Successfully logged in! Navigating to Attendance...")
        try:
             page.click("text=Attendance Details, a:has-text('Attendance Details')", timeout=10000)
        except:
             print(f"[{reg_no}] [Thread] Could not find Attendance Details button to click.")
             out_queue.put({'success': False, 'error': 'Logged in successfully, but the Attendance page link is missing from your portal dashboard.'})
             return
        
        print(f"[{reg_no}] [Thread] Waiting for table frame...")
        try:
            page.wait_for_selector("table, #divMainDetails table", timeout=15000)
        except:
            page.screenshot(path=f"debug_playwright_table_{reg_no}.png", full_page=True)
            out_queue.put({'success': False, 'error': 'Clicked Attendance, but table never loaded.'})
            return

        print(f"[{reg_no}] [Thread] Parsing Table Rows...")
        rows_locator = page.locator("table tr")
        rows_count = rows_locator.count()
        live_scraped_data = []
        
        for idx in range(1, rows_count):
            cols = rows_locator.nth(idx).locator("td")
            col_count = cols.count()
            if col_count >= 6:
                try:
                    subject_name_text = cols.nth(1).inner_text().strip()
                    code_text = cols.nth(0).inner_text().strip()
                    subject_name = subject_name_text if len(subject_name_text) > 3 else code_text
                    
                    max_hours_str = cols.nth(col_count - 4).inner_text().strip()
                    attended_hours_str = cols.nth(col_count - 3).inner_text().strip()
                    
                    if max_hours_str.isdigit() and attended_hours_str.isdigit():
                        live_scraped_data.append({
                            'id': int(time.time() * 1000) + idx,
                            'name': subject_name,
                            'attended': int(attended_hours_str),
                            'total': int(max_hours_str)
                        })
                except Exception as parse_err:
                    print(f"Row skipped: {parse_err}")

        if len(live_scraped_data) > 0:
            print(f"[{reg_no}] [Thread] Scraping successful! Returning payload.")
            out_queue.put({'success': True, 'data': live_scraped_data})
        else:
            out_queue.put({'success': False, 'error': 'Table found, but no subjects could be parsed.'})

    except Exception as fn_err:
        print(f"[{reg_no}] [Thread] Critical scraping failure: {str(fn_err)}")
        out_queue.put({'success': False, 'error': f'Backend error during extraction: {str(fn_err)}'})
    finally:
        print(f"[{reg_no}] [Thread] Tearing down browser.")
        if browser:
            try: browser.close()
            except: pass
        if p:
            try: p.stop()
            except: pass
        with session_lock:
             active_sessions.pop(session_id, None)

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    reg_no = data.get('regNo')
    pwd = data.get('pwd')

    if not reg_no or not pwd:
        return jsonify({'success': False, 'error': 'Registration number and password are required.'}), 400

    session_id = str(uuid.uuid4())
    in_queue = queue.Queue()
    out_queue = queue.Queue()
    
    with session_lock:
        active_sessions[session_id] = {
            'in_queue': in_queue,
            'out_queue': out_queue,
            'reg_no': reg_no,
            'timestamp': time.time()
        }

    t = threading.Thread(target=playwright_worker, args=(session_id, reg_no, pwd, in_queue, out_queue))
    t.daemon = True
    t.start()

    try:
        result = out_queue.get(timeout=30) 
        
        if result.get('requires_captcha'):
            return jsonify({
                'success': True,
                'requires_captcha': True,
                'session_id': session_id,
                'captcha_base64': result.get('captcha_base64')
            })
            
        else:
            final_result = out_queue.get(timeout=60)
            if final_result.get('success'):
                return jsonify({'success': True, 'requires_captcha': False, 'data': final_result.get('data')})
            else:
                return jsonify({'success': False, 'error': final_result.get('error')}), 500
                
    except queue.Empty:
        return jsonify({'success': False, 'error': 'The cloud browser timed out while trying to reach the login page.'}), 502
    except Exception as e:
         return jsonify({'success': False, 'error': f'A backend error occurred starting the session: {str(e)}'}), 500

@app.route('/api/submit_captcha', methods=['POST'])
def submit_captcha():
    data = request.json
    session_id = data.get('session_id')
    captcha_text = data.get('captcha_text')

    if not session_id or not captcha_text:
        return jsonify({'success': False, 'error': 'Missing session_id or captcha text.'}), 400

    with session_lock:
        session_data = active_sessions.get(session_id)
        
    if not session_data:
        return jsonify({'success': False, 'error': 'Your login session timed out. Please try again from the beginning.'}), 400

    in_queue = session_data['in_queue']
    out_queue = session_data['out_queue']
    reg_no = session_data['reg_no']
    
    print(f"[{reg_no}] Passing Captcha to Worker Thread...")
    in_queue.put({'action': 'submit', 'captcha_text': captcha_text})
    
    try:
        final_result = out_queue.get(timeout=60)
        
        if final_result.get('success'):
            return jsonify({'success': True, 'data': final_result.get('data')})
        else:
            return jsonify({'success': False, 'error': final_result.get('error')}), 500
            
    except queue.Empty:
         return jsonify({'success': False, 'error': 'The cloud browser timed out while waiting for the dashboard to load.'}), 502
    except Exception as e:
         return jsonify({'success': False, 'error': f'A backend error occurred after captcha: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
