import time
import threading
import queue
import os
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__, static_folder='.')
CORS(app)

def scrape_academia_worker(reg_no, pwd, out_queue):
    p = None
    browser = None
    try:
        p = sync_playwright().start()
        print(f"[{reg_no}] Launching Academia Sniper...")
        
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()
        page.set_default_timeout(90000)

        if "@" not in reg_no: reg_no += "@srmist.edu.in"

        print(f"[{reg_no}] 1. Loading Academia Login Page...")
        try:
            page.goto("https://academia.srmist.edu.in/", wait_until="commit", timeout=60000)
            page.wait_for_timeout(5000)
        except Exception as e:
            out_queue.put({'success': False, 'error': f'Academia page failed to load: {str(e)}'})
            return

        def find_in_frames(selector, filter_text=None, filter_not_text=None):
            loc = page.locator(selector)
            if filter_text: loc = loc.filter(has_text=re.compile(filter_text, re.IGNORECASE))
            if filter_not_text: loc = loc.filter(has_not_text=re.compile(filter_not_text, re.IGNORECASE))
            if loc.count() > 0: return loc.first
            for frame in page.frames:
                try:
                    loc = frame.locator(selector)
                    if filter_text: loc = loc.filter(has_text=re.compile(filter_text, re.IGNORECASE))
                    if filter_not_text: loc = loc.filter(has_not_text=re.compile(filter_not_text, re.IGNORECASE))
                    if loc.count() > 0: return loc.first
                except: continue
            return None
            
        print(f"[{reg_no}] 2. Entering Email...")
        try:
            email_input = find_in_frames('input[type="email"], input[type="text"], input[name="LOGIN_ID"]', filter_not_text="hidden")
            if not email_input: raise Exception("Could not find Email box.")
            email_input.fill(reg_no, force=True)
            
            next_btn = find_in_frames('button, input[type="submit"]', filter_text="next|continue")
            if next_btn: next_btn.click(force=True, timeout=5000)
            else: page.keyboard.press("Enter")
        except Exception as e:
            out_queue.put({'success': False, 'error': f'Failed to enter Email: {str(e)}'})
            return

        print(f"[{reg_no}] 3. Entering Password...")
        try:
            pwd_input = None
            for _ in range(15): 
                pwd_input = find_in_frames('input[type="password"], input[name="PASSWORD"]')
                if pwd_input: break
                page.wait_for_timeout(1000)
                
            if not pwd_input: raise Exception("Could not find Password box.")
            
            pwd_input.fill("") 
            pwd_input.type(pwd, delay=50) 
            page.wait_for_timeout(1000) 
            
            submit_btn = find_in_frames('button, input[type="submit"]', filter_text="sign in|login|submit|verify")
            if submit_btn: submit_btn.click(force=True, timeout=5000)
            else: page.keyboard.press("Enter")
            page.wait_for_timeout(5000) 
        except Exception as e:
            out_queue.put({'success': False, 'error': f'Failed to enter Password: {str(e)}'})
            return

        print(f"[{reg_no}] 4. Checking for Session Limit Blocker...")
        try:
            terminate_btn = page.locator('button, a').filter(has_text=re.compile(r"terminate all session|terminate", re.IGNORECASE)).first
            if terminate_btn.count() > 0 and terminate_btn.is_visible(timeout=3000):
                print(f"[{reg_no}] Session blocked! Clicking Terminate All Sessions...")
                terminate_btn.click(force=True)
                page.wait_for_timeout(5000) 
        except: pass 

        # 🚨 THE HARD RELOAD BYPASS 🚨
        print(f"[{reg_no}] 5. Teleporting and forcing Hard Reload to My_Attendance...")
        try:
            page.goto("https://academia.srmist.edu.in/#Page:My_Attendance", wait_until="commit")
            # Force Zoho to read the hash by reloading the page
            page.reload(wait_until="commit") 
            page.wait_for_timeout(15000) # Give the tables plenty of time to render
        except Exception as e:
            print(f"[{reg_no}] Warning during teleport: {str(e)}")

        print(f"[{reg_no}] 6. Extracting all tables from all frames...")
        all_tables_data = []
        for frame in page.frames:
            try:
                tables = frame.evaluate("""() => {
                    let all = [];
                    document.querySelectorAll('table').forEach(t => {
                        let rows = [];
                        t.querySelectorAll('tr').forEach(tr => {
                            let row = [];
                            tr.querySelectorAll('td, th').forEach(td => {
                                row.push(td.innerText.trim());
                            });
                            if (row.length > 0) rows.push(row);
                        });
                        if (rows.length > 1) all.push(rows);
                    });
                    return all;
                }""")
                if tables: all_tables_data.extend(tables)
            except: pass

        print(f"[{reg_no}] 7. Parsing the extracted tables...")
        parsed_data = [] 
        parsed_marks = []
        
        for table in all_tables_data:
            # Check the table headers to identify it
            header_text = " ".join(table[0]).lower()
            if len(table) > 1: header_text += " " + " ".join(table[1]).lower()

            if "hours conducted" in header_text and "attn" in header_text:
                for row in table:
                    if len(row) >= 9:
                        if "Course Code" in row[0]: continue
                        try:
                            parsed_data.append({
                                "courseTitle": f"{row[0]} - {row[1][:25]}...",
                                "attended": int(row[6]) - int(row[7]),
                                "total": int(row[6])
                            })
                        except: pass
                        
            elif "test performance" in header_text or "internal" in header_text:
                for row in table:
                    if len(row) >= 3:
                        if "Course Code" in row[0]: continue
                        parsed_marks.append({
                            "courseTitle": f"{row[0]} ({row[1]})",
                            "Test Performance": row[2].replace('\n', ' | ')
                        })

        # 🚨 BULLETPROOF FAILSAFE: DUMP RAW TEXT IF PARSING FAILS 🚨
        if not parsed_data and not parsed_marks:
            if all_tables_data:
                out_queue.put({
                    'success': True, 
                    'data': [], 
                    'marks': [
                        {"courseTitle": "PARSING FAILED", "Internal Note": "Please screenshot this data!"},
                        {"RAW TABLES": str(all_tables_data)[:2000]}
                    ],
                    'timetable': []
                })
            else:
                out_queue.put({'success': False, 'error': 'Reached dashboard, but no tables were found in any iframe. Try syncing again.'})
            return

        out_queue.put({
            'success': True, 
            'data': parsed_data,
            'marks': parsed_marks,
            'timetable': []
        })

    except Exception as e:
        out_queue.put({'success': False, 'error': f"Unexpected Playwright Error: {str(e)}"})
    finally:
        if browser: browser.close()
        if p: p.stop()

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    out_queue = queue.Queue()
    t = threading.Thread(target=scrape_academia_worker, args=(data.get('regNo'), data.get('pwd'), out_queue))
    t.start()
    try:
        result = out_queue.get(timeout=110)
        return jsonify(result)
    except queue.Empty:
        return jsonify({'success': False, 'error': 'Server Timeout. Academia took too long to respond.'})

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
