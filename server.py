import time
import threading
import queue
import os
import re
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__, static_folder='.')
CORS(app)

import os

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("[DB] WARNING: psycopg2 not installed but DATABASE_URL is set! Falling back to SQLite.")
        DATABASE_URL = None

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hub.db')

def get_db():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute('''CREATE TABLE IF NOT EXISTS students (
            net_id TEXT PRIMARY KEY, name TEXT, register_no TEXT,
            overall_attendance REAL DEFAULT 0, est_cgpa REAL DEFAULT 0, synced_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT, tech_stack TEXT,
            github_url TEXT, demo_url TEXT, submitted_by TEXT, net_id TEXT, submitted_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS marketplace (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT, category TEXT, price TEXT, phone_no TEXT, image_url TEXT,
            seller_name TEXT, net_id TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS campus_wall (
            id SERIAL PRIMARY KEY, message TEXT NOT NULL, author TEXT, likes INTEGER DEFAULT 0, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS cab_sharing (
            id SERIAL PRIMARY KEY, destination TEXT NOT NULL, travel_date TEXT, travel_time TEXT, spots TEXT, phone_no TEXT,
            creator_name TEXT, net_id TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS club_events (
            id SERIAL PRIMARY KEY, club_name TEXT NOT NULL, event_title TEXT NOT NULL, event_date TEXT, registration_link TEXT, image_url TEXT,
            created_by TEXT, net_id TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS lost_found (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT, category TEXT, location TEXT, image_url TEXT,
            poster_name TEXT, net_id TEXT, created_at TEXT)''')
    else:
        cur.execute('''CREATE TABLE IF NOT EXISTS students (
            net_id TEXT PRIMARY KEY, name TEXT, register_no TEXT,
            overall_attendance REAL DEFAULT 0, est_cgpa REAL DEFAULT 0, synced_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, tech_stack TEXT,
            github_url TEXT, demo_url TEXT, submitted_by TEXT, net_id TEXT, submitted_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS marketplace (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, category TEXT, price TEXT, phone_no TEXT, image_url TEXT,
            seller_name TEXT, net_id TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS campus_wall (
            id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, author TEXT, likes INTEGER DEFAULT 0, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS cab_sharing (
            id INTEGER PRIMARY KEY AUTOINCREMENT, destination TEXT NOT NULL, travel_date TEXT, travel_time TEXT, spots TEXT, phone_no TEXT,
            creator_name TEXT, net_id TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS club_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, club_name TEXT NOT NULL, event_title TEXT NOT NULL, event_date TEXT, registration_link TEXT, image_url TEXT,
            created_by TEXT, net_id TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS lost_found (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, category TEXT, location TEXT, image_url TEXT,
            poster_name TEXT, net_id TEXT, created_at TEXT)''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

def save_student_to_db(net_id, name, register_no, att_data, marks_data):
    try:
        # Calculate Attendance
        total_att = 0; total_cls = 0
        for sub in (att_data or []):
            try:
                total_att += int(sub.get('attended', 0) or 0)
                total_cls += int(sub.get('total', 0) or 0)
            except: continue
        overall_att = round((total_att / total_cls) * 100, 1) if total_cls > 0 else 0.0

        # Calculate Est CGPA (Mimicking Frontend Logic)
        grand_total_obtained = 0
        grand_total_max = 0
        for sub in (marks_data or []):
            try:
                perf_string = sub.get('Test Performance') or sub.get('performance') or sub.get('marks') or ""
                matches = re.findall(r'([A-Za-z0-9-]+)/([0-9.]+)\s*\|\s*([0-9.]+)', perf_string)
                for test_name, max_str, obtained_str in matches:
                    try:
                        grand_total_max += float(max_str)
                        grand_total_obtained += float(obtained_str)
                    except ValueError:
                        pass
            except Exception as e:
                continue
                
        cgpa = round((grand_total_obtained / grand_total_max) * 10, 2) if grand_total_max > 0 else 0.0

        conn = get_db()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute('''
                INSERT INTO students (net_id, name, register_no, overall_attendance, est_cgpa, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(net_id) DO UPDATE SET
                    name=EXCLUDED.name, register_no=EXCLUDED.register_no,
                    overall_attendance=EXCLUDED.overall_attendance, est_cgpa=EXCLUDED.est_cgpa,
                    synced_at=EXCLUDED.synced_at
            ''', (net_id.lower(), name, register_no.upper(), overall_att, cgpa, datetime.utcnow().isoformat()))
        else:
            cur.execute('''
                INSERT INTO students (net_id, name, register_no, overall_attendance, est_cgpa, synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(net_id) DO UPDATE SET
                    name=excluded.name, register_no=excluded.register_no,
                    overall_attendance=excluded.overall_attendance, est_cgpa=excluded.est_cgpa,
                    synced_at=excluded.synced_at
            ''', (net_id.lower(), name, register_no.upper(), overall_att, cgpa, datetime.utcnow().isoformat()))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] save_student_to_db error: {e}")




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
                            Array.from(t.querySelectorAll('tr')).map(tr => {
                                let rowArr = [];
                                Array.from(tr.querySelectorAll('td, th')).forEach(td => {
                                    let span = td.colSpan || 1;
                                    let text = td.innerText.trim();
                                    for(let i=0; i<span; i++) rowArr.push(text);
                                });
                                return rowArr;
                            }).filter(row => row.length > 0)
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
        page.wait_for_timeout(3000)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(5000)

        raw_tables = get_all_tables()
        parsed_att = []
        parsed_marks = []

        # Profile Extraction
        profile_data = {
            "name": "STUDENT",
            "regNo": reg_no.split('@')[0].upper(),
            "course": "B.Tech",
            "semester": "Current"
        }
        for table in raw_tables:
            if not table: continue
            for row in table:
                if len(row) >= 2:
                    for i in range(len(row) - 1):
                        k = str(row[i]).replace(':', '').strip().lower()
                        v = str(row[i+1]).replace(':', '').strip()
                        if "name" in k and not "father" in k and not "mother" in k:
                            if len(v) > 2 and profile_data["name"] == "STUDENT": profile_data["name"] = v
                        elif "program" in k or "course" in k or "degree" in k or "branch" in k:
                            if len(v) > 2: profile_data["course"] = v[:35]
                        elif "semester" in k:
                            if len(v) > 0 and len(v) <= 2: profile_data["semester"] = v

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
        # Reverted 2024_25 back to 2023_24 based on Academia's weird hardcoded URL hash
        page.goto("https://academia.srmist.edu.in/#Page:My_Time_Table_2023_24")
        page.wait_for_timeout(5000)
        
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
                            # Refined Regex matching (matches A, P49, PT2, etc)
                            slots_found = re.findall(r'\b[A-Z]{1,2}\d*\b', row[idx_slot])
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
        page.wait_for_timeout(5000)
        
        master_tables = get_all_tables()
        for table in master_tables:
            if not table: continue
            
            time_cols = []
            from_row = []
            to_row = []
            start_row = -1
            
            for r_idx, row in enumerate(table):
                first_cell = str(row[0]).lower().replace('\n', ' ').strip()
                
                if "from" in first_cell and "to" not in first_cell: from_row = row[1:]
                elif "to" in first_cell and "from" not in first_cell: to_row = row[1:]
                elif "from" in first_cell and "to" in first_cell:
                    time_cols = [str(c).replace('\n', ' ') for c in row[1:]]
                elif any(x in first_cell for x in ["hour", "order", "time", "period"]):
                    if not time_cols and not from_row:
                        time_cols = [str(c).replace('\n', ' ') for c in row[1:]]
                elif "day" in first_cell and any(str(i) in first_cell for i in range(1, 6)):
                    start_row = r_idx
                    break
                    
            if not time_cols and from_row and to_row:
                for f, t in zip(from_row, to_row):
                    time_cols.append(f"{f} - {t}")
                    
            if start_row != -1:
                for row in table[start_row:]:
                    try:
                        day_match = re.search(r'\d+', row[0])
                        if not day_match: continue
                        day_order = day_match.group()
                        
                        if day_order in final_tt:
                            seen_entries = set()
                            for i, cell in enumerate(row[1:]):
                                slots_in_cell = re.findall(r'\b[A-Z]{1,2}\d*\b', cell)
                                for s in slots_in_cell:
                                    if s in student_slots:
                                        t_str = time_cols[i] if i < len(time_cols) else f"Period {i+1}"
                                        t_str = re.sub(r'\s+', ' ', t_str).strip()
                                        
                                        entry_key = f"{t_str}-{student_slots[s]['subject']}"
                                        if entry_key not in seen_entries:
                                            final_tt[day_order].append({
                                                "time": t_str,
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
            'profile': profile_data,
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
        # Auto-save student to DB on every successful sync
        if result.get('success'):
            profile = result.get('profile', {})
            raw_reg = data.get('regNo', '')
            net_id = raw_reg.split('@')[0]          # e.g. ra2511026010324
            register_no = net_id.upper()            # e.g. RA2511026010324
            name = profile.get('name', 'Student')
            save_student_to_db(net_id, name, register_no, result.get('data', []), result.get('marks', []))
        return jsonify(result)
    except queue.Empty:
        return jsonify({'success': False, 'error': 'Server Timeout. Check internet speed.'})

@app.route('/api/save_student', methods=['POST'])
def save_student():
    d = request.json
    try:
        conn = get_db()
        if DATABASE_URL:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO students (net_id, name, overall_attendance, est_cgpa, synced_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(net_id) DO UPDATE SET
                        name=EXCLUDED.name,
                        overall_attendance=EXCLUDED.overall_attendance,
                        est_cgpa=EXCLUDED.est_cgpa,
                        synced_at=EXCLUDED.synced_at
                ''', (d.get('net_id','').lower(), d.get('name','Student'),
                      float(d.get('attendance', 0)), float(d.get('cgpa', 0)),
                      datetime.utcnow().isoformat()))
        else:
            conn.execute('''
                INSERT INTO students (net_id, name, overall_attendance, est_cgpa, synced_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(net_id) DO UPDATE SET
                    name=excluded.name,
                    overall_attendance=excluded.overall_attendance,
                    est_cgpa=excluded.est_cgpa,
                    synced_at=excluded.synced_at
            ''', (d.get('net_id','').lower(), d.get('name','Student'),
                  float(d.get('attendance', 0)), float(d.get('cgpa', 0)),
                  datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/leaderboard/attendance', methods=['GET'])
def leaderboard_attendance():
    conn = get_db()
    if DATABASE_URL:
        # Use RealDictCursor style for Postgres
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT name, net_id, register_no, overall_attendance FROM students ORDER BY overall_attendance DESC LIMIT 50')
            rows = cur.fetchall()
    else:
        rows = [dict(r) for r in conn.execute('SELECT name, net_id, register_no, overall_attendance FROM students ORDER BY overall_attendance DESC LIMIT 50').fetchall()]
    conn.close()
    return jsonify(list(rows))

@app.route('/api/leaderboard/marks', methods=['GET'])
def leaderboard_marks():
    conn = get_db()
    if DATABASE_URL:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT name, net_id, register_no, est_cgpa FROM students ORDER BY est_cgpa DESC LIMIT 50')
            rows = cur.fetchall()
    else:
        rows = [dict(r) for r in conn.execute('SELECT name, net_id, register_no, est_cgpa FROM students ORDER BY est_cgpa DESC LIMIT 50').fetchall()]
    conn.close()
    return jsonify(list(rows))

@app.route('/api/projects', methods=['GET'])
def get_projects():
    conn = get_db()
    if DATABASE_URL:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM projects ORDER BY submitted_at DESC')
            rows = cur.fetchall()
    else:
        rows = [dict(r) for r in conn.execute('SELECT * FROM projects ORDER BY submitted_at DESC').fetchall()]
    conn.close()
    return jsonify(list(rows))

@app.route('/api/projects/submit', methods=['POST'])
def submit_project():
    data = request.json
    required = ['title', 'submitted_by']
    if not all(k in data for k in required):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()
    tz = 'IST' # Simplified wrapper
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO projects (title, description, tech_stack, github_url, demo_url, submitted_by, net_id, submitted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (data.get('title'), data.get('description',''), data.get('tech_stack',''),
                  data.get('github_url',''), data.get('demo_url',''), data.get('submitted_by'),
                  data.get('net_id',''), now_str))
        else:
            cur.execute("""
                INSERT INTO projects (title, description, tech_stack, github_url, demo_url, submitted_by, net_id, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (data.get('title'), data.get('description',''), data.get('tech_stack',''),
                  data.get('github_url',''), data.get('demo_url',''), data.get('submitted_by'),
                  data.get('net_id',''), now_str))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({'success': True})

# --- NEW MARKETPLACE ROUTES ---

@app.route('/api/marketplace', methods=['GET'])
def get_marketplace():
    conn = get_db()
    
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM marketplace ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        projects = [dict(row) for row in rows]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM marketplace ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        projects = [dict(row) for row in rows]
    
    cur.close()
    conn.close()
    return jsonify(projects)

@app.route('/api/marketplace/submit', methods=['POST'])
def submit_marketplace():
    data = request.json
    required = ['title', 'category', 'seller_name']
    if not all(k in data for k in required) or not data['title']:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO marketplace (title, description, category, price, phone_no, image_url, seller_name, net_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (data.get('title'), data.get('description',''), data.get('category',''),
                  data.get('price',''), data.get('phone_no',''), data.get('image_url',''),
                  data.get('seller_name'), data.get('net_id',''), now_str))
        else:
            cur.execute("""
                INSERT INTO marketplace (title, description, category, price, phone_no, image_url, seller_name, net_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (data.get('title'), data.get('description',''), data.get('category',''),
                  data.get('price',''), data.get('phone_no',''), data.get('image_url',''),
                  data.get('seller_name'), data.get('net_id',''), now_str))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({'success': True})

# --- MARKETPLACE DELETE (Owner Only) ---

@app.route('/api/marketplace/delete/<int:item_id>', methods=['DELETE'])
def delete_marketplace(item_id):
    data = request.json or {}
    net_id = data.get('net_id', '').lower().strip()
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("SELECT net_id FROM marketplace WHERE id = %s", (item_id,))
        else:
            cur.execute("SELECT net_id FROM marketplace WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        owner_id = (dict(row) if DATABASE_URL else dict(row)).get('net_id', '').lower().strip()
        if owner_id != net_id:
            return jsonify({'success': False, 'error': 'You can only delete your own listings'}), 403

        if DATABASE_URL:
            cur.execute("DELETE FROM marketplace WHERE id = %s", (item_id,))
        else:
            cur.execute("DELETE FROM marketplace WHERE id = ?", (item_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

# --- CAMPUS WALL ROUTES ---

@app.route('/api/wall', methods=['GET'])
def get_wall():
    conn = get_db()
    
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM campus_wall ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        posts = [dict(row) for row in rows]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM campus_wall ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        posts = [dict(row) for row in rows]
    
    cur.close()
    conn.close()
    return jsonify(posts)

@app.route('/api/wall/submit', methods=['POST'])
def submit_wall():
    data = request.json
    if not data or not data.get('message'):
        return jsonify({'success': False, 'error': 'Message required'}), 400

    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if DATABASE_URL:
            cur.execute("INSERT INTO campus_wall (message, author, created_at) VALUES (%s, %s, %s)",
                       (data.get('message'), data.get('author', 'Anonymous'), now_str))
        else:
            cur.execute("INSERT INTO campus_wall (message, author, created_at) VALUES (?, ?, ?)",
                       (data.get('message'), data.get('author', 'Anonymous'), now_str))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({'success': True})

@app.route('/api/wall/like/<int:post_id>', methods=['POST'])
def like_wall(post_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("UPDATE campus_wall SET likes = likes + 1 WHERE id = %s", (post_id,))
        else:
            cur.execute("UPDATE campus_wall SET likes = likes + 1 WHERE id = ?", (post_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

# --- CAB SHARING ROUTES ---

@app.route('/api/cabs', methods=['GET'])
def get_cabs():
    conn = get_db()
    
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Delete old trips ideally, but for now just fetch recent ones
        cur.execute("SELECT * FROM cab_sharing ORDER BY travel_date ASC, travel_time ASC LIMIT 100")
        rows = cur.fetchall()
        cabs = [dict(row) for row in rows]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cab_sharing ORDER BY travel_date ASC, travel_time ASC LIMIT 100")
        rows = cur.fetchall()
        cabs = [dict(row) for row in rows]
    
    cur.close()
    conn.close()
    return jsonify(cabs)

@app.route('/api/cabs/submit', methods=['POST'])
def submit_cab():
    data = request.json
    required = ['destination', 'travel_date', 'travel_time', 'phone_no']
    if not all(k in data for k in required) or not data['destination']:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO cab_sharing (destination, travel_date, travel_time, spots, phone_no, creator_name, net_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (data.get('destination'), data.get('travel_date'), data.get('travel_time'),
                  data.get('spots',''), data.get('phone_no'), data.get('creator_name'),
                  data.get('net_id',''), now_str))
        else:
            cur.execute("""
                INSERT INTO cab_sharing (destination, travel_date, travel_time, spots, phone_no, creator_name, net_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (data.get('destination'), data.get('travel_date'), data.get('travel_time'),
                  data.get('spots',''), data.get('phone_no'), data.get('creator_name'),
                  data.get('net_id',''), now_str))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({'success': True})

# --- CAB SHARING DELETE (Owner Only) ---

@app.route('/api/cabs/delete/<int:cab_id>', methods=['DELETE'])
def delete_cab(cab_id):
    data = request.json or {}
    net_id = data.get('net_id', '').lower().strip()
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("SELECT net_id FROM cab_sharing WHERE id = %s", (cab_id,))
        else:
            cur.execute("SELECT net_id FROM cab_sharing WHERE id = ?", (cab_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Ride not found'}), 404

        owner_id = (dict(row) if DATABASE_URL else dict(row)).get('net_id', '').lower().strip()
        if owner_id != net_id:
            return jsonify({'success': False, 'error': 'You can only delete your own rides'}), 403

        if DATABASE_URL:
            cur.execute("DELETE FROM cab_sharing WHERE id = %s", (cab_id,))
        else:
            cur.execute("DELETE FROM cab_sharing WHERE id = ?", (cab_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

# --- EVENTS & CLUB RADAR ROUTES ---

@app.route('/api/events', methods=['GET'])
def get_events():
    conn = get_db()
    
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM club_events ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        events = [dict(row) for row in rows]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM club_events ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        events = [dict(row) for row in rows]
    
    cur.close()
    conn.close()
    return jsonify(events)

@app.route('/api/events/submit', methods=['POST'])
def submit_event():
    data = request.json
    required = ['club_name', 'event_title', 'event_date']
    if not all(k in data for k in required) or not data['event_title']:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO club_events (club_name, event_title, event_date, registration_link, image_url, created_by, net_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (data.get('club_name'), data.get('event_title'), data.get('event_date'),
                  data.get('registration_link',''), data.get('image_url',''),
                  data.get('created_by'), data.get('net_id',''), now_str))
        else:
            cur.execute("""
                INSERT INTO club_events (club_name, event_title, event_date, registration_link, image_url, created_by, net_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (data.get('club_name'), data.get('event_title'), data.get('event_date'),
                  data.get('registration_link',''), data.get('image_url',''),
                  data.get('created_by'), data.get('net_id',''), now_str))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({'success': True})

# --- LOST & FOUND ROUTES ---

@app.route('/api/lostfound', methods=['GET'])
def get_lostfound():
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM lost_found ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        items = [dict(row) for row in rows]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM lost_found ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        items = [dict(row) for row in rows]
    cur.close()
    conn.close()
    return jsonify(items)

@app.route('/api/lostfound/submit', methods=['POST'])
def submit_lostfound():
    data = request.json
    required = ['title', 'category']
    if not all(k in data for k in required) or not data['title']:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO lost_found (title, description, category, location, image_url, poster_name, net_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (data.get('title'), data.get('description',''), data.get('category',''),
                  data.get('location',''), data.get('image_url',''),
                  data.get('poster_name','Student'), data.get('net_id',''), now_str))
        else:
            cur.execute("""
                INSERT INTO lost_found (title, description, category, location, image_url, poster_name, net_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (data.get('title'), data.get('description',''), data.get('category',''),
                  data.get('location',''), data.get('image_url',''),
                  data.get('poster_name','Student'), data.get('net_id',''), now_str))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/lostfound/delete/<int:item_id>', methods=['DELETE'])
def delete_lostfound(item_id):
    data = request.json or {}
    net_id = data.get('net_id', '').lower().strip()
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("SELECT net_id FROM lost_found WHERE id = %s", (item_id,))
        else:
            cur.execute("SELECT net_id FROM lost_found WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        owner_id = (dict(row) if DATABASE_URL else dict(row)).get('net_id', '').lower().strip()
        if owner_id != net_id:
            return jsonify({'success': False, 'error': 'You can only delete your own posts'}), 403

        if DATABASE_URL:
            cur.execute("DELETE FROM lost_found WHERE id = %s", (item_id,))
        else:
            cur.execute("DELETE FROM lost_found WHERE id = ?", (item_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/ping')
def ping(): return 'pong', 200

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
