import time
import threading
import queue
import os
import re
import sqlite3
import json
import requests
import uuid
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
    conn = sqlite3.connect(DB_PATH, timeout=20)
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
        cur.execute('''CREATE TABLE IF NOT EXISTS music_hub (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, artist TEXT, audio_data TEXT NOT NULL, cover_data TEXT,
            uploaded_by TEXT, net_id TEXT, created_at TEXT, order_index INTEGER DEFAULT 0)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS class_chats (
            id SERIAL PRIMARY KEY, section TEXT NOT NULL, sender_name TEXT, sender_net_id TEXT, message TEXT, image_url TEXT, deleted_for_all INTEGER DEFAULT 0, deleted_by TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS spotted_feed (
            id SERIAL PRIMARY KEY, message TEXT NOT NULL, likes INTEGER DEFAULT 0, net_id TEXT, created_at TEXT)''')
        conn.commit()
        try:
            cur.execute("ALTER TABLE music_hub ADD COLUMN order_index INTEGER DEFAULT 0")
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
        try:
            cur.execute("ALTER TABLE class_chats ADD COLUMN audio_url TEXT")
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
        cur.execute('''CREATE TABLE IF NOT EXISTS class_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT NOT NULL, sender_name TEXT, sender_net_id TEXT, message TEXT, image_url TEXT, deleted_for_all INTEGER DEFAULT 0, deleted_by TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS spotted_feed (
            id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, likes INTEGER DEFAULT 0, net_id TEXT, created_at TEXT)''')
        
        try:
            cur.execute("ALTER TABLE music_hub ADD COLUMN order_index INTEGER DEFAULT 0")
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
                att_val = float(sub.get('attended', 0) or 0)
                tot_val = float(sub.get('total', 0) or 0)
                total_att += int(att_val)
                total_cls += int(tot_val)
            except: continue
        overall_att = round((total_att / total_cls) * 100, 1) if total_cls > 0 else 0.0

        # Calculate Est CGPA (Mimicking Frontend Logic)
        grand_total_obtained = 0
        grand_total_max = 0
        for sub in (marks_data or []):
            try:
                perf_string = sub.get('Test Performance') or sub.get('performance') or sub.get('marks') or ""
                # Logic: extract max and obtained using regex matching `/([0-9.]+)\s*\|\s*([0-9.]+)/` (like frontend)
                # But it's easier: split by '|', if it has '/', left is obtained, right is max?
                # The frontend regex: `([A-Za-z0-9-]+)\/([0-9.]+)\s*\|\s*([0-9.]+)` 
                # This seems like it was matching something else, let's look at the regex:
                # regex = /([A-Za-z0-9-]+)\/([0-9.]+)\s*\|\s*([0-9.]+)/g
                # match[1] = testName, match[2] = max, match[3] = obtained? 
                
                # Let's write a simple python regex that extracts all numbers around '/' and '|'
                # The frontend is matching: "CT 1/50.0 | 45.0" or similar?
                # Wait, let's just use Python re module
                
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
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1920,1080'
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='Asia/Kolkata'
        )
        
        # --- STEALTH: Hide automation flags from Zoho bot detection ---
        context.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            // Fake plugins array
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' }
                ]
            });
            // Fake languages
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            // Hide automation-related Chrome properties
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        """)
        
        page = context.new_page()
        page.set_default_timeout(30000)

        if "@" not in reg_no: reg_no += "@srmist.edu.in"

        print(f"[{reg_no}] 1. Loading Academia...")
        try:
            page.goto("https://academia.srmist.edu.in/", wait_until="domcontentloaded", timeout=45000)
            print(f"[{reg_no}] 2. Page loaded. Current URL: {page.url}")
        except Exception as e:
            out_queue.put({'success': False, 'error': f'Portal failed to load: {str(e)}'})
            return

        def find_in_frames(selector, filter_text=None, filter_not_text=None):
            loc = page.locator(selector)
            if filter_text: loc = loc.filter(has_text=re.compile(filter_text, re.IGNORECASE))
            if filter_not_text: loc = loc.filter(has_not_text=re.compile(filter_not_text, re.IGNORECASE))
            try:
                if loc.count() > 0: return loc.first
            except: pass
            for frame in page.frames:
                try:
                    loc = frame.locator(selector)
                    if filter_text: loc = loc.filter(has_text=re.compile(filter_text, re.IGNORECASE))
                    if filter_not_text: loc = loc.filter(has_not_text=re.compile(filter_not_text, re.IGNORECASE))
                    if loc.count() > 0: return loc.first
                except: continue
            return None
            
        def check_and_handle_zoho_popups():
            try:
                current_url = page.url
                content_lower = ""
                try: content_lower = page.content().lower()
                except: pass
                
                if 'sessions-reminder' in current_url.lower() or 'terminate' in content_lower or 'session' in content_lower:
                    print(f"[{reg_no}] Zoho popup warning detected. URL: {current_url}")
                    terminate_btn = find_in_frames('button, a, div, span, input', filter_text='terminate')
                    if terminate_btn:
                        try:
                            print(f"[{reg_no}] Clicking terminate button...")
                            terminate_btn.click(force=True, timeout=2000)
                            page.wait_for_timeout(1000)
                            return True
                        except Exception as e:
                            print(f"[{reg_no}] Failed to click terminate: {e}")
                            
                    # If terminate fails or isn't there, try "Skip for now"
                    skip_btn = find_in_frames('button, a, div, span', filter_text='skip')
                    if skip_btn:
                        try:
                            print(f"[{reg_no}] Clicking skip button...")
                            skip_btn.click(force=True, timeout=2000)
                            page.wait_for_timeout(1000)
                            return True
                        except Exception as e:
                            print(f"[{reg_no}] Failed to click skip: {e}")
            except Exception as e:
                print(f"[{reg_no}] Error checking Zoho popups: {e}")
            return False
            
        # ============ LOGIN LOGIC (Zoho-aware) ============
        login_success = False
        try:
            for login_attempt in range(1, 4):
                print(f"[{reg_no}] Login Attempt {login_attempt} of 3...")
                # Wait for login page to fully render (Zoho redirect may take time)
                page.wait_for_timeout(1000)
                
                # Check if we are already logged in (meaning not on accounts.zoho or signin pages)
                current_url = page.url
                if 'accounts.zoho' not in current_url.lower() and 'signin' not in current_url.lower():
                    # Check if we have concurrent session warning page active
                    content_lower = ""
                    try: content_lower = page.content().lower()
                    except: pass
                    if 'sessions-reminder' in current_url.lower() or 'terminate' in content_lower:
                        print(f"[{reg_no}] Warn page visible at start of attempt {login_attempt}. Handling popups...")
                        check_and_handle_zoho_popups()
                        page.wait_for_timeout(1000)
                        current_url = page.url
                        
                    # Verify we are actually on the dashboard before assuming we're authenticated
                    dashboard_els = find_in_frames('#Welcome, .profile-header, #ul-main-menu, .user-name, #zohoviewer, .tab-title, [class*="profile"]')
                    
                    if dashboard_els and 'accounts.zoho' not in current_url.lower() and 'signin' not in current_url.lower() and 'sessions-reminder' not in current_url.lower():
                        print(f"[{reg_no}] Already authenticated (Attempt {login_attempt})! URL: {current_url}")
                        login_success = True
                        break

                # Strategy 1: Check if password field is already visible (Zoho remembered the username)
                pwd_input = find_in_frames('input[type="password"]')
                if pwd_input and pwd_input.is_visible():
                    print(f"[{reg_no}] Username already filled. Proceeding to password...")
                else:
                    # Look for email input field
                    email_input = None
                    for attempt in range(8):
                        if find_in_frames('#Welcome, .profile-header, #ul-main-menu, .user-name, #zohoviewer, .tab-title, [class*="profile"]'):
                            print(f"[{reg_no}] Dashboard loaded belatedly during email check (attempt {attempt+1}). Authenticated!")
                            login_success = True
                            break
                            
                        email_input = find_in_frames('input[name="LOGIN_ID"]')
                        if not email_input:
                            email_input = find_in_frames('input[type="email"]')
                        if not email_input:
                            # Strategy 3: Text input with login-like attributes in frames
                            for frame in page.frames:
                                try:
                                    for inp in ['input[name="LOGIN_ID"]', 'input[type="email"]', 'input[id="login_id"]', 'input[placeholder*="email" i]', 'input[placeholder*="Email" i]', 'input[placeholder*="ID" i]']:
                                        loc = frame.locator(inp)
                                        if loc.count() > 0 and loc.first.is_visible():
                                            email_input = loc.first
                                            break
                                except: pass
                                if email_input: break
                        if email_input:
                            print(f"[{reg_no}] Found email input field (attempt {attempt+1})")
                            break
                        page.wait_for_timeout(1000)

                    if login_success:
                        break

                    if not email_input:
                        # Fallback: maybe password input is visible
                        pwd_input = find_in_frames('input[type="password"]')
                        if not pwd_input:
                            print(f"[{reg_no}] WARNING: Neither email nor password box found yet. Retrying attempt...")
                            continue
                    else:
                        # Fill email
                        email_input.click(force=True)
                        page.wait_for_timeout(300)
                        email_input.fill(reg_no, force=True)
                        print(f"[{reg_no}] 3a. Email filled")
                        page.wait_for_timeout(500)
                        
                        # Click Next
                        next_btn = find_in_frames('button#nextbtn', filter_text=None)
                        if not next_btn:
                            next_btn = find_in_frames('button, input[type="submit"]', filter_text="next|continue")
                        if next_btn:
                            print(f"[{reg_no}] 3b. Clicking Next button...")
                            next_btn.click(force=True, timeout=2000)
                        else:
                            print(f"[{reg_no}] 3b. No Next button found, pressing Enter...")
                            page.keyboard.press("Enter")
                        
                        page.wait_for_timeout(1000)

                # Wait for password input field
                pwd_input = None
                for attempt in range(10):
                    if find_in_frames('#Welcome, .profile-header, #ul-main-menu, .user-name, #zohoviewer, .tab-title, [class*="profile"]'):
                        print(f"[{reg_no}] Dashboard loaded belatedly during pwd check (attempt {attempt+1}). Authenticated!")
                        login_success = True
                        break
                        
                    pwd_input = find_in_frames('input[type="password"]')
                    if not pwd_input:
                        pwd_input = find_in_frames('input[name="PASSWORD"]')
                    if pwd_input:
                        print(f"[{reg_no}] Found password field (attempt {attempt+1})")
                        break
                    
                    # Check for explicit errors on the email screen (e.g. invalid email)
                    error_el = find_in_frames('.error, .alert-danger, #errormsg, .zloginerror, .login-error', filter_text=None)
                    if error_el:
                        try:
                            err_text = error_el.inner_text(timeout=500)
                            if err_text and len(err_text.strip()) > 3:
                                if "incorrect" in err_text.lower() or "invalid" in err_text.lower() or "error" in err_text.lower() or "exist" in err_text.lower():
                                    out_queue.put({'success': False, 'error': f'Auth Error: {err_text.strip()}'})
                                    return
                        except: pass
                    
                    page.wait_for_timeout(1000)
                
                if login_success:
                    break

                if not pwd_input:
                    print(f"[{reg_no}] WARNING: Password box not found on attempt {login_attempt}. Retrying...")
                    continue

                # Type password
                pwd_input.click(force=True)
                page.wait_for_timeout(300)
                pwd_input.type(pwd, delay=50)
                print(f"[{reg_no}] 4a. Password typed")
                page.wait_for_timeout(500)

                # Click Sign In button
                submit_btn = find_in_frames('button#nextbtn', filter_text=None)
                if not submit_btn:
                    submit_btn = find_in_frames('button, input[type="submit"]', fill_text=None, filter_text="sign.?in|login|submit|verify|next")
                if submit_btn:
                    print(f"[{reg_no}] 4b. Clicking Sign In button...")
                    submit_btn.click(force=True, timeout=3000)
                else:
                    print(f"[{reg_no}] 4b. No Sign In button found, pressing Enter...")
                    page.keyboard.press("Enter")

                print(f"[{reg_no}] 4c. Waiting for login to process...")
                page.wait_for_timeout(1000)

                # Check for explicit errors immediately to avoid long timeouts
                error_el = find_in_frames('.error, .alert-danger, #errormsg, .zloginerror, .login-error', filter_text=None)
                err_text = ""
                if error_el:
                    try: err_text = error_el.inner_text(timeout=1000)
                    except: pass
                
                captcha_el = find_in_frames('#captchadiv, .captcha, [id*="captcha"]')
                if captcha_el:
                    out_queue.put({'success': False, 'error': 'CAPTCHA detected. Please try again later.'})
                    return
                elif err_text and len(err_text.strip()) > 3:
                    if "incorrect" in err_text.lower() or "invalid" in err_text.lower() or "error" in err_text.lower() or "try again" in err_text.lower():
                        out_queue.put({'success': False, 'error': f'Auth Error: {err_text.strip()}'})
                        return

                # Wait the remaining time
                page.wait_for_timeout(3000)

                # Check for warnings/popups
                for _ in range(4):
                    if check_and_handle_zoho_popups():
                        print(f"[{reg_no}] Handled popup on login attempt {login_attempt}.")
                        page.wait_for_timeout(1000)
                        break
                    page.wait_for_timeout(500)

                current_url = page.url
                print(f"[{reg_no}] Post-login URL: {current_url}")

                if 'accounts.zoho' not in current_url.lower() and 'signin' not in current_url.lower() and 'sessions-reminder' not in current_url.lower():
                    print(f"[{reg_no}] Login succeeded on attempt {login_attempt}!")
                    login_success = True
                    break

            if not login_success:
                current_url = page.url
                print(f"[{reg_no}] ERROR: Login failed after 3 attempts. Final URL: {current_url}")
                
                # Diagnostic check for CAPTCHA or incorrect credentials
                error_el = find_in_frames('.error, .alert-danger, #errormsg, .zloginerror', filter_text=None)
                err_text = ""
                if error_el:
                    try: err_text = error_el.inner_text(timeout=2000)
                    except: pass
                
                captcha_el = find_in_frames('#captchadiv, .captcha, [id*="captcha"]')
                if captcha_el:
                    out_queue.put({'success': False, 'error': 'CAPTCHA detected. Too many login attempts. Please try again later.'})
                elif err_text:
                    out_queue.put({'success': False, 'error': f'Auth Error: {err_text.strip()}'})
                else:
                    out_queue.put({'success': False, 'error': 'Login failed - still on login page. Check credentials.'})
                return

            # DIAGNOSTIC: Print all available sidebar links
            unique_links = []
            try:
                print(f"[{reg_no}] DIAGNOSTIC: Scanning for available menu pages...")
                page.wait_for_timeout(500)
                links = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a')).map(a => a.href).filter(h => h.includes('#Page:'));
                }""")
                for f in page.frames:
                    try:
                        frame_links = f.evaluate("""() => {
                            return Array.from(document.querySelectorAll('a')).map(a => a.href).filter(h => h.includes('#Page:'));
                        }""")
                        if frame_links: links.extend(frame_links)
                    except: pass
                unique_links = list(set(links))
                print(f"[{reg_no}] DIAGNOSTIC Available Pages: {unique_links}")
                
                if not unique_links:
                    print(f"[{reg_no}] DIAGNOSTIC: No links found! What is on the screen?")
                    page_text = page.evaluate("document.body.innerText")
                    clean_text = ' | '.join([line.strip() for line in page_text.split('\n') if line.strip()][:20])
                    print(f"[{reg_no}] DIAGNOSTIC PAGE TEXT: {clean_text}")
                    for i, f in enumerate(page.frames):
                        try:
                            f_text = f.evaluate("document.body.innerText")
                            f_clean = ' | '.join([line.strip() for line in f_text.split('\n') if line.strip()][:10])
                            if f_clean:
                                print(f"[{reg_no}] DIAGNOSTIC FRAME {i} TEXT: {f_clean}")
                        except: pass
            except Exception as e:
                print(f"[{reg_no}] DIAGNOSTIC Failed to scan links: {e}")

        except Exception as e:
            out_queue.put({'success': False, 'error': f'Auth Failed: {str(e)}'})
            return

        def get_all_tables():
            try:
                page.wait_for_selector("iframe", state="attached", timeout=5000)
            except: pass
            all_tables = []
            for frame in page.frames:
                try:
                    tables = frame.evaluate("""() => {
                        return Array.from(document.querySelectorAll('table')).map(t => 
                            Array.from(t.querySelectorAll('tr')).map(tr => {
                                let rowArr = [];
                                Array.from(tr.querySelectorAll('td, th')).forEach(td => {
                                    let span = td.colSpan || 1;
                                    let text = (td.innerText || td.textContent || "").trim();
                                    for(let i=0; i<span; i++) rowArr.push(text);
                                });
                                return rowArr;
                            }).filter(row => row.length > 0)
                        ).filter(table => table.length > 0);
                    }""")
                    if tables: all_tables.extend(tables)
                except: pass
            return all_tables
            
        def wait_for_data_tables(keywords, timeout=20000):
            if isinstance(keywords, str):
                keywords = [keywords]
            keywords = [k.lower() for k in keywords]
            
            start = time.time()
            tables_seen_start = None
            while time.time() - start < timeout / 1000.0:
                if check_and_handle_zoho_popups():
                    print(f"[{reg_no}] Handled popup warning during wait. Waiting for redirect...")
                    page.wait_for_timeout(1000)
                tables = get_all_tables()
                if tables:
                    for t in tables:
                        for row in t:
                            for c in row:
                                c_str = str(c).lower()
                                if any(k in c_str for k in keywords):
                                    return tables
                    if tables_seen_start is None:
                        tables_seen_start = time.time()
                    elif time.time() - tables_seen_start > 5.0:
                        print(f"[{reg_no}] Tables found but keywords {keywords} not matched. Returning tables anyway.")
                        return tables
                page.wait_for_timeout(500)
            return get_all_tables()

        def get_col_index(headers, *keywords):
            for i, h in enumerate(headers):
                h_lower = str(h).lower()
                if any(kw in h_lower for kw in keywords):
                    return i
            return -1

        # --- ATTENDANCE & MARKS ---
        print(f"[{reg_no}] 5. Scoping Attendance...")
        
        # Try multiple attendance page URLs
        att_urls_pool = [
            "https://academia.srmist.edu.in/#Page:My_Attendance",
            "https://academia.srmist.edu.in/#Page:My_Attendance_2024_25",
            "https://academia.srmist.edu.in/#Page:My_Attendance_2025_26",
            "https://academia.srmist.edu.in/#Page:My_Attendance_2023_24"
        ]
        
        # Only check URLs that are actually in the student's menu
        att_urls = [u for u in att_urls_pool if any(u.split('#Page:')[1] in link for link in unique_links)]
        if not att_urls:
            att_urls = att_urls_pool
            
        raw_tables = []
        for att_url in att_urls:
            print(f"[{reg_no}] Trying attendance URL: {att_url}")
            page.goto(att_url)
            raw_tables = wait_for_data_tables(["attn", "attendance", "conducted", "absent", "hour", "code"], timeout=5000)
            if raw_tables and len(raw_tables) > 0:
                # Check if any table actually has attendance-like data
                has_att_data = False
                for t in raw_tables:
                    for row in t:
                        row_str = ' '.join(str(c).lower() for c in row)
                        if any(k in row_str for k in ["attn", "attendance", "conducted", "absent", "hour"]):
                            has_att_data = True
                            break
                    if has_att_data: break
                if has_att_data:
                    print(f"[{reg_no}] Found attendance data from {att_url}")
                    break
        
        # If still no data, try a reload on the primary URL
        if not raw_tables or not any(k in str(c).lower() for k in ["attn", "attendance", "conducted", "absent"] for t in raw_tables for row in t for c in row):
            print(f"[{reg_no}] Attendance data not found on any URL. Trying reload...")
            page.goto(att_urls[0])
            page.reload(wait_until="domcontentloaded")
            raw_tables = wait_for_data_tables(["attn", "attendance", "conducted", "absent", "code"], timeout=5000)
        
        # Log what we found
        if raw_tables:
            print(f"[{reg_no}] Found {len(raw_tables)} tables on attendance page")
            for idx, t in enumerate(raw_tables):
                if t and len(t) > 0:
                    print(f"[{reg_no}]   Table {idx}: {len(t)} rows, headers: {t[0][:5] if t[0] else '?'}")
        else:
            print(f"[{reg_no}] WARNING: No tables found on attendance page at all. Semester holidays?")
            try:
                print(f"[{reg_no}] DIAGNOSTIC: Attendance page has NO tables. URL: {page.url}")
                page_text = page.evaluate("document.body.innerText")
                clean_text = ' | '.join([line.strip() for line in page_text.split('\n') if line.strip()][:25])
                print(f"[{reg_no}] DIAGNOSTIC ATTENDANCE PAGE TEXT: {clean_text}")
                for i, f in enumerate(page.frames):
                    try:
                        f_text = f.evaluate("document.body.innerText")
                        f_clean = ' | '.join([line.strip() for line in f_text.split('\n') if line.strip()][:10])
                        if f_clean:
                            print(f"[{reg_no}] DIAGNOSTIC ATTENDANCE FRAME {i} TEXT: {f_clean}")
                    except: pass
            except Exception as e:
                print(f"[{reg_no}] Failed to log attendance diagnostics: {e}")

        parsed_att = []
        parsed_marks = []
        print(f"[{reg_no}] Found {len(parsed_att)} attendance records. Now loading timetable...")

        def get_table_headers(tbl):
            if not tbl: return [], "", -1
            for r_idx in range(min(4, len(tbl))):
                hdrs = [str(h).lower() for h in tbl[r_idx]]
                hdr_str = " ".join(hdrs)
                if ("code" in hdr_str and ("title" in hdr_str or "name" in hdr_str)) or "attn" in hdr_str:
                    return hdrs, hdr_str, r_idx
            hdrs = [str(h).lower() for h in tbl[0]]
            return hdrs, " ".join(hdrs), 0

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
            headers, header_str, h_idx = get_table_headers(table)

            # Dynamic Attendance Parsing
            if "attn" in header_str or "attendance" in header_str:
                try:
                    idx_code = get_col_index(headers, "code")
                    idx_title = get_col_index(headers, "title", "name", "description", "desc", "subject")
                    
                    # New UI has "attn %" or similar
                    idx_attn_perc = get_col_index(headers, "attn %", "attn", "attendance")
                    # Fallback for old UI
                    idx_cond = get_col_index(headers, "conducted")
                    idx_abs = get_col_index(headers, "absent")
                    
                    # Extract Credits
                    idx_credit = get_col_index(headers, "max credit", "credit")
                    
                    if idx_code != -1 and idx_title != -1:
                        for row in table[h_idx+1:]:
                            credit_val = 3.0
                            if idx_credit != -1 and len(row) > idx_credit:
                                try: credit_val = float(row[idx_credit])
                                except: pass
                                
                            if idx_attn_perc != -1 and len(row) > idx_attn_perc:
                                # New Map: Just Attn %
                                perc_str = str(row[idx_attn_perc]).replace('%', '').strip()
                                try:
                                    perc = float(perc_str)
                                    parsed_att.append({
                                        "courseTitle": f"{row[idx_code]} - {row[idx_title][:20]}",
                                        "attended": perc,
                                        "total": 100,
                                        "credits": credit_val
                                    })
                                except: pass
                            elif idx_cond != -1 and idx_abs != -1 and len(row) > max(idx_cond, idx_abs):
                                # Old Map: Hours conducted & absent
                                try:
                                    cond = int(float(row[idx_cond] or 0))
                                    absent = int(float(row[idx_abs] or 0))
                                    parsed_att.append({
                                        "courseTitle": f"{row[idx_code]} - {row[idx_title][:20]}",
                                        "attended": max(0, cond - absent),
                                        "total": cond,
                                        "credits": credit_val
                                    })
                                except: pass
                except Exception as e:
                    print("Parsing error (Attendance):", str(e))
                    continue

            # Dynamic Marks Parsing
            elif any(kw in header_str for kw in ["test performance", "assessment", "marks", "internal"]):
                try:
                    idx_code = get_col_index(headers, "code")
                    idx_title = get_col_index(headers, "title", "name", "course name", "description", "desc", "subject")
                    idx_perf = get_col_index(headers, "performance", "assessment", "marks", "internal")
                    
                    idx_max = get_col_index(headers, "max")
                    idx_obt = get_col_index(headers, "obtained")
                    
                    idx_credit = get_col_index(headers, "max credit", "credit")
                    
                    if idx_code == -1 or idx_perf == -1: continue
                    
                    current_code = ""
                    current_title = ""
                    
                    for row in table[h_idx+1:]:
                        code_val = row[idx_code].strip() if idx_code != -1 and len(row) > idx_code else ""
                        title_val = row[idx_title].strip() if idx_title != -1 and len(row) > idx_title else ""
                        
                        # If a row has a valid code, update our tracker. Otherwise, inherit from previous row (handles rowspan).
                        # Only accept valid course codes (no spaces, slashes, or decimals) to prevent parsing garbage tables.
                        if code_val and len(code_val) > 2 and "/" not in code_val and "." not in code_val and " " not in code_val.strip():
                            current_code = code_val
                            current_title = title_val if title_val else code_val
                        
                        if not current_code: continue
                        
                        credit_val = 3.0
                        if idx_credit != -1 and len(row) > idx_credit:
                            try: credit_val = float(row[idx_credit])
                            except: pass
                        
                        if idx_max != -1 and idx_obt != -1 and len(row) > max(idx_perf, idx_obt, idx_max):
                            # New Format (Separate Max and Obtained columns)
                            perf_name = row[idx_perf].replace(' ', '')
                            max_val = str(row[idx_max]).strip()
                            obt_val = str(row[idx_obt]).strip()
                            
                            if not obt_val or not max_val: continue
                            
                            formatted_perf = f"{perf_name}/{max_val} | {obt_val}"
                            
                            existing = next((item for item in parsed_marks if item["courseCode"] == current_code), None)
                            if existing:
                                if formatted_perf not in existing["Test Performance"]:
                                    existing["Test Performance"] += f" \n {formatted_perf}"
                                # Upgrade title if we found a better one
                                if len(current_title) > len(existing.get("courseTitle", "")):
                                    existing["courseTitle"] = current_title
                            else:
                                parsed_marks.append({
                                    "courseTitle": current_title,
                                    "courseCode": current_code,
                                    "Test Performance": formatted_perf,
                                    "credits": credit_val
                                })
                        elif len(row) > idx_perf:
                            # Old Format Fallback
                            perf_str = row[idx_perf].replace('\n', ' | ')
                            if not perf_str.strip(): continue
                            
                            existing = next((item for item in parsed_marks if item["courseCode"] == current_code), None)
                            if existing:
                                if perf_str not in existing["Test Performance"]:
                                    existing["Test Performance"] += f" \n {perf_str}"
                            else:
                                parsed_marks.append({
                                    "courseTitle": current_title,
                                    "courseCode": current_code,
                                    "Test Performance": perf_str,
                                    "credits": credit_val
                                })
                except Exception as e:
                    print("Parsing error (Marks):", str(e))
                    continue

        # --- TIMETABLE STEP 1 (STUDENT SLOTS) ---
        print(f"[{reg_no}] 6. Scoping Registered Slots...")
        student_slots = {}
        timetable_urls_pool = [
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2023_24",
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25",
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2025_26",
            "https://academia.srmist.edu.in/#Page:My_Time_Table"
        ]
        timetable_urls = [u for u in timetable_urls_pool if any(u.split('#Page:')[1] in link for link in unique_links)]
        if not timetable_urls:
            timetable_urls = timetable_urls_pool
        
        slot_tables = []
        for url in timetable_urls:
            print(f"[{reg_no}] Trying timetable URL: {url}")
            page.goto(url)
            slot_tables = wait_for_data_tables(["slot", "course", "code"], timeout=5000)
            if any(k in str(c).lower() for k in ["slot", "course", "code"] for t in slot_tables for row in t for c in row):
                print(f"[{reg_no}] Successfully loaded timetable from {url}")
                break
        else:
            print(f"[{reg_no}] Warning: No slot tables found with primary URLs. Attempting page reload on primary...")
            page.goto(timetable_urls[0])
            page.reload(wait_until="domcontentloaded")
            slot_tables = wait_for_data_tables(["slot", "course", "code"], timeout=8000)
            if not slot_tables:
                try:
                    print(f"[{reg_no}] DIAGNOSTIC: Timetable page has NO tables. URL: {page.url}")
                    page_text = page.evaluate("document.body.innerText")
                    clean_text = ' | '.join([line.strip() for line in page_text.split('\n') if line.strip()][:25])
                    print(f"[{reg_no}] DIAGNOSTIC TIMETABLE PAGE TEXT: {clean_text}")
                    for i, f in enumerate(page.frames):
                        try:
                            f_text = f.evaluate("document.body.innerText")
                            f_clean = ' | '.join([line.strip() for line in f_text.split('\n') if line.strip()][:10])
                            if f_clean:
                                print(f"[{reg_no}] DIAGNOSTIC TIMETABLE FRAME {i} TEXT: {f_clean}")
                        except: pass
                except Exception as e:
                    print(f"[{reg_no}] Failed to log timetable diagnostics: {e}")
        
        # --- EXTRACT RICH PROFILE DATA FROM TIMETABLE PAGE ---
        for table in slot_tables:
            if not table: continue
            for row in table:
                if len(row) >= 2:
                    for i in range(len(row) - 1):
                        k = str(row[i]).replace(':', '').strip().lower()
                        v = str(row[i+1]).replace(':', '').strip()
                        if "registration" in k and "number" in k:
                            if len(v) > 5: profile_data["regNo"] = v.strip()
                        elif "department" in k:
                            if len(v) > 2: profile_data["department"] = v.strip()
                        elif "combo" in k or "batch" in k:
                            if len(v) > 0: profile_data["batch"] = v.strip()
                        elif "class room" in k or "classroom" in k:
                            if len(v) > 0: profile_data["classRoom"] = v.strip()
                        elif "program" in k:
                            if len(v) > 2: profile_data["course"] = v.strip()[:35]
                        elif "semester" in k:
                            if len(v) > 0 and len(v) <= 2: profile_data["semester"] = v.strip()
                        elif "name" in k and "father" not in k and "mother" not in k and "faculty" not in k:
                            if len(v) > 2 and profile_data["name"] == "STUDENT": profile_data["name"] = v.strip()
        
        # --- EXTRACT ADVISOR DATA FROM TIMETABLE PAGE ---
        print(f"[{reg_no}] 6a. Extracting Advisor Details...")
        for table in slot_tables:
            if not table: continue
            for r_idx, row in enumerate(table):
                for c_idx, cell in enumerate(row):
                    cell_str = str(cell).strip()
                    cell_lower = cell_str.lower()
                    
                    # Faculty Advisor detection (usually in one multiline cell)
                    if 'faculty advisor' in cell_lower:
                        lines = [line.strip() for line in cell_str.split('\n') if line.strip()]
                        for k, line in enumerate(lines):
                            ll = line.lower()
                            if 'faculty advisor' in ll:
                                if k > 0 and len(lines[k-1]) > 3:
                                    profile_data['fa_name'] = lines[k-1]
                            elif '@' in ll and 'srmist' in ll:
                                profile_data['fa_email'] = line
                            elif re.match(r'^\+?[0-9\s-]{10,}$', line) and len(re.sub(r'\D', '', line)) >= 10:
                                profile_data['fa_phone'] = re.sub(r'\D', '', line)[-10:]
                    
                    # Academic Advisor detection
                    if 'academic advisor' in cell_lower:
                        lines = [line.strip() for line in cell_str.split('\n') if line.strip()]
                        for k, line in enumerate(lines):
                            ll = line.lower()
                            if 'academic advisor' in ll:
                                if k > 0 and len(lines[k-1]) > 3:
                                    profile_data['aa_name'] = lines[k-1]
                            elif '@' in ll and 'srmist' in ll:
                                profile_data['aa_email'] = line
                            elif re.match(r'^\+?[0-9\s-]{10,}$', line) and len(re.sub(r'\D', '', line)) >= 10:
                                profile_data['aa_phone'] = re.sub(r'\D', '', line)[-10:]
        
        print(f"[{reg_no}] Profile extracted: regNo={profile_data.get('regNo','?')}, dept={profile_data.get('department','?')}, FA={profile_data.get('fa_name','?')}, AA={profile_data.get('aa_name','?')}")
        
        # --- PARSE STUDENT SLOTS ---
        for table in slot_tables:
            if not table: continue
            headers, header_str, h_idx = get_table_headers(table)
            
            if "slot" in header_str and "code" in header_str:
                try:
                    idx_code = get_col_index(headers, "code")
                    idx_title = get_col_index(headers, "title", "name", "description", "desc", "subject")
                    idx_slot = get_col_index(headers, "slot")
                    idx_room = get_col_index(headers, "room")
                    
                    if -1 in (idx_code, idx_title, idx_slot, idx_room): continue
                    
                    for row in table[h_idx+1:]:
                        if len(row) > idx_room:
                            # Refined Regex matching (matches A, P49, PT2, etc)
                            slots_found = re.findall(r'\b[A-Z]{1,2}\d*\b', row[idx_slot])
                            for s in slots_found:
                                # Use subject title if possible, else subject code
                                subj_name = row[idx_title].strip() if idx_title != -1 and len(row) > idx_title and row[idx_title].strip() else row[idx_code].strip()
                                student_slots[s] = {
                                    "subject": subj_name,
                                    "room": row[idx_room].strip() if idx_room != -1 and len(row) > idx_room else "TBA",
                                    "code": row[idx_code].strip() if idx_code != -1 and len(row) > idx_code else ""
                                }
                except Exception as e:
                    print("Parsing error (Slots):", str(e))
                    continue

        # --- TIMETABLE STEP 2 (MASTER TIMINGS) ---
        print(f"[{reg_no}] 7. Mapping to Master (Batch {batch})...")
        final_tt = {"1": [], "2": [], "3": [], "4": [], "5": []}
        global_seen_entries = {"1": set(), "2": set(), "3": set(), "4": set(), "5": set()}
        
        # Smart year extraction from registration number
        # Formats: RA2311003010123 (RA + 23 = 2023), KR4495 (KR + 44 = invalid)
        # Only accept years between 2018 and current_year+1
        import datetime as dt_module
        current_year = dt_module.datetime.now().year
        joining_year = str(current_year)  # Default to current year
        
        # Try to extract year from common SRM reg number formats
        # Format 1: RA23xxxxxxx - 2 letter prefix + 2 digit year
        reg_clean = reg_no.split('@')[0].upper()
        year_found = False
        
        # Try matching RA23, RM24 etc (2 letter + 2 digit year)
        reg_year_match = re.match(r'^[A-Z]{2}(\d{2})', reg_clean)
        if reg_year_match:
            y = int(reg_year_match.group(1))
            full_year = 2000 + y
            if 2018 <= full_year <= current_year + 1:
                joining_year = str(full_year)
                year_found = True
                print(f"[{reg_no}] Extracted joining year {joining_year} from reg prefix")
        
        # If that didn't work, try longer patterns like RA2311003...
        if not year_found:
            reg_year_match2 = re.search(r'(20[12]\d)', reg_clean)
            if reg_year_match2:
                full_year = int(reg_year_match2.group(1))
                if 2018 <= full_year <= current_year + 1:
                    joining_year = str(full_year)
                    year_found = True
                    print(f"[{reg_no}] Extracted joining year {joining_year} from 4-digit pattern")
        
        if not year_found:
            print(f"[{reg_no}] Could not extract valid year from reg number. Using current year: {joining_year}")
            
        print(f"[{reg_no}] Using joining year: {joining_year}")
        
        timetable_years = [joining_year, str(current_year), str(current_year - 1), str(current_year - 2)]
        timetable_years = list(dict.fromkeys(timetable_years))  # Remove duplicates
        
        master_urls_pool = [f"https://academia.srmist.edu.in/#Page:Unified_Time_Table_{y}_Batch_{batch}" for y in timetable_years]
        valid_master_urls = [u for u in master_urls_pool if any(u.split('#Page:')[1] in link for link in unique_links)]
        if not valid_master_urls:
            valid_master_urls = master_urls_pool
        
        master_tables = []
        for url in valid_master_urls:
            print(f"[{reg_no}] Trying unified timetable URL: {url}")
            page.goto(url)
            master_tables = wait_for_data_tables(["day 1", "day order", "timings", "time"], timeout=8000)
            if any("day 1" in str(c).lower() for t in master_tables for row in t for c in row):
                print(f"[{reg_no}] Successfully loaded unified timetable from {url}")
                break
        else:
            print(f"[{reg_no}] Warning: No unified timetable tables found. Reloading primary...")
            url = f"https://academia.srmist.edu.in/#Page:Unified_Time_Table_{joining_year}_Batch_{batch}"
            page.goto(url)
            page.reload(wait_until="networkidle")
            master_tables = wait_for_data_tables(["day 1", "day order", "timings", "time"], timeout=15000)
        
        print(f"[{reg_no}] Found {len(master_tables)} master tables")
        
        last_good_time_cols = []
        for t_idx, table in enumerate(master_tables):
            if not table: continue
            
            time_cols = []
            from_row = []
            to_row = []
            start_row = -1
            
            for r_idx, row in enumerate(table):
                first_cell = str(row[0]).lower().replace('\n', ' ').strip()
                
                # Check for \d+:\d+ pattern in the row to deeply detect timing rows
                time_matches = [re.search(r'\d{1,2}:\d{2}', str(c)) for c in row[1:]]
                has_times = sum(1 for m in time_matches if m is not None) >= 3
                
                if has_times:
                    extracted = [str(c).replace('\n', ' ').strip() for c in row[1:]]
                    if not from_row:
                        from_row = extracted
                    elif not to_row:
                        to_row = extracted
                    elif len(time_cols) == 0:
                        # Fallback if both filled but another time row found
                        time_cols = extracted
                
                # Sometimes a row has explicitly '8:00 - 8:50'
                combined_match = [re.search(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', str(c)) for c in row[1:]]
                if sum(1 for m in combined_match if m is not None) >= 3:
                    time_cols = [str(c).replace('\n', ' ').strip() for c in row[1:]]
                
                # Identify where days start
                if ("day" in first_cell or "order" in first_cell) and any(str(i) in first_cell for i in range(1, 6)):
                    start_row = r_idx
                    break
                    
            if not time_cols and from_row and to_row:
                for f, t in zip(from_row, to_row):
                    f_clean = f.strip()
                    t_clean = t.strip()
                    if f_clean and t_clean:
                        time_cols.append(f"{f_clean} - {t_clean}")
                    elif f_clean:
                        time_cols.append(f_clean)
                    else:
                        time_cols.append("")
            elif not time_cols and from_row and not to_row:
                time_cols = from_row
                        
            # Inherit from previous tables if split
            if time_cols:
                last_good_time_cols = time_cols
            elif last_good_time_cols:
                time_cols = last_good_time_cols
                
            # Debug: print extracted time columns
            if time_cols:
                print(f"[{reg_no}] Table {t_idx}: time_cols ({len(time_cols)}) = {time_cols[:10]}")
            elif from_row:
                print(f"[{reg_no}] Table {t_idx}: fallback from_row ({len(from_row)}) = {from_row[:10]}")
                    
            if start_row != -1:
                print(f"[{reg_no}] Table {t_idx}: Day rows start at row {start_row}")
                for row in table[start_row:]:
                    try:
                        day_match = re.search(r'\d+', row[0])
                        if not day_match: continue
                        day_order = day_match.group()
                        
                        if day_order in final_tt:
                            for i, cell in enumerate(row[1:]):
                                slots_in_cell = re.findall(r'\b[A-Z]{1,2}\d*\b', cell)
                                for s in slots_in_cell:
                                    if s in student_slots:
                                        t_str = time_cols[i] if i < len(time_cols) else f"Period {i+1}"
                                        
                                        # Validate if t_str actually contains a time. If it got corrupted with a slot string, fallback to standard SRM times.
                                        if not re.search(r'\d{1,2}:\d{2}', t_str):
                                            std_times = ["08:00 - 08:50", "08:50 - 09:40", "09:45 - 10:35", "10:35 - 11:25", "11:30 - 12:20", "12:20 - 13:10", "13:15 - 14:05", "14:05 - 14:55", "15:00 - 15:50", "15:50 - 16:40"]
                                            t_str = std_times[i] if i < len(std_times) else f"Period {i+1}"
                                            
                                        t_str = re.sub(r'\s+', ' ', t_str).strip()
                                        
                                        entry_key = f"{t_str}-{student_slots[s]['subject']}"
                                        if entry_key not in global_seen_entries[day_order]:
                                            last_entry = final_tt[day_order][-1] if final_tt[day_order] else None
                                            
                                            # Merge continuous identical slots to avoid unnecessary extra cards
                                            if last_entry and last_entry["subject"] == student_slots[s]['subject']:
                                                old_start = last_entry["time"].split('-')[0].strip()
                                                new_end = t_str.split('-')[-1].strip() if '-' in t_str else t_str
                                                last_entry["time"] = f"{old_start} - {new_end}"
                                            else:
                                                final_tt[day_order].append({
                                                    "time": t_str,
                                                    "subject": student_slots[s]['subject'],
                                                    "room": student_slots[s]['room']
                                                })
                                            global_seen_entries[day_order].add(entry_key)
                                            print(f"[{reg_no}]   Day {day_order}: slot {s} -> {t_str} | {student_slots[s]['subject']}")
                    except Exception as e:
                        print("Parsing error (Master TT Row):", str(e))
                        continue

        # Debug Logging for Empty Parsing
        if not parsed_att and not parsed_marks and not student_slots:
            try:
                with open("debug_tables.txt", "w", encoding="utf-8") as f:
                    f.write("RAW TABLES:\n" + str(raw_tables) + "\n\nSLOT TABLES:\n" + str(slot_tables) + "\n\nMASTER TABLES:\n" + str(master_tables))
                print(f"[{reg_no}] Empty arrays detected. Saved to debug_tables.txt")
                print(f"[{reg_no}] DIAGNOSTIC: Current URL: {page.url} | Title: {page.title()}")
                page_text = page.evaluate("document.body.innerText")
                clean_text = ' | '.join([line.strip() for line in page_text.split('\n') if line.strip()][:30])
                print(f"[{reg_no}] DIAGNOSTIC PAGE TEXT: {clean_text}")
                for i, f in enumerate(page.frames):
                    try:
                        f_text = f.evaluate("document.body.innerText")
                        f_clean = ' | '.join([line.strip() for line in f_text.split('\n') if line.strip()][:15])
                        if f_clean:
                            print(f"[{reg_no}] DIAGNOSTIC FRAME {i} TEXT: {f_clean}")
                    except: pass
            except Exception as e:
                print(f"Failed to write debug file or logs: {str(e)}")

        # --- POST-PROCESS TITLES ---
        # Collect the absolute best title for each course code across all three data sources
        best_titles = {}
        for a in parsed_att:
            c = a.get("courseCode")
            t = a.get("courseTitle", "")
            if c and "-" in t:
                clean = t.split("-", 1)[1].strip()
                if clean and len(clean) > len(best_titles.get(c, "")): best_titles[c] = clean
        
        for m in parsed_marks:
            c = m.get("courseCode")
            t = m.get("courseTitle", "")
            if c and t and t != c and len(t) > len(best_titles.get(c, "")): best_titles[c] = t
            
        for s_data in student_slots.values():
            c = s_data.get("code")
            t = s_data.get("subject", "")
            if c and t and t != c and len(t) > len(best_titles.get(c, "")): best_titles[c] = t

        # Apply the best titles back to the data
        for m in parsed_marks:
            c = m.get("courseCode")
            if c in best_titles and (m.get("courseTitle") == c or not m.get("courseTitle")):
                m["courseTitle"] = best_titles[c]
                
        for a in parsed_att:
            c = a.get("courseCode")
            if c in best_titles:
                a["courseTitle"] = f"{c} - {best_titles[c]}"
                
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

sync_jobs = {}

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    sync_id = str(uuid.uuid4())
    sync_jobs[sync_id] = {'status': 'processing', 'timestamp': time.time()}
    
    def worker_wrapper(reg_no, pwd, batch, sid):
        out_queue = queue.Queue()
        # We start the scraper normally
        scrape_academia_worker(reg_no, pwd, batch, out_queue)
        try:
            # We wait for the scraper to finish without holding the HTTP response
            result = out_queue.get(timeout=10)
            if result.get('success'):
                profile = result.get('profile', {})
                raw_reg = reg_no or ''
                net_id = raw_reg.split('@')[0]
                register_no = net_id.upper()
                name = profile.get('name', 'Student')
                save_student_to_db(net_id, name, register_no, result.get('data', []), result.get('marks', []))
            sync_jobs[sid] = {'status': 'completed', 'result': result, 'timestamp': time.time()}
        except queue.Empty:
            sync_jobs[sid] = {'status': 'failed', 'result': {'success': False, 'error': 'Background task crashed.'}, 'timestamp': time.time()}
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

        owner_id = (row[0] if DATABASE_URL else dict(row).get('net_id', '')).lower().strip()
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

        owner_id = (row[0] if DATABASE_URL else dict(row).get('net_id', '')).lower().strip()
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
        cur.execute("SELECT id, title, artist, cover_data, uploaded_by, net_id, created_at FROM music_hub ORDER BY order_index ASC, created_at DESC")
    else:
        cur = conn.cursor()
        cur.execute("SELECT id, title, artist, cover_data, uploaded_by, net_id, created_at FROM music_hub ORDER BY order_index ASC, created_at DESC")
    
    rows = cur.fetchall()
    items = [dict(row) for row in rows]
    cur.close()
    conn.close()
    return jsonify(items)

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
    if row:
        return jsonify({'audio_data': row[0]})
    return jsonify({'error': 'Track not found'}), 404

@app.route('/api/music/submit', methods=['POST'])
def submit_music():
    data = request.json
    required = ['title', 'artist', 'audio_data', 'uploaded_by', 'net_id']
    if not all(k in data for k in required) or not data['audio_data']:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO music_hub (title, artist, audio_data, cover_data, uploaded_by, net_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (data.get('title'), data.get('artist'), data.get('audio_data'), data.get('cover_data'),
                  data.get('uploaded_by'), data.get('net_id'), now_str))
        else:
            cur.execute("""
                INSERT INTO music_hub (title, artist, audio_data, cover_data, uploaded_by, net_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (data.get('title'), data.get('artist'), data.get('audio_data'), data.get('cover_data'),
                  data.get('uploaded_by'), data.get('net_id'), now_str))
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
    
    models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.5-flash-latest", "gemini-pro"]
    last_error = ""
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            data = response.json()
            if 'error' in data:
                err_msg = data['error'].get('message', str(data['error']))
                last_error = err_msg
                if 'not found' in err_msg.lower() or 'not supported' in err_msg.lower():
                    continue # try next model
                return "API Error: " + err_msg
            if 'candidates' in data and data['candidates']:
                return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            last_error = str(e)
            
    return f"Error: All Gemini models failed. Last error: {last_error}"

@app.route('/api/music/lyrics', methods=['GET'])
def get_lyrics():
    artist = request.args.get('artist')
    title = request.args.get('title')
    if not artist or not title:
        return jsonify({'success': False, 'error': 'Missing parameters'})
    try:
        clean_title = re.sub(r'\(.*?\)', '', title).strip()
        # Extract primary artist only to improve search hit rate for collaborations
        clean_artist = artist.lower().split(' x ')[0].split(',')[0].split('&')[0].split(' feat.')[0].split(' ft.')[0].strip()
        
        query = f"{clean_title} {clean_artist}"
        url = f"https://lrclib.net/api/search?q={urllib.parse.quote(query)}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                lyrics = data[0].get('plainLyrics') or data[0].get('syncedLyrics')
                if lyrics:
                    return jsonify({'success': True, 'lyrics': lyrics})
    except: pass
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

@app.route('/api/chat/<section>', methods=['GET'])
def get_chat(section):
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM class_chats WHERE section = %s ORDER BY created_at ASC", (section,))
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM class_chats WHERE section = ? ORDER BY created_at ASC", (section,))
    rows = cur.fetchall()
    items = [dict(row) for row in rows]
    cur.close()
    conn.close()
    return jsonify(items)

@app.route('/api/chat/<section>', methods=['POST'])
def post_chat(section):
    data = request.json
    sender_name = data.get('sender_name', 'Anonymous').strip()
    sender_net_id = data.get('sender_net_id', '').lower().strip()
    message = data.get('message', '').strip()
    image_url = data.get('image_url', '')
    audio_url = data.get('audio_url', '')
    now = datetime.now().isoformat()
    
    if not message and not image_url and not audio_url:
        return jsonify({'success': False, 'error': 'Empty message'})
        
    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("INSERT INTO class_chats (section, sender_name, sender_net_id, message, image_url, audio_url, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (section, sender_name, sender_net_id, message, image_url, audio_url, now))
        else:
            cur.execute("INSERT INTO class_chats (section, sender_name, sender_net_id, message, image_url, audio_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (section, sender_name, sender_net_id, message, image_url, audio_url, now))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/chat/delete/<int:msg_id>', methods=['POST'])
def delete_chat(msg_id):
    data = request.json
    net_id = data.get('net_id', '').lower().strip()
    mode = data.get('mode', 'me') # 'me' or 'everyone'
    
    conn = get_db()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("SELECT sender_net_id, deleted_by FROM class_chats WHERE id = %s", (msg_id,))
        else:
            cur.execute("SELECT sender_net_id, deleted_by FROM class_chats WHERE id = ?", (msg_id,))
            
        row = cur.fetchone()
        if not row: return jsonify({'success': False, 'error': 'Message not found'})
        
        sender = row[0]
        deleted_by_list = row[1] or ""
        
        if mode == 'everyone':
            if sender != net_id:
                return jsonify({'success': False, 'error': 'Cannot delete others message for everyone'})
            if DATABASE_URL:
                cur.execute("UPDATE class_chats SET deleted_for_all = 1, message = ' This message was deleted', image_url = '' WHERE id = %s", (msg_id,))
            else:
                cur.execute("UPDATE class_chats SET deleted_for_all = 1, message = ' This message was deleted', image_url = '' WHERE id = ?", (msg_id,))
        else:
            new_deleted = deleted_by_list + f",{net_id}" if deleted_by_list else net_id
            if DATABASE_URL:
                cur.execute("UPDATE class_chats SET deleted_by = %s WHERE id = %s", (new_deleted, msg_id))
            else:
                cur.execute("UPDATE class_chats SET deleted_by = ? WHERE id = ?", (new_deleted, msg_id))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
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
    return jsonify(items)

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
def ping(): return 'pong', 200

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
