
import time
import threading
import queue
import os
import re
import sqlite3
import json
import requests
import uuid
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response, send_file
from flask_compress import Compress

from collections import defaultdict
import time

# --- ANTI-SCRAPING PROTECTIONS ---
API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "srm-hub-protected-x9f2")
ip_rate_limits = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 30
RATE_LIMIT_WINDOW = 60 # seconds

def is_rate_limited(ip):
    now = time.time()
    # clean old timestamps
    ip_rate_limits[ip] = [t for t in ip_rate_limits[ip] if now - t < RATE_LIMIT_WINDOW]
    if len(ip_rate_limits[ip]) >= MAX_LOGIN_ATTEMPTS:
        return True
    ip_rate_limits[ip].append(now)
    return False
from functools import lru_cache
import base64
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__, static_folder='.')
CORS(app)
Compress(app)

sync_jobs = {}



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


@app.post("/api/campusweb_sync")
def campusweb_sync():
    data = request.json
    net_id = data.get('net_id')
    password = data.get('password')
    if not net_id or not password:
        return jsonify({"success": False, "error": "Missing credentials"}), 400
        
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if is_rate_limited(client_ip, net_id):
        return jsonify({"success": False, "error": "Too many sync attempts. Please wait a minute."}), 429
        
    try:
        import cw_scraper
        res = cw_scraper.scrape_campusweb(net_id, password)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def get_db():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def strip_base64_images(items, table_name):
    col = 'image_url' # all these tables use image_url
    for item in items:
        if col in item and item[col] and item[col].startswith('data:image'):
            item[col] = f"/api/image/{table_name}/{item['id']}"
    return items

def clean_net_id(val):
    if not val:
        return ''
    return str(val).split('@')[0].strip().lower()

@app.route('/api/track_open', methods=['POST'])
def track_open():
    data = request.json or {}
    net_id = data.get('net_id', '').strip().lower()
    if not net_id:
        return jsonify({'success': False})
    
    conn = get_db()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    try:
        if DATABASE_URL:
            cur.execute("UPDATE students SET last_opened_at = %s WHERE net_id = %s", (now, net_id))
        else:
            cur.execute("UPDATE students SET last_opened_at = ? WHERE net_id = ?", (now, net_id))
        conn.commit()
    except Exception as e:
        pass
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/image/<table>/<int:item_id>', methods=['GET'])
def get_image_data(table, item_id):
    valid_tables = {'class_chats': 'image_url', 'marketplace': 'image_url', 'club_events': 'image_url', 'lost_found': 'image_url'}
    if table not in valid_tables: return "Invalid table", 400
    
    conn = get_db()
    cur = conn.cursor()
    col = valid_tables[table]
    try:
        if DATABASE_URL:
            cur.execute(f"SELECT {col} FROM {table} WHERE id = %s", (item_id,))
        else:
            cur.execute(f"SELECT {col} FROM {table} WHERE id = ?", (item_id,))
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
        
    if not row or not row[0] or not str(row[0]).startswith('data:image'):
        return "Not found", 404
        
    try:
        header, encoded = str(row[0]).split(',', 1)
        mime_type = header.split(';')[0].split(':')[1]
        import base64
        from io import BytesIO
        img_bytes = base64.b64decode(encoded)
        response = send_file(BytesIO(img_bytes), mimetype=mime_type)
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response
    except Exception as e:
        return str(e), 400


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
        cur.execute('''CREATE TABLE IF NOT EXISTS music_hub (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, artist TEXT, audio_data TEXT NOT NULL, cover_data TEXT,
            uploaded_by TEXT, net_id TEXT, created_at TEXT, order_index INTEGER DEFAULT 0)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS music_logs (
            id SERIAL PRIMARY KEY, track_id INTEGER, title TEXT, artist TEXT, user_name TEXT, net_id TEXT, played_at TEXT)'''
        )
        cur.execute('''CREATE TABLE IF NOT EXISTS class_chats (
            id SERIAL PRIMARY KEY, section TEXT NOT NULL, sender_name TEXT, sender_net_id TEXT, message TEXT, image_url TEXT, deleted_for_all INTEGER DEFAULT 0, deleted_by TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS spotted_feed (
            id SERIAL PRIMARY KEY, message TEXT NOT NULL, likes INTEGER DEFAULT 0, net_id TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS wall_comments (
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL, message TEXT NOT NULL, author TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS spotted_comments (
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL, message TEXT NOT NULL, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS spotted_likes (
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL, net_id TEXT NOT NULL, UNIQUE(post_id, net_id))''')

        conn.commit()
        for table, col, ctype in [
            ('students', 'created_at', 'TEXT'),
            ('students', 'last_opened_at', 'TEXT'),
            ('music_hub', 'play_count', 'INTEGER DEFAULT 0')
        ]:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}")
                conn.commit()
            except Exception:
                conn.rollback()

        try:
            cur.execute("ALTER TABLE music_hub ADD COLUMN order_index INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            conn.rollback()

        try:
            cur.execute("ALTER TABLE music_hub ADD COLUMN lyrics TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found RENAME COLUMN item_name TO title")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN title TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN category TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN location TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN image_url TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN poster_name TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        for col, ctype in [('audio_url', 'TEXT'), ('deleted_for_all', 'INTEGER DEFAULT 0'), ('deleted_by', 'TEXT')]:
            try:
                cur.execute(f"ALTER TABLE class_chats ADD COLUMN {col} {ctype}")
                conn.commit()
            except Exception:
                conn.rollback()
        try:
            cur.execute("ALTER TABLE campus_wall ADD COLUMN net_id TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
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
        cur.execute('''CREATE TABLE IF NOT EXISTS music_hub (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, artist TEXT, audio_data TEXT NOT NULL, cover_data TEXT,
            uploaded_by TEXT, net_id TEXT, created_at TEXT, order_index INTEGER DEFAULT 0)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS music_logs (
            id SERIAL PRIMARY KEY, track_id INTEGER, title TEXT, artist TEXT, user_name TEXT, net_id TEXT, played_at TEXT)'''
        )
        cur.execute('''CREATE TABLE IF NOT EXISTS class_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT NOT NULL, sender_name TEXT, sender_net_id TEXT, message TEXT, image_url TEXT, deleted_for_all INTEGER DEFAULT 0, deleted_by TEXT, created_at TEXT, audio_url TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS spotted_feed (
            id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, likes INTEGER DEFAULT 0, net_id TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS wall_comments (
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL, message TEXT NOT NULL, author TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS spotted_comments (
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL, message TEXT NOT NULL, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS spotted_likes (
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL, net_id TEXT NOT NULL, UNIQUE(post_id, net_id))''')

        
        for table, col, ctype in [
            ('students', 'created_at', 'TEXT'),
            ('students', 'last_opened_at', 'TEXT'),
            ('music_hub', 'play_count', 'INTEGER DEFAULT 0')
        ]:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}")
                conn.commit()
            except Exception:
                conn.rollback()

        try:
            cur.execute("ALTER TABLE music_hub ADD COLUMN order_index INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            conn.rollback()

        try:
            cur.execute("ALTER TABLE music_hub ADD COLUMN lyrics TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found RENAME COLUMN item_name TO title")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE class_chats ADD COLUMN audio_url TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN title TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN category TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN location TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN image_url TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE lost_found ADD COLUMN poster_name TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            cur.execute("ALTER TABLE campus_wall ADD COLUMN net_id TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
    conn.commit()
    cur.close()
    conn.close()

init_db()

def save_student_to_db(net_id, name, register_no, att_data, marks_data, is_mock=False):
    try:
        # Calculate Attendance
        total_att = 0; total_cls = 0
        for sub in (att_data or []):
            try:
                # Handle cw_scraper format (conducted, absent, attended = pct)
                if 'conducted' in sub:
                    tot_val = float(sub.get('conducted', 0) or 0)
                    abs_val = float(sub.get('absent', 0) or 0)
                    att_val = tot_val - abs_val
                else:
                    att_val = float(sub.get('attended', 0) or 0)
                    tot_val = float(sub.get('total', 0) or 0)
                
                total_att += int(att_val)
                total_cls += int(tot_val)
            except: continue
        overall_att = round((total_att / total_cls) * 100, 1) if total_cls > 0 else 0.0

        # Calculate Est CGPA (Mimicking Frontend Logic EXACTLY)
        total_grade_points = 0
        total_credits = 0
        for sub in (marks_data or []):
            try:
                perf_string = sub.get('Test Performance') or sub.get('performance') or sub.get('marks') or ""
                
                matches = re.findall(r'([^/]+)/([0-9.]+)\s*\|\s*([0-9.]+)', perf_string)
                
                course_max = 0
                course_obtained = 0
                for test_name, max_str, obtained_str in matches:
                    try:
                        course_max += float(max_str)
                        course_obtained += float(obtained_str)
                    except ValueError:
                        pass
                
                if course_max > 0:
                    percent = (course_obtained / course_max) * 100
                    gp = 0
                    if percent >= 90: gp = 10
                    elif percent >= 80: gp = 9
                    elif percent >= 70: gp = 8
                    elif percent >= 60: gp = 7
                    elif percent >= 50: gp = 6
                    elif percent >= 40: gp = 5
                    
                    total_grade_points += (gp * 3)
                    total_credits += 3
            except Exception as e:
                continue
                
        cgpa = round((total_grade_points / total_credits), 2) if total_credits > 0 else 0.0

        conn = get_db()
        cur = conn.cursor()
        if is_mock:
            update_att = "overall_attendance=COALESCE(students.overall_attendance, EXCLUDED.overall_attendance)"
            update_cgpa = "est_cgpa=COALESCE(students.est_cgpa, EXCLUDED.est_cgpa)"
            update_att_lite = "overall_attendance=COALESCE(students.overall_attendance, excluded.overall_attendance)"
            update_cgpa_lite = "est_cgpa=COALESCE(students.est_cgpa, excluded.est_cgpa)"
        else:
            update_att = "overall_attendance=EXCLUDED.overall_attendance"
            update_cgpa = "est_cgpa=EXCLUDED.est_cgpa"
            update_att_lite = "overall_attendance=excluded.overall_attendance"
            update_cgpa_lite = "est_cgpa=excluded.est_cgpa"

        if DATABASE_URL:
            cur.execute(f'''
                INSERT INTO students (net_id, name, register_no, overall_attendance, est_cgpa, synced_at, created_at, last_opened_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(net_id) DO UPDATE SET
                    name=EXCLUDED.name, register_no=EXCLUDED.register_no,
                    {update_att}, {update_cgpa},
                    synced_at=EXCLUDED.synced_at
            ''', (net_id.lower(), name, register_no.upper(), overall_att, cgpa, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
        else:
            cur.execute(f'''
                INSERT INTO students (net_id, name, register_no, overall_attendance, est_cgpa, synced_at, created_at, last_opened_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(net_id) DO UPDATE SET
                    name=excluded.name, register_no=excluded.register_no,
                    {update_att_lite}, {update_cgpa_lite},
                    synced_at=excluded.synced_at
            ''', (net_id.lower(), name, register_no.upper(), overall_att, cgpa, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] save_student_to_db error: {e}")




def scrape_academia_worker(reg_no, pwd, batch, out_queue):
    from fast_scraper_adapter import run_fast_scraper
    run_fast_scraper(reg_no, pwd, out_queue)





@app.route('/api/start_session', methods=['POST'])


def start_session():
    data = request.json

    # 1. API Key Check
    client_key = request.headers.get('X-App-Key')
    if client_key != API_SECRET_KEY:
        return jsonify({'success': False, 'error': 'Unauthorized: Invalid API Key'}), 403

    # 2. Rate Limiting Check
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()
    if is_rate_limited(client_ip):
        return jsonify({'success': False, 'error': 'Too many requests. Please try again later.'}), 429

    sync_id = str(uuid.uuid4())
    sync_jobs[sync_id] = {'status': 'processing', 'timestamp': time.time()}
    
    def worker_wrapper(reg_no, pwd, batch, sid):
        import concurrent.futures
        try:
            import cw_scraper
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
            
            def run_academia():
                out_queue = queue.Queue()
                scrape_academia_worker(reg_no, pwd, batch, out_queue)
                return out_queue.get(timeout=55)
            
            # Run BOTH in parallel at the same time
            future_ac = executor.submit(run_academia)
            future_cw = executor.submit(cw_scraper.scrape_campusweb, reg_no, pwd)
            
            # 1. Wait for Academia FIRST (Cold starts with Unified Timetable can take 20-30s)
            result = None
            try:
                result = future_ac.result(timeout=50)
            except Exception as e:
                print(f"[{reg_no}] Academia failed or timed out: {e}")
            
            # 2. Now check CampusWeb - it's been running in parallel this whole time
            cw_res = None
            try:
                # Give it up to 10 more seconds if Academia finished early
                cw_res = future_cw.result(timeout=10)
            except Exception as e:
                print(f"[{reg_no}] CampusWeb slow/failed (non-blocking): {e}")
            
            # Release executor immediately
            executor.shutdown(wait=False)
            
            # Build final result
            if result is None or not result.get('success'):
                result = result or {}
                ac_err = result.get('error', '')
                ac_err_lower = ac_err.lower()
                
                # STRICT AUTH: If Academia explicitly rejected the password, DO NOT fallback to CampusWeb!
                # (CampusWeb API insecurely caches data without verifying passwords)
                if 'password' in ac_err_lower or 'credential' in ac_err_lower or 'wrong email' in ac_err_lower or 'invalid' in ac_err_lower:
                    sync_jobs[sid] = {'status': 'failed', 'result': {'success': False, 'error': "Wrong NetID or Password. Please try again."}, 'timestamp': time.time()}
                    return
                
                result['success'] = True if (cw_res and cw_res.get('success')) else False
                if not result.get('success'):
                    cw_err = (cw_res or {}).get('error', '')
                    
                    final_err = "Login Failed. Invalid NetID or Password."
                    if 'password' in cw_err.lower():
                        final_err = "Wrong NetID or Password. Please try again."
                    elif '@srmist.edu.in' not in reg_no.lower():
                        final_err = "Please include @srmist.edu.in in your NetID."
                    elif 'network' in ac_err.lower() or 'timeout' in ac_err.lower() or 'time out' in ac_err.lower() or 'network' in cw_err.lower():
                        final_err = "Poor network connectivity. The university servers took too long to respond."
                    elif ac_err:
                        final_err = f"University Server Error: {ac_err}"
                    
                    sync_jobs[sid] = {'status': 'failed', 'result': {'success': False, 'error': final_err}, 'timestamp': time.time()}
                    return
            
            # Override with CampusWeb attendance & marks if available
            if cw_res and cw_res.get('success'):
                if not result.get('profile'):
                    raw_reg = reg_no or ''
                    net_id = raw_reg.split('@')[0].upper()
                    result['profile'] = {'name': 'STUDENT (Academia Offline)', 'regNo': net_id, 'course': 'Partial Data Synced', 'department': ''}
                if cw_res.get('attendance') and len(cw_res.get('attendance')) > 0:
                    result['data'] = cw_res.get('attendance')
                    result['is_mock_attendance'] = False
                if cw_res.get('marks') and len(cw_res.get('marks')) > 0:
                    result['marks'] = cw_res.get('marks')
            
            if result.get('success'):
                profile = result.get('profile', {})
                raw_reg = reg_no or ''
                net_id = raw_reg.split('@')[0]
                register_no = profile.get('reg_no', net_id.upper())
                name = profile.get('name', 'Student')
                save_student_to_db(net_id, name, register_no, result.get('data', []), result.get('marks', []), is_mock=result.get('is_mock_attendance', False))
            sync_jobs[sid] = {'status': 'completed', 'result': result, 'timestamp': time.time()}
        except queue.Empty:
            sync_jobs[sid] = {'status': 'failed', 'result': {'success': False, 'error': 'Background task crashed or timed out.'}, 'timestamp': time.time()}
        except Exception as e:
            sync_jobs[sid] = {'status': 'failed', 'result': {'success': False, 'error': f'Background task exception: {str(e)}'}, 'timestamp': time.time()}

    t = threading.Thread(target=worker_wrapper, args=(data.get('regNo'), data.get('pwd'), data.get('batch', 1), sync_id))
    t.start()
    return jsonify({'success': True, 'sync_id': sync_id})

@app.route('/api/sync_status/<sync_id>', methods=['GET'])
def sync_status(sync_id):
    job = sync_jobs.get(sync_id)
    if not job:
        return jsonify({'status': 'failed', 'result': {'success': False, 'error': 'Job not found or expired.'}})
    
    if job['status'] == 'completed' or job['status'] == 'failed':
        res = sync_jobs.pop(sync_id, None)
        return jsonify({'status': res['status'], 'result': res.get('result')})
    
    return jsonify({'status': 'processing'})

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
            cur.execute('SELECT name, net_id, register_no, overall_attendance FROM students ORDER BY overall_attendance DESC')
            rows = cur.fetchall()
    else:
        rows = [dict(r) for r in conn.execute('SELECT name, net_id, register_no, overall_attendance FROM students ORDER BY overall_attendance DESC').fetchall()]
    conn.close()
    return jsonify(list(rows))

@app.route('/api/leaderboard/marks', methods=['GET'])
def leaderboard_marks():
    conn = get_db()
    if DATABASE_URL:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT name, net_id, register_no, est_cgpa FROM students ORDER BY est_cgpa DESC')
            rows = cur.fetchall()
    else:
        rows = [dict(r) for r in conn.execute('SELECT name, net_id, register_no, est_cgpa FROM students ORDER BY est_cgpa DESC').fetchall()]
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

@app.route('/api/projects/delete/<int:item_id>', methods=['DELETE'])
def delete_project(item_id):
    data = request.json or {}
    net_id = data.get('net_id', '').lower().strip()
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("SELECT net_id FROM projects WHERE id = %s", (item_id,))
        else:
            cur.execute("SELECT net_id FROM projects WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        owner_id = (row[0] if DATABASE_URL else dict(row).get('net_id', '')).lower().strip()
        if owner_id != net_id:
            return jsonify({'success': False, 'error': 'You can only delete your own projects'}), 403

        if DATABASE_URL:
            cur.execute("DELETE FROM projects WHERE id = %s", (item_id,))
        else:
            cur.execute("DELETE FROM projects WHERE id = ?", (item_id,))
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
    return jsonify(strip_base64_images(projects, 'marketplace'))

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

        owner_id = (row[0] if DATABASE_URL else dict(row).get('net_id', '') or '')
        if clean_net_id(owner_id) != clean_net_id(net_id):
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
        
        if posts:
            post_ids = [p['id'] for p in posts]
            placeholders = ','.join(['%s' if DATABASE_URL else '?'] * len(post_ids))
            cur.execute(f"SELECT * FROM wall_comments WHERE post_id IN ({placeholders}) ORDER BY id ASC", tuple(post_ids))
            comments = [dict(c) for c in cur.fetchall()]
            for p in posts:
                p['comments'] = [c for c in comments if c['post_id'] == p['id']]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM campus_wall ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        posts = [dict(row) for row in rows]
        
        if posts:
            post_ids = [p['id'] for p in posts]
            placeholders = ','.join(['%s' if DATABASE_URL else '?'] * len(post_ids))
            cur.execute(f"SELECT * FROM wall_comments WHERE post_id IN ({placeholders}) ORDER BY id ASC", tuple(post_ids))
            comments = [dict(c) for c in cur.fetchall()]
            for p in posts:
                p['comments'] = [c for c in comments if c['post_id'] == p['id']]
    
    cur.close()
    conn.close()
    return jsonify(posts)

@app.route('/api/wall/submit', methods=['POST'])
def submit_wall():
    data = request.json or {}
    if not data or not data.get('message'):
        return jsonify({'success': False, 'error': 'Message required'}), 400

    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    net_id = (data.get('net_id') or '').strip().lower()

    try:
        if DATABASE_URL:
            cur.execute("INSERT INTO campus_wall (message, author, net_id, created_at) VALUES (%s, %s, %s, %s)",
                       (data.get('message'), data.get('author', 'Anonymous'), net_id, now_str))
        else:
            cur.execute("INSERT INTO campus_wall (message, author, net_id, created_at) VALUES (?, ?, ?, ?)",
                       (data.get('message'), data.get('author', 'Anonymous'), net_id, now_str))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({'success': True})

@app.route('/api/wall/delete/<int:post_id>', methods=['DELETE', 'POST'])
def delete_wall(post_id):
    data = request.json or {}
    net_id = (data.get('net_id') or '').strip().lower()
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("SELECT net_id FROM campus_wall WHERE id = %s", (post_id,))
        else:
            cur.execute("SELECT net_id FROM campus_wall WHERE id = ?", (post_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        owner_id = (row[0] if DATABASE_URL else dict(row).get('net_id', '') or '')
        if clean_net_id(owner_id) != clean_net_id(net_id):
            return jsonify({'success': False, 'error': 'You can only delete your own posts'}), 403

        if DATABASE_URL:
            cur.execute("DELETE FROM wall_comments WHERE post_id = %s", (post_id,))
            cur.execute("DELETE FROM campus_wall WHERE id = %s", (post_id,))
        else:
            cur.execute("DELETE FROM wall_comments WHERE post_id = ?", (post_id,))
            cur.execute("DELETE FROM campus_wall WHERE id = ?", (post_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


@app.route('/api/wall/comment/<int:post_id>', methods=['POST'])
def submit_wall_comment(post_id):
    data = request.json
    if not data or not data.get('message'): return jsonify({'success': False, 'error': 'Message required'}), 400
    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    author = data.get('author', 'Anonymous Fox').strip()
    try:
        if DATABASE_URL:
            cur.execute("INSERT INTO wall_comments (post_id, message, author, created_at) VALUES (%s, %s, %s, %s)",
                        (post_id, data['message'].strip(), author, now_str))
        else:
            cur.execute("INSERT INTO wall_comments (post_id, message, author, created_at) VALUES (?, ?, ?, ?)",
                        (post_id, data['message'].strip(), author, now_str))
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

        owner_id = (row[0] if DATABASE_URL else dict(row).get('net_id', '') or '')
        if clean_net_id(owner_id) != clean_net_id(net_id):
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
    return jsonify(strip_base64_images(events, 'club_events'))

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
    return jsonify(strip_base64_images(items, 'lost_found'))

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

        owner_id = (row[0] if DATABASE_URL else dict(row).get('net_id', '')).lower().strip()
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

# --- MUSIC LOUNGE ROUTES ---

@app.route('/api/music', methods=['GET'])
def get_music():
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, title, artist, cover_data, uploaded_by, net_id, created_at, lyrics, CASE WHEN video_data IS NOT NULL THEN 1 ELSE 0 END as has_video FROM music_hub ORDER BY order_index ASC, created_at DESC")
    else:
        cur = conn.cursor()
        cur.execute("SELECT id, title, artist, cover_data, uploaded_by, net_id, created_at, lyrics, CASE WHEN video_data IS NOT NULL THEN 1 ELSE 0 END as has_video FROM music_hub ORDER BY order_index ASC, created_at DESC")
    
    rows = cur.fetchall()
    items = []
    for r in rows:
        row = dict(r)
        c_data = row.get('cover_data')
        if c_data:
            if str(c_data).startswith('http'):
                row['cover_url'] = c_data
            else:
                row['cover_url'] = f"/api/music/cover/{row['id']}"
        else:
            row['cover_url'] = None
        row.pop('cover_data', None)
        items.append(row)

    cur.close()
    conn.close()
    return jsonify(strip_base64_images(items, 'lost_found'))

import base64
from flask import Response

@app.route('/api/music/cover/<int:track_id>', methods=['GET'])
def get_music_cover(track_id):
    conn = get_db()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute("SELECT cover_data FROM music_hub WHERE id = %s", (track_id,))
    else:
        cur.execute("SELECT cover_data FROM music_hub WHERE id = ?", (track_id,))
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row and row[0]:
        c_data = row[0]
        if c_data.startswith('data:image'):
            try:
                header, encoded = c_data.split(',', 1)
                mime_type = header.split(':')[1].split(';')[0]
                decoded = base64.b64decode(encoded)
                return Response(decoded, mimetype=mime_type, headers={'Cache-Control': 'public, max-age=31536000'})
            except Exception:
                pass
    return Response(status=404)


@app.route('/api/music/video/<int:track_id>', methods=['GET'])
def get_music_video(track_id):
    conn = get_db()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute("SELECT video_data FROM music_hub WHERE id = %s", (track_id,))
    else:
        cur.execute("SELECT video_data FROM music_hub WHERE id = ?", (track_id,))
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row and row[0]:
        v_data = row[0]
        if v_data.startswith('http'):
            # Directly redirect to Supabase CDN for massive bandwidth savings
            from flask import redirect
            return redirect(v_data)
        elif v_data.startswith('data:video'):
            try:
                header, encoded = v_data.split(',', 1)
                mime_type = header.split(':')[1].split(';')[0]
                decoded = base64.b64decode(encoded)
                # Stream it natively to save bandwidth
                return Response(decoded, mimetype=mime_type, headers={'Cache-Control': 'public, max-age=31536000', 'Accept-Ranges': 'bytes'})
            except Exception:
                pass
    return Response(status=404)

@app.route('/api/music/video/upload', methods=['POST'])
def upload_music_video():
    data = request.json or {}
    track_id = data.get('id')
    net_id = (data.get('net_id') or '').strip().lower()
    video_data = data.get('video_data')
    
    if not track_id or not video_data:
        return jsonify({'success': False, 'error': 'Missing required fields (track_id or video_data)'})
        
    conn = get_db()
    cur = conn.cursor()
    try:
        # Check ownership
        if DATABASE_URL:
            cur.execute("SELECT net_id, video_data FROM music_hub WHERE id = %s", (track_id,))
        else:
            cur.execute("SELECT net_id, video_data FROM music_hub WHERE id = ?", (track_id,))
            
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Track not found'})
            
        owner_id = (row[0] or '').strip().lower()
        has_video = bool(row[1])
        if has_video and owner_id and owner_id != net_id:
            return jsonify({'success': False, 'error': 'Unauthorized: This track already has a video. Only the original uploader can change it.'})
            
        # If the user uploaded a file, it comes as base64. We upload it to Supabase Storage!
        if video_data and video_data.startswith("data:"):
            import base64
            import requests
            import uuid
            
            try:
                b64_str = video_data.split(",")[1]
                video_bytes = base64.b64decode(b64_str)
                
                # Using the live keys
                SUPABASE_URL = "https://turnmciexwkrgloqfgit.supabase.co"
                SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY')
                
                if SUPABASE_KEY:
                    filename = f"video_{uuid.uuid4().hex[:12]}.mp4"
                    upload_url = f"{SUPABASE_URL}/storage/v1/object/music/{filename}"
                    
                    headers = {
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "apikey": SUPABASE_KEY,
                        "Content-Type": "video/mp4"
                    }
                    
                    res = requests.post(upload_url, headers=headers, data=video_bytes)
                    if res.status_code == 200:
                        # Replace the giant base64 string with just the URL!
                        video_data = f"{SUPABASE_URL}/storage/v1/object/public/music/{filename}"
                    else:
                        print(f"Failed to upload video to storage: {res.text}")
            except Exception as e:
                print(f"Storage upload error: {str(e)}")

        # Update video
        if DATABASE_URL:
            cur.execute("UPDATE music_hub SET video_data = %s WHERE id = %s", (video_data, track_id))
        else:
            cur.execute("UPDATE music_hub SET video_data = ? WHERE id = ?", (video_data, track_id))
            
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()

@app.route('/api/music/audio/<int:track_id>', methods=['GET'])
def get_music_audio(track_id):
    conn = get_db()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute("SELECT audio_data FROM music_hub WHERE id = %s", (track_id,))
    else:
        cur.execute("SELECT audio_data FROM music_hub WHERE id = ?", (track_id,))
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row and row[0]:
        return jsonify({'audio_data': row[0]})
    return jsonify({'audio_data': None})

@lru_cache(maxsize=32)
def get_track_binary(track_id):
    conn = get_db()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute("SELECT audio_data FROM music_hub WHERE id = %s", (track_id,))
    else:
        cur.execute("SELECT audio_data FROM music_hub WHERE id = ?", (track_id,))
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if not row or not row[0]:
        return None, None
        
    data_url = row[0]
    try:
        header, encoded = data_url.split(",", 1)
        mime_type = header.split(";")[0].split(":")[1]
        binary_data = base64.b64decode(encoded)
        return binary_data, mime_type
    except Exception:
        return None, None

@app.route('/api/music/audio/<int:track_id>/stream', methods=['GET'])
def stream_music_audio(track_id):
    binary_data, mime_type = get_track_binary(track_id)
    if not binary_data:
        return "Not found", 404
        
    try:
        total_size = len(binary_data)
        range_header = request.headers.get('Range')
        
        if range_header:
            # Handle Range request for seeking and progressive playback
            byte_range = range_header.replace('bytes=', '').split('-')
            start = int(byte_range[0])
            end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else total_size - 1
            end = min(end, total_size - 1)
            chunk_size = end - start + 1
            
            resp = Response(
                binary_data[start:end+1],
                status=206,
                mimetype=mime_type
            )
            resp.headers['Content-Range'] = f'bytes {start}-{end}/{total_size}'
            resp.headers['Content-Length'] = str(chunk_size)
            resp.headers['Accept-Ranges'] = 'bytes'
            resp.headers['Cache-Control'] = 'public, max-age=3600'
            return resp
        else:
            resp = Response(
                binary_data,
                status=200,
                mimetype=mime_type
            )
            resp.headers['Content-Length'] = str(total_size)
            resp.headers['Accept-Ranges'] = 'bytes'
            resp.headers['Cache-Control'] = 'public, max-age=3600'
            return resp
    except Exception as e:
        return str(e), 500

@app.route('/api/music/submit', methods=['POST'])
def submit_music():
    data = request.json
    required = ['title', 'artist', 'audio_data', 'uploaded_by', 'net_id']
    if not all(k in data for k in required) or not data['audio_data']:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    audio_data = data.get('audio_data')
    
    # If the user uploaded a file, it comes as base64. We upload it to Supabase Storage!
    if audio_data and audio_data.startswith("data:"):
        import base64
        import requests
        import uuid
        
        try:
            b64_str = audio_data.split(",")[1]
            audio_bytes = base64.b64decode(b64_str)
            
            # Using the live keys
            SUPABASE_URL = "https://turnmciexwkrgloqfgit.supabase.co"
            SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY')
            
            if not SUPABASE_KEY:
                return jsonify({'success': False, 'error': 'Server missing SUPABASE_SECRET_KEY'}), 500
            
            filename = f"track_{uuid.uuid4().hex[:12]}.mp3"
            upload_url = f"{SUPABASE_URL}/storage/v1/object/music/{filename}"
            
            headers = {
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "apikey": SUPABASE_KEY,
                "Content-Type": "audio/mpeg"
            }
            
            res = requests.post(upload_url, headers=headers, data=audio_bytes)
            if res.status_code == 200:
                # Replace the giant base64 string with just the URL!
                audio_data = f"{SUPABASE_URL}/storage/v1/object/public/music/{filename}"
            else:
                return jsonify({'success': False, 'error': f'Failed to upload to storage: {res.text}'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': f'Storage upload error: {str(e)}'}), 500

    video_data = data.get('video_data')
    if video_data and video_data.startswith("data:"):
        import base64
        import requests
        import uuid
        try:
            b64_str = video_data.split(",")[1]
            video_bytes = base64.b64decode(b64_str)
            SUPABASE_URL = "https://turnmciexwkrgloqfgit.supabase.co"
            SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY')
            if SUPABASE_KEY:
                v_filename = f"video_{uuid.uuid4().hex[:12]}.mp4"
                v_upload_url = f"{SUPABASE_URL}/storage/v1/object/music/{v_filename}"
                v_headers = {
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "apikey": SUPABASE_KEY,
                    "Content-Type": "video/mp4"
                }
                v_res = requests.post(v_upload_url, headers=v_headers, data=video_bytes)
                if v_res.status_code == 200:
                    video_data = f"{SUPABASE_URL}/storage/v1/object/public/music/{v_filename}"
        except Exception as e:
            print(f"Submit music video storage error: {str(e)}")

    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO music_hub (title, artist, audio_data, cover_data, uploaded_by, net_id, created_at, video_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (data.get('title'), data.get('artist'), audio_data, data.get('cover_data'),
                  data.get('uploaded_by'), data.get('net_id'), now_str, video_data))
        else:
            cur.execute("""
                INSERT INTO music_hub (title, artist, audio_data, cover_data, uploaded_by, net_id, created_at, video_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (data.get('title'), data.get('artist'), audio_data, data.get('cover_data'),
                  data.get('uploaded_by'), data.get('net_id'), now_str, video_data))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/music/delete/<int:track_id>', methods=['DELETE'])
def delete_music(track_id):
    data = request.json or {}
    net_id = data.get('net_id', '').lower().strip()
    if not net_id: return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("SELECT net_id FROM music_hub WHERE id = %s", (track_id,))
        else:
            cur.execute("SELECT net_id FROM music_hub WHERE id = ?", (track_id,))
        row = cur.fetchone()
        if not row: return jsonify({'success': False, 'error': 'Track not found'}), 404
        
        owner_id = (row[0] if DATABASE_URL else dict(row).get('net_id', '')).lower().strip()
        if owner_id != net_id: return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        if DATABASE_URL:
            cur.execute("DELETE FROM music_hub WHERE id = %s", (track_id,))
        else:
            cur.execute("DELETE FROM music_hub WHERE id = ?", (track_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/music/reorder', methods=['POST'])
def reorder_music():
    data = request.json
    order = data.get('order', []) # array of track IDs
    if not order: return jsonify({'success': False, 'error': 'No order provided'})
    
    conn = get_db()
    cur = conn.cursor()
    try:
        for idx, track_id in enumerate(order):
            if DATABASE_URL:
                cur.execute("UPDATE music_hub SET order_index = %s WHERE id = %s", (idx, track_id))
            else:
                cur.execute("UPDATE music_hub SET order_index = ? WHERE id = ?", (idx, track_id))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

def call_gemini(prompt, file_base64=None, mime_type=None):
    if not GEMINI_API_KEY:
        return "System Notice: The AI Chatbot is currently unavailable because the GEMINI_API_KEY is not configured on the server."
    parts = [{"text": prompt}]
    if file_base64 and mime_type:
        b64_data = file_base64.split(',')[1] if ',' in file_base64 else file_base64
        parts.append({"inlineData": {"mimeType": mime_type, "data": b64_data}})
        
    payload = {"contents": [{"parts": parts}]}
    
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-preview-05-20", "gemini-1.5-flash", "gemini-2.0-flash-lite"]
    last_error = ""
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json', 'x-goog-api-key': GEMINI_API_KEY})
            data = response.json()
            if 'error' in data:
                err_msg = data['error'].get('message', str(data['error']))
                last_error = err_msg
                # Try the next model for these recoverable errors
                if 'not found' in err_msg.lower() or 'not supported' in err_msg.lower() or 'quota' in err_msg.lower() or 'rate limit' in err_msg.lower() or 'resource' in err_msg.lower():
                    continue
                return "API Error: " + err_msg
            if 'candidates' in data and data['candidates']:
                return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            last_error = str(e)
            
    return f"Error: All Gemini models failed. Last error: {last_error}"


@app.route('/api/music/play/<int:track_id>', methods=['POST'])
def record_music_play(track_id):
    data = request.json or {}
    user_name = data.get('user_name', 'Anonymous')
    net_id = data.get('net_id', '')
    now = datetime.utcnow().isoformat()
    
    conn = get_db()
    cur = conn.cursor()
    try:
        # Get track info
        if DATABASE_URL:
            cur.execute("SELECT title, artist FROM music_hub WHERE id = %s", (track_id,))
        else:
            cur.execute("SELECT title, artist FROM music_hub WHERE id = ?", (track_id,))
        track = cur.fetchone()
        
        if track:
            title, artist = track[0], track[1]
            if DATABASE_URL:
                cur.execute("UPDATE music_hub SET play_count = COALESCE(play_count, 0) + 1 WHERE id = %s", (track_id,))
                cur.execute("INSERT INTO music_logs (track_id, title, artist, user_name, net_id, played_at) VALUES (%s, %s, %s, %s, %s, %s)",
                            (track_id, title, artist, user_name, net_id, now))
            else:
                cur.execute("UPDATE music_hub SET play_count = COALESCE(play_count, 0) + 1 WHERE id = ?", (track_id,))
                cur.execute("INSERT INTO music_logs (track_id, title, artist, user_name, net_id, played_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (track_id, title, artist, user_name, net_id, now))
            conn.commit()
    except Exception as e:
        print(f"Error logging play: {e}")
    finally:
        cur.close()
        conn.close()
    return jsonify({"success": True})

@app.route('/api/music/lyrics', methods=['GET'])
def get_lyrics():
    artist = request.args.get('artist')
    title = request.args.get('title')
    if not artist or not title:
        return jsonify({'success': False, 'error': 'Missing parameters'})
    try:
        clean_title = re.sub(r'\(.*?\)', '', title).strip()
        clean_artist = artist.lower().split(' x ')[0].split(',')[0].split('&')[0].split(' feat.')[0].split(' ft.')[0].strip()
        
        # Try 1: Search API
        query = f"{clean_title} {clean_artist}"
        url = f"https://lrclib.net/api/search?q={urllib.parse.quote(query)}"
        resp = requests.get(url, timeout=8, headers={'User-Agent': 'SRM Student Hub/1.0'})
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                is_synced = bool(data[0].get('syncedLyrics'))
                lyrics = data[0].get('syncedLyrics') or data[0].get('plainLyrics')
                if lyrics:
                    return jsonify({'success': True, 'lyrics': lyrics, 'isSynced': is_synced})
        
        # Try 2: Direct get API (exact match)
        url2 = f"https://lrclib.net/api/get?artist_name={urllib.parse.quote(clean_artist)}&track_name={urllib.parse.quote(clean_title)}"
        resp2 = requests.get(url2, timeout=8, headers={'User-Agent': 'SRM Student Hub/1.0'})
        if resp2.status_code == 200:
            data2 = resp2.json()
            is_synced = bool(data2.get('syncedLyrics'))
            lyrics = data2.get('syncedLyrics') or data2.get('plainLyrics')
            if lyrics:
                return jsonify({'success': True, 'lyrics': lyrics, 'isSynced': is_synced})
        
        # Try 3: Search with just the title (sometimes artist name variation causes no match)
        url3 = f"https://lrclib.net/api/search?q={urllib.parse.quote(clean_title)}"
        resp3 = requests.get(url3, timeout=8, headers={'User-Agent': 'SRM Student Hub/1.0'})
        if resp3.status_code == 200:
            data3 = resp3.json()
            if isinstance(data3, list) and len(data3) > 0:
                is_synced = bool(data3[0].get('syncedLyrics'))
                lyrics = data3[0].get('syncedLyrics') or data3[0].get('plainLyrics')
                if lyrics:
                    return jsonify({'success': True, 'lyrics': lyrics, 'isSynced': is_synced})
                    
    except Exception as e:
        print(f"Lyrics fetch error: {e}")
    return jsonify({'success': False, 'error': 'Lyrics not found.'})

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    data = request.json
    user_msg = data.get('prompt', '')
    attendance = data.get('attendance', '[]')
    timetable = data.get('timetable', '{}')
    file_base64 = data.get('file_base64', None)
    mime_type = data.get('mime_type', None)
    if not user_msg and not file_base64: return jsonify({'success': False, 'error': 'Empty prompt'})
    
    sys_prompt = f"""You are SRM Hub AI, a friendly and helpful AI assistant for SRM University students built by Balaga Lalit Kishore. ONLY mention his social media (Instagram: @lalit._.kishore, LinkedIn: balagalalitkishore) IF explicitly asked.
You have access to the user's real-time academic data:
Attendance Data: {attendance}
Timetable Data: {timetable}

Features you support:
1. Bunk Strategy: If they ask about bunking or attendance, analyze their data. 75% is the strict minimum requirement. Calculate exactly how many classes they can afford to miss, and look at their timetable to advise them on which specific classes to skip today/tomorrow based on their margin.
2. Assignment Solver: If they ask you to solve an assignment, provide a highly accurate, well-formatted answer. If it requires images, you can use markdown `![image](url)` syntax if you have a source, or just provide the text. If they provided an image or PDF, analyze it accurately.
3. General Chat: Answer study questions, PYQs, coding doubts, and casual questions.

Be friendly, concise, and smart. DO NOT output the raw JSON data to the user, just use it to give intelligent, personalized advice.
User: {user_msg}"""
    
    reply = call_gemini(sys_prompt, file_base64, mime_type)
    if reply and not reply.startswith("Sorry, I could not generate a response"):
        return jsonify({'success': True, 'reply': reply})
    return jsonify({'success': False, 'error': reply or 'AI failed to respond.'})

@app.route('/api/ai/predict', methods=['POST'])
def ai_predict():
    data = request.json
    cgpa = data.get('cgpa', '')
    skills = data.get('skills', '')
    projects = data.get('projects', '')
    prompt = f"Act as a friendly Placement Predictor for SRM University students. Given CGPA: {cgpa}, Skills: {skills}, Projects: {projects}. Briefly list 3 target tech companies they are eligible for, and give a 6-month strict roadmap to secure a Super Dream offer. Keep it very concise."
    reply = call_gemini(prompt)
    if reply and not reply.startswith("Sorry, I could not generate a response"):
        return jsonify({'success': True, 'reply': reply})
    return jsonify({'success': False, 'error': reply or 'AI failed to predict.'})

# --- CHAT & SPOTTED ENDPOINTS ---

@app.route('/api/chat/<path:section>', methods=['GET'])
def get_chat(section):
    from urllib.parse import unquote
    section = unquote(section).strip()
    conn = get_db()
    
    # Fetch max 100 recent messages ordered strictly by id (most reliable across timezones)
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM (SELECT * FROM class_chats WHERE UPPER(TRIM(section)) = UPPER(TRIM(%s)) ORDER BY id DESC LIMIT 100) sub ORDER BY id ASC", (section,))
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM (SELECT * FROM class_chats WHERE UPPER(TRIM(section)) = UPPER(TRIM(?)) ORDER BY id DESC LIMIT 100) sub ORDER BY id ASC", (section,))
    rows = cur.fetchall()
    items = [dict(row) for row in rows]
    cur.close()
    conn.close()
    
    items = strip_base64_images(items, 'class_chats')
    return jsonify(items)

@app.route('/api/chat/<path:section>', methods=['POST'])
def post_chat(section):
    from urllib.parse import unquote
    section = unquote(section).strip()
    data = request.json or {}
    sender_name = (data.get('sender_name') or 'Anonymous').strip()
    sender_net_id = (data.get('sender_net_id') or '').lower().strip()
    message = (data.get('message') or '').strip()
    image_url = data.get('image_url') or ''
    audio_url = data.get('audio_url') or ''
    now = datetime.now().isoformat()
    
    if not message and not image_url and not audio_url:
        return jsonify({'success': False, 'error': 'Empty message'}), 400
        
    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("INSERT INTO class_chats (section, sender_name, sender_net_id, message, image_url, audio_url, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (section, sender_name, sender_net_id, message, image_url, audio_url, now))
            # Auto-trim to 200 messages per section to prevent DB bloat
            cur.execute("DELETE FROM class_chats WHERE UPPER(TRIM(section)) = UPPER(TRIM(%s)) AND id NOT IN (SELECT id FROM class_chats WHERE UPPER(TRIM(section)) = UPPER(TRIM(%s)) ORDER BY id DESC LIMIT 200)", (section, section))
        else:
            cur.execute("INSERT INTO class_chats (section, sender_name, sender_net_id, message, image_url, audio_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (section, sender_name, sender_net_id, message, image_url, audio_url, now))
            cur.execute("DELETE FROM class_chats WHERE UPPER(TRIM(section)) = UPPER(TRIM(?)) AND id NOT IN (SELECT id FROM class_chats WHERE UPPER(TRIM(section)) = UPPER(TRIM(?)) ORDER BY id DESC LIMIT 200)", (section, section))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/chat/delete/<int:msg_id>', methods=['POST'])
def delete_chat(msg_id):
    data = request.json or {}
    net_id = (data.get('net_id') or '').strip().lower()
    mode = data.get('mode', 'me') # 'me' or 'everyone'
    sender_name_client = (data.get('sender_name') or '').strip().lower()
    
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("SELECT sender_net_id, deleted_by, sender_name FROM class_chats WHERE id = %s", (msg_id,))
        else:
            cur.execute("SELECT sender_net_id, deleted_by, sender_name FROM class_chats WHERE id = ?", (msg_id,))
            
        row = cur.fetchone()
        if not row: return jsonify({'success': False, 'error': 'Message not found'}), 404
        
        sender = row[0] or ""
        deleted_by_list = row[1] or ""
        sender_name_db = (row[2] or "").strip().lower() if len(row) > 2 else ""
        
        if mode == 'everyone':
            sender_clean = clean_net_id(sender)
            net_clean = clean_net_id(net_id)
            is_owner = False
            if sender_clean and net_clean and sender_clean == net_clean:
                is_owner = True
            elif not sender_clean and sender_name_client and sender_name_db and sender_name_client == sender_name_db and sender_name_db != 'anonymous':
                is_owner = True
                
            if not is_owner:
                return jsonify({'success': False, 'error': 'Cannot delete others message for everyone'}), 403
            if DATABASE_URL:
                cur.execute("UPDATE class_chats SET deleted_for_all = 1, message = 'This message was deleted', image_url = '', audio_url = '' WHERE id = %s", (msg_id,))
            else:
                cur.execute("UPDATE class_chats SET deleted_for_all = 1, message = 'This message was deleted', image_url = '', audio_url = '' WHERE id = ?", (msg_id,))
        else:
            clean_list = [clean_net_id(x) for x in deleted_by_list.split(',') if clean_net_id(x)]
            net_clean = clean_net_id(net_id)
            if net_clean and net_clean not in clean_list:
                clean_list.append(net_clean)
            new_deleted = ",".join(clean_list)
            if DATABASE_URL:
                cur.execute("UPDATE class_chats SET deleted_by = %s WHERE id = %s", (new_deleted, msg_id))
            else:
                cur.execute("UPDATE class_chats SET deleted_by = ? WHERE id = ?", (new_deleted, msg_id))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/spotted', methods=['GET'])
def get_spotted():
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM spotted_feed ORDER BY created_at DESC LIMIT 100")
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM spotted_feed ORDER BY created_at DESC LIMIT 100")
    rows = cur.fetchall()
    items = [dict(row) for row in rows]
    cur.close()
    conn.close()
    return jsonify(strip_base64_images(items, 'lost_found'))

@app.route('/api/spotted', methods=['POST'])
def post_spotted():
    data = request.json
    message = data.get('message', '').strip()
    net_id = data.get('net_id', '').lower().strip()
    now = datetime.now().isoformat()
    if not message: return jsonify({'success': False, 'error': 'Empty message'})
    
    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("INSERT INTO spotted_feed (message, net_id, created_at) VALUES (%s, %s, %s)", (message, net_id, now))
        else:
            cur.execute("INSERT INTO spotted_feed (message, net_id, created_at) VALUES (?, ?, ?)", (message, net_id, now))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/spotted/delete/<int:post_id>', methods=['DELETE', 'POST'])
def delete_spotted(post_id):
    data = request.json or {}
    net_id = (data.get('net_id') or '').strip().lower()
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("SELECT net_id FROM spotted_feed WHERE id = %s", (post_id,))
        else:
            cur.execute("SELECT net_id FROM spotted_feed WHERE id = ?", (post_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        owner_id = (row[0] if DATABASE_URL else dict(row).get('net_id', '') or '')
        if clean_net_id(owner_id) != clean_net_id(net_id):
            return jsonify({'success': False, 'error': 'You can only delete your own posts'}), 403

        if DATABASE_URL:
            cur.execute("DELETE FROM spotted_comments WHERE post_id = %s", (post_id,))
            cur.execute("DELETE FROM spotted_likes WHERE post_id = %s", (post_id,))
            cur.execute("DELETE FROM spotted_feed WHERE id = %s", (post_id,))
        else:
            cur.execute("DELETE FROM spotted_comments WHERE post_id = ?", (post_id,))
            cur.execute("DELETE FROM spotted_likes WHERE post_id = ?", (post_id,))
            cur.execute("DELETE FROM spotted_feed WHERE id = ?", (post_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


@app.route('/api/spotted/comment/<int:post_id>', methods=['POST'])
def submit_spotted_comment(post_id):
    data = request.json
    if not data or not data.get('message'): return jsonify({'success': False, 'error': 'Message required'}), 400
    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if DATABASE_URL:
            cur.execute("INSERT INTO spotted_comments (post_id, message, created_at) VALUES (%s, %s, %s)",
                        (post_id, data['message'].strip(), now_str))
        else:
            cur.execute("INSERT INTO spotted_comments (post_id, message, created_at) VALUES (?, ?, ?)",
                        (post_id, data['message'].strip(), now_str))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/spotted/like/<int:post_id>', methods=['POST'])
def like_spotted(post_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("UPDATE spotted_feed SET likes = likes + 1 WHERE id = %s", (post_id,))
        else:
            cur.execute("UPDATE spotted_feed SET likes = likes + 1 WHERE id = ?", (post_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False})
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/ping')
def ping():
    return jsonify({"status": "ok"})


@app.route('/api/admin/db_size', methods=['GET'])
def admin_db_size():
    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute('''
                SELECT relname AS table_name,
                       pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
                       pg_total_relation_size(relid) AS size_bytes
                FROM pg_catalog.pg_statio_user_tables
                ORDER BY pg_total_relation_size(relid) DESC;
            ''')
            rows = cur.fetchall()
            return jsonify([{'table': r[0], 'size': r[1], 'bytes': r[2]} for r in rows])
        else:
            return jsonify({'error': 'Not Postgres'})
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        cur.close()
        conn.close()

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    secret_key = request.args.get('key')
    if secret_key != os.environ.get('ADMIN_SECRET_KEY', 'lalitadmin123'):
        return jsonify({"error": "Unauthorized. Invalid Admin Key."}), 403
        
    conn = get_db()
    cur = conn.cursor()
    
    # Get total registered students
    cur.execute("SELECT COUNT(*) FROM students")
    total_users = cur.fetchone()[0] if not DATABASE_URL else cur.fetchone()[0]
    
    # Get active users today (check both synced_at and last_opened_at)
    today_prefix = datetime.utcnow().isoformat()[:10]
    if DATABASE_URL:
        cur.execute("SELECT COUNT(*) FROM students WHERE synced_at LIKE %s OR last_opened_at LIKE %s", (f"{today_prefix}%", f"{today_prefix}%"))
    else:
        cur.execute("SELECT COUNT(*) FROM students WHERE synced_at LIKE ? OR last_opened_at LIKE ?", (f"{today_prefix}%", f"{today_prefix}%"))
    active_today = cur.fetchone()[0]

    def fetch_users(order_by):
        try:
            if DATABASE_URL:
                cur.execute(f"SELECT name, register_no, net_id, {order_by} FROM students WHERE {order_by} IS NOT NULL ORDER BY {order_by} DESC LIMIT 10")
            else:
                cur.execute(f"SELECT name, register_no, net_id, {order_by} FROM students WHERE {order_by} IS NOT NULL ORDER BY {order_by} DESC LIMIT 10")
            
            users = []
            for r in cur.fetchall():
                name = r[0] or 'Unknown'
                net_id = r[2] or ''
                reg_no = r[1]
                if not reg_no: reg_no = net_id.upper() if net_id else 'N/A'
                users.append({"name": name, "register_no": reg_no, "net_id": net_id, "timestamp": r[3] or "Never"})
            return users
        except Exception as e:
            return [{"name": "Error", "register_no": str(e), "net_id": "", "timestamp": ""}]

    recent_new_users = fetch_users('created_at')
    recent_synced_users = fetch_users('synced_at')
    recent_opened_users = fetch_users('last_opened_at')
    
    def get_count(table):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return cur.fetchone()[0]
        except:
            return 0

    cur.close()
    conn.close()

    return jsonify({
        "status": "success",
        "admin": "Lalit",
        "total_users": total_users,
        "active_today": active_today,
        "recent_new_users": recent_new_users,
        "recent_synced_users": recent_synced_users,
        "recent_opened_users": recent_opened_users,
        "total_chat_messages": get_count('class_chats'),
        "total_marketplace_items": get_count('marketplace'),
        "total_events": get_count('club_events'),
        "total_lost_and_found": get_count('lost_found')
    })

@app.route('/')
def serve_index():
    response = send_from_directory('.', 'index.html')
    response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return response
@app.route('/<path:path>')
def serve_static(path):
    safe_paths = ['index.html', 'manifest.json', 'sw.js', 'robots.txt', 'sitemap.xml']
    safe_folders = ['images', 'css', 'js', 'fonts', 'themes']
    is_safe = path in safe_paths or any(path.startswith(f"{f}/") for f in safe_folders)
    if not is_safe:
        return "Access Denied", 403
        
    response = send_from_directory('.', path)
    # Aggressively cache static assets to save bandwidth
    if path.startswith('images/') or path.endswith('.js') or path.endswith('.css'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif path == 'index.html':
        response.headers['Cache-Control'] = 'no-cache, must-revalidate' # always revalidate HTML
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))