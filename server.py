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

def scrape_academia_worker(reg_no, pwd, batch, out_queue):
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

        print(f"[{reg_no}] 1. Loading Academia...")
        try:
            page.goto("https://academia.srmist.edu.in/", wait_until="networkidle", timeout=60000)
        except Exception as e:
            out_queue.put({'success': False, 'error': f'Portal failed to load: {str(e)}'})
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
            
        # Login Logic
        try:
            email_input = find_in_frames('input[type="email"], input[type="text"], input[name="LOGIN_ID"]', filter_not_text="hidden")
            if not email_input: raise Exception("Email box not found")
            email_input.fill(reg_no, force=True)
            
            next_btn = find_in_frames('button, input[type="submit"]', filter_text="next|continue")
            if next_btn: next_btn.click(force=True, timeout=5000)
            else: page.keyboard.press("Enter")

            pwd_input = None
            for _ in range(10): 
                pwd_input = find_in_frames('input[type="password"], input[name="PASSWORD"]')
                if pwd_input: break
                page.wait_for_timeout(1000)
                
            if not pwd_input: raise Exception("Password box not found")
            pwd_input.type(pwd, delay=30) 
            
            submit_btn = find_in_frames('button, input[type="submit"]', filter_text="sign in|login|submit|verify")
            if submit_btn: submit_btn.click(force=True, timeout=5000)
            else: page.keyboard.press("Enter")
            page.wait_for_timeout(5000) 

            terminate_btn = page.locator('button, a').filter(has_text=re.compile(r"terminate", re.IGNORECASE)).first
            if terminate_btn.count() > 0: terminate_btn.click(force=True); page.wait_for_timeout(4000)
        except Exception as e:
            out_queue.put({'success': False, 'error': f'Auth Failed: {str(e)}'})
            return

        def get_all_tables():
            try:
                page.wait_for_selector("iframe", timeout=10000)
            except Exception as e:
                print("Wait for iframe error:", str(e))
            all_tables = []
            for frame in page.frames:
                try:
                    tables = frame.evaluate("""() => {
                        return Array.from(document.querySelectorAll('table')).map(t => 
                            Array.from(t.querySelectorAll('tr')).map(tr => 
                                Array.from(tr.querySelectorAll('td, th')).map(td => td.innerText.trim())
                            ).filter(row => row.length > 0)
                        ).filter(table => table.length > 0);
                    }""")
                    if tables: all_tables.extend(tables)
                except: pass
            return all_tables

        def get_col_index(headers, *keywords):
            for i, h in enumerate(headers):
                h_lower = str(h).lower()
                if any(kw in h_lower for kw in keywords):
                    return i
            return -1

        # --- ATTENDANCE & MARKS ---
        print(f"[{reg_no}] 5. Scoping Attendance...")
        page.goto("https://academia.srmist.edu.in/#Page:My_Attendance")
        page.reload(wait_until="networkidle")

        raw_tables = get_all_tables()
        parsed_att = []
        parsed_marks = []

        for table in raw_tables:
            if not table: continue
            headers = [str(h).lower() for h in table[0]]
            header_str = " ".join(headers)

            # Dynamic Attendance Parsing
            if "hours conducted" in header_str and "absent" in header_str:
                try:
                    idx_code = get_col_index(headers, "code")
                    idx_title = get_col_index(headers, "title")
                    idx_cond = get_col_index(headers, "conducted")
                    idx_abs = get_col_index(headers, "absent")
                    
                    if -1 in (idx_code, idx_title, idx_cond, idx_abs): continue
                    
                    for row in table[1:]:
                        if len(row) > max(idx_cond, idx_abs):
                            cond = int(float(row[idx_cond] or 0))
                            absent = int(float(row[idx_abs] or 0))
                            parsed_att.append({
                                "courseTitle": f"{row[idx_code]} - {row[idx_title][:20]}",
                                "attended": max(0, cond - absent),
                                "total": cond
                            })
                except Exception as e:
                    print("Parsing error (Attendance):", str(e))
                    continue

            # Dynamic Marks Parsing
            elif any(kw in header_str for kw in ["test performance", "assessment", "marks", "internal"]):
                try:
                    idx_code = get_col_index(headers, "code")
                    idx_perf = get_col_index(headers, "performance", "assessment", "marks", "internal")
                    
                    if idx_code == -1 or idx_perf == -1: continue
                    
                    for row in table[1:]:
                        if len(row) > idx_perf:
                            parsed_marks.append({
                                "courseTitle": row[idx_code],
                                "Test Performance": row[idx_perf].replace('\n', ' | ')
                            })
                except Exception as e:
                    print("Parsing error (Marks):", str(e))
                    continue

        # --- TIMETABLE STEP 1 (STUDENT SLOTS) ---
        print(f"[{reg_no}] 6. Scoping Registered Slots...")
        student_slots = {}
        page.goto("https://academia.srmist.edu.in/#Page:My_Time_Table_2023_24")
        
        slot_tables = get_all_tables()
        for table in slot_tables:
            if not table: continue
            headers = [str(h).lower() for h in table[0]]
            header_str = " ".join(headers)
            
            if "slot" in header_str and "code" in header_str:
                try:
                    idx_code = get_col_index(headers, "code")
                    idx_title = get_col_index(headers, "title")
                    idx_slot = get_col_index(headers, "slot")
                    idx_room = get_col_index(headers, "room")
                    
                    if -1 in (idx_code, idx_title, idx_slot, idx_room): continue
                    
                    for row in table[1:]:
                        if len(row) > idx_room:
                            # Refined Regex matching
                            slots_found = re.findall(r'[A-Z]\d+', row[idx_slot])
                            for s in slots_found:
                                student_slots[s] = {
                                    "subject": f"{row[idx_code]} - {row[idx_title]}",
                                    "room": row[idx_room]
                                }
                except Exception as e:
                    print("Parsing error (Slots):", str(e))
                    continue

        # --- TIMETABLE STEP 2 (MASTER TIMINGS) ---
        print(f"[{reg_no}] 7. Mapping to Master (Batch {batch})...")
        final_tt = {"1": [], "2": [], "3": [], "4": [], "5": []}
        page.goto(f"https://academia.srmist.edu.in/#Page:Unified_Time_Table_2025_Batch_{batch}")
        
        master_tables = get_all_tables()
        for table in master_tables:
            if not table: continue
            headers = [str(h).lower() for h in table[0]]
            
            if "day order" in headers[0] or "day" in headers[0]:
                time_cols = table[0][1:]
                for row in table[1:]:
                    try:
                        day_match = re.search(r'\d+', row[0])
                        if not day_match: continue
                        day_order = day_match.group()
                        
                        if day_order in final_tt:
                            seen_entries = set()
                            for i, cell in enumerate(row[1:]):
                                slots_in_cell = re.findall(r'[A-Z]\d+', cell)
                                for s in slots_in_cell:
                                    if s in student_slots:
                                        entry_key = f"{time_cols[i] if i < len(time_cols) else 'N/A'}-{student_slots[s]['subject']}"
                                        if entry_key not in seen_entries:
                                            final_tt[day_order].append({
                                                "time": time_cols[i] if i < len(time_cols) else "N/A",
                                                "subject": student_slots[s]['subject'],
                                                "room": student_slots[s]['room']
                                            })
                                            seen_entries.add(entry_key)
                    except Exception as e:
                        print("Parsing error (Master TT Row):", str(e))
                        continue

        # Debug Logging for Empty Parsing
        if not parsed_att and not parsed_marks and not student_slots:
            try:
                with open("debug_tables.txt", "w", encoding="utf-8") as f:
                    f.write("RAW TABLES:\n" + str(raw_tables) + "\n\nSLOT TABLES:\n" + str(slot_tables) + "\n\nMASTER TABLES:\n" + str(master_tables))
                print(f"[{reg_no}] Empty arrays detected. Saved to debug_tables.txt")
            except Exception as e:
                print(f"Failed to write debug file: {str(e)}")

        out_queue.put({
            'success': True, 
            'data': parsed_att,
            'marks': parsed_marks,
            'timetable': final_tt
        })

    except Exception as e:
        out_queue.put({'success': False, 'error': f"Scraper Exception: {str(e)}"})
    finally:
        if browser: browser.close()
        if p: p.stop()

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    out_queue = queue.Queue()
    t = threading.Thread(target=scrape_academia_worker, args=(data.get('regNo'), data.get('pwd'), data.get('batch', 1), out_queue))
    t.start()
    try:
        result = out_queue.get(timeout=150) 
        return jsonify(result)
    except queue.Empty:
        return jsonify({'success': False, 'error': 'Server Timeout. Check internet speed.'})

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
