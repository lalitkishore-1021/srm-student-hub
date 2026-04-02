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
import sqlite3
import re
import json
from datetime import datetime

# ----- RENDER.COM CRASH FIX -----
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
print("Starting backend... Verifying Chromium installation...")
subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=False)
print("Chromium Verification Complete.")

app = Flask(__name__)
CORS(app)

# ==========================================
# DATABASE SETUP
# ==========================================
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
        cur.execute('''CREATE TABLE IF NOT EXISTS campus_polls (
            id SERIAL PRIMARY KEY, question TEXT NOT NULL, options TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS poll_votes (
            id SERIAL PRIMARY KEY, poll_id INTEGER, net_id TEXT, option_index INTEGER, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS placements (
            id SERIAL PRIMARY KEY, company_name TEXT NOT NULL, role TEXT, ctc TEXT, visit_date TEXT, experience TEXT, submitted_by TEXT, net_id TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS lost_found (
            id SERIAL PRIMARY KEY, item_name TEXT NOT NULL, description TEXT, location TEXT, type TEXT, contact_phone TEXT, net_id TEXT, created_at TEXT)''')
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
        cur.execute('''CREATE TABLE IF NOT EXISTS campus_polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, options TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS poll_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, poll_id INTEGER, net_id TEXT, option_index INTEGER, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS placements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL, role TEXT, ctc TEXT, visit_date TEXT, experience TEXT, submitted_by TEXT, net_id TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS lost_found (
            id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT NOT NULL, description TEXT, location TEXT, type TEXT, contact_phone TEXT, net_id TEXT, created_at TEXT)''')
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

        # Calculate Est CGPA
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
                    name=CASE WHEN EXCLUDED.name != 'Student' THEN EXCLUDED.name ELSE students.name END,
                    register_no=EXCLUDED.register_no,
                    overall_attendance=EXCLUDED.overall_attendance, est_cgpa=EXCLUDED.est_cgpa,
                    synced_at=EXCLUDED.synced_at
            ''', (net_id.lower(), name, register_no.upper(), overall_att, cgpa, datetime.utcnow().isoformat()))
        else:
            cur.execute('''
                INSERT INTO students (net_id, name, register_no, overall_attendance, est_cgpa, synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(net_id) DO UPDATE SET
                    name=CASE WHEN excluded.name != 'Student' THEN excluded.name ELSE students.name END,
                    register_no=excluded.register_no,
                    overall_attendance=excluded.overall_attendance, est_cgpa=excluded.est_cgpa,
                    synced_at=excluded.synced_at
            ''', (net_id.lower(), name, register_no.upper(), overall_att, cgpa, datetime.utcnow().isoformat()))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] save_student_to_db error: {e}")

# ==========================================
# STATIC FILES SERVING
# ==========================================
@app.route("/")
def home():
    return send_file("index.html")

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory('images', filename)

@app.route('/<path:filename>')
def serve_root_files(filename):
    return send_from_directory('.', filename)

# ==========================================
# PLAYWRIGHT SCRAPING LOGIC
# ==========================================
active_sessions = {}
completed_sessions = {}
session_lock = threading.Lock()

def playwright_worker(session_id, reg_no, pwd, batch, in_queue, out_queue):
    p = None
    browser = None
    start_time = time.time()
    try:
        p = sync_playwright().start()
        print(f"[{reg_no}] [Thread] Launching Chromium...")

        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
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

            print(f"[{reg_no}] [Thread] Waiting for user to solve Captcha...")
            try:
                user_msg = in_queue.get(timeout=180)
            except queue.Empty:
                print(f"[{reg_no}] [Thread] User took too long. Aborting.")
                return

            if user_msg.get('action') == 'kill':
                return

            captcha_text = user_msg.get('captcha_text')
            print(f"[{reg_no}] [Thread] Got captcha: '{captcha_text}'. Submitting...")
            captcha_input.fill(captcha_text)
            captcha_input.press('Enter')

        else:
            print(f"[{reg_no}] [Thread] No Captcha needed. Submitting...")
            page.press('input[type="password"]', 'Enter')
            out_queue.put({'requires_captcha': False})

        print(f"[{reg_no}] [Thread] Waiting for dashboard...")
        try:
            page.wait_for_selector("text=Attendance Details, a:has-text('Attendance Details'), .navbar-brand >> visible=true", timeout=40000)
        except:
            print(f"[{reg_no}] Dashboard timeout. Checking for errors...")
            error_el = page.locator("span, td, div", has_text="Invalid").first
            if error_el.count() > 0:
                error_text = error_el.inner_text().strip()
                out_queue.put({'success': False, 'error': f'Portal Error: {error_text}'})
                return
            print(f"[{reg_no}] Attempting direct URL fallback...")

        print(f"[{reg_no}] [Thread] Navigating to Attendance...")
        try:
            attendance_link = page.locator("a:has-text('Attendance Details'), #link_8").first
            attendance_link.click(timeout=10000)
        except:
            print(f"[{reg_no}] Could not click link. Using direct URL...")
            page.goto("https://sp.srmist.edu.in/srmiststudentportal/students/report/viewAttendance.jsp")

        print(f"[{reg_no}] [Thread] Waiting for attendance table...")
        try:
            page.wait_for_selector("table, #divMainDetails table", timeout=20000)
        except:
            out_queue.put({'success': False, 'error': 'Attendance table never loaded. Session may have expired.'})
            return

        print(f"[{reg_no}] [Thread] Parsing attendance rows...")
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
                            'courseTitle': subject_name,
                            'attended': int(attended_hours_str),
                            'total': int(max_hours_str)
                        })
                except Exception as parse_err:
                    print(f"Row skipped: {parse_err}")

        end_time = time.time()
        print(f"[{reg_no}] Sync done in {round(end_time - start_time, 2)}s. {len(live_scraped_data)} courses found.")

        if len(live_scraped_data) > 0:
            profile_data = {
                "name": "STUDENT",
                "regNo": reg_no.upper(),
                "course": "B.Tech",
                "semester": "Current"
            }
            out_queue.put({
                'success': True,
                'profile': profile_data,
                'data': live_scraped_data,
                'marks': [],
                'timetable': {"1": [], "2": [], "3": [], "4": [], "5": []},
                'sync_time': round(end_time - start_time, 2)
            })
        else:
            out_queue.put({'success': False, 'error': 'Table found but no attendance data. Try again.'})

    except Exception as fn_err:
        print(f"[{reg_no}] Critical failure: {str(fn_err)}")
        out_queue.put({'success': False, 'error': f'Backend error: {str(fn_err)}'})
    finally:
        print(f"[{reg_no}] [Thread] Tearing down browser.")
        if browser:
            try: browser.close()
            except: pass
        if p:
            try: p.stop()
            except: pass



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

    batch = data.get('batch', 1)
    t = threading.Thread(target=playwright_worker, args=(session_id, reg_no, pwd, batch, in_queue, out_queue))
    t.daemon = True
    t.start()
    
    return jsonify({'success': True, 'session_id': session_id, 'status': 'processing'})

@app.route('/api/session_status/<session_id>', methods=['GET'])
def session_status(session_id):
    with session_lock:
        if session_id in completed_sessions:
            return jsonify(completed_sessions.pop(session_id))
        session_data = active_sessions.get(session_id)
        
    if not session_data:
        return jsonify({'success': False, 'error': 'Session invalid or expired.'}), 404

    try:
        result = session_data['out_queue'].get_nowait()
        if result.get('requires_captcha'):
            return jsonify({
                'success': True,
                'status': 'requires_captcha',
                'session_id': session_id,
                'captcha_base64': result.get('captcha_base64')
            })
        else:
            if result.get('success'):
                raw_reg = session_data['reg_no']
                net_id = raw_reg.split('@')[0] if '@' in raw_reg else raw_reg
                save_student_to_db(net_id, 'Student', net_id.upper(), result.get('data', []), [])
            
            result['status'] = 'completed'
            with session_lock:
                completed_sessions[session_id] = result
                active_sessions.pop(session_id, None)
            return jsonify(result)
            
    except queue.Empty:
        return jsonify({'success': True, 'status': 'processing', 'session_id': session_id})

@app.route('/api/submit_captcha', methods=['POST'])
def submit_captcha():
    data = request.json
    session_id = data.get('session_id')
    captcha_text = data.get('captcha_text')

    with session_lock:
        session_data = active_sessions.get(session_id)
        
    if not session_data:
        return jsonify({'success': False, 'error': 'Session timed out.'}), 400

    session_data['in_queue'].put({'action': 'submit', 'captcha_text': captcha_text})
    
    return jsonify({'success': True, 'status': 'processing', 'session_id': session_id})

# ==========================================
# DATABASE ROUTES
# ==========================================

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

@app.route('/api/cabs', methods=['GET'])
def get_cabs():
    conn = get_db()
    
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001)) # Changed to 5001 to avoid VS Code clash
    app.run(host='0.0.0.0', port=port, debug=True)

# ==========================================
# OVERTAKE PHASE ROUTES
# ==========================================

@app.get('/api/polls/active')
def get_active_poll():
    conn = get_db()
    try:
        if DATABASE_URL:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM campus_polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    cur.execute("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id = %s GROUP BY option_index", (row['id'],))
                    votes = {r['option_index']: r['count'] for r in cur.fetchall()}
                    row = dict(row)
                    row['votes'] = votes
                    return jsonify(row)
        else:
            row = conn.execute("SELECT * FROM campus_polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                row = dict(row)
                votes_rows = conn.execute("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id = ? GROUP BY option_index", (row['id'],)).fetchall()
                row['votes'] = {r['option_index']: r['count'] for r in votes_rows}
                return jsonify(row)
                
        # Default seeded poll if empty
        default_poll = {
            'id': 1, 'question': 'Is the Mess Food edible today?',
            'options': json.dumps(["Yes, surprisingly!", "No, skip it.", "Safe to Bunk!"]),
            'votes': {}, 'is_active': 1, 'created_at': datetime.now().isoformat()
        }
        return jsonify(default_poll)
    finally:
        conn.close()

@app.post('/api/polls/vote')
def vote_poll():
    d = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        net_id = d.get('net_id', 'Anonymous')
        if DATABASE_URL:
            cur.execute("SELECT id FROM poll_votes WHERE poll_id = %s AND net_id = %s", (d['poll_id'], net_id))
        else:
            cur.execute("SELECT id FROM poll_votes WHERE poll_id = ? AND net_id = ?", (d['poll_id'], net_id))
            
        if cur.fetchone():
            return jsonify({"success": False, "error": "Already voted"}), 400
            
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if DATABASE_URL:
            cur.execute("INSERT INTO poll_votes (poll_id, net_id, option_index, created_at) VALUES (%s, %s, %s, %s)",
                       (d['poll_id'], net_id, d['option_index'], now))
        else:
            cur.execute("INSERT INTO poll_votes (poll_id, net_id, option_index, created_at) VALUES (?, ?, ?, ?)",
                       (d['poll_id'], net_id, d['option_index'], now))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@app.get('/api/placements')
def get_placements():
    conn = get_db()
    try:
        if DATABASE_URL:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM placements ORDER BY id DESC LIMIT 50")
                rows = cur.fetchall()
        else:
            rows = [dict(r) for r in conn.execute("SELECT * FROM placements ORDER BY id DESC LIMIT 50").fetchall()]
        return jsonify(list(rows))
    finally:
        conn.close()

@app.post('/api/placements/submit')
def submit_placement():
    d = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("INSERT INTO placements (company_name, role, ctc, visit_date, experience, submitted_by, net_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                       (d['company_name'], d.get('role'), d.get('ctc'), d.get('visit_date'), d.get('experience'), d.get('submitted_by'), d.get('net_id')))
        else:
            cur.execute("INSERT INTO placements (company_name, role, ctc, visit_date, experience, submitted_by, net_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (d['company_name'], d.get('role'), d.get('ctc'), d.get('visit_date'), d.get('experience'), d.get('submitted_by'), d.get('net_id')))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@app.get('/api/lostfound')
def get_lostfound():
    conn = get_db()
    try:
        if DATABASE_URL:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lost_found ORDER BY id DESC LIMIT 50")
                rows = cur.fetchall()
        else:
            rows = [dict(r) for r in conn.execute("SELECT * FROM lost_found ORDER BY id DESC LIMIT 50").fetchall()]
        return jsonify(list(rows))
    finally:
        conn.close()

@app.post('/api/lostfound/submit')
def submit_lostfound():
    d = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if DATABASE_URL:
            cur.execute("INSERT INTO lost_found (item_name, description, location, type, contact_phone, net_id, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                       (d['item_name'], d.get('description'), d.get('location'), d['type'], d.get('contact_phone'), d.get('net_id'), now))
        else:
            cur.execute("INSERT INTO lost_found (item_name, description, location, type, contact_phone, net_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (d['item_name'], d.get('description'), d.get('location'), d['type'], d.get('contact_phone'), d.get('net_id'), now))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()
