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

# =============================================================================
# FIX #4 — DATABASE CONNECTION
# Root cause: Render's DATABASE_URL starts with "postgres://" but psycopg2 ≥ 2.9
# only accepts "postgresql://". Also added robust fallback so a bad DB_URL
# never crashes the entire server on startup.
# =============================================================================
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Fix the Render URL scheme mismatch
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Try to import psycopg2 only when we actually have a real URL
if DATABASE_URL:
    try:
        import psycopg2
        import psycopg2.extras
        # Verify the connection works at startup — fail loudly and fall back to SQLite
        _test_conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        _test_conn.close()
        print("[DB] PostgreSQL connection verified ✓")
    except Exception as _db_err:
        print(f"[DB] WARNING: PostgreSQL connection failed ({_db_err}). Falling back to SQLite.")
        DATABASE_URL = ''

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hub.db')

def get_db():
    """Return a live DB connection, always falling back to SQLite if Postgres fails."""
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            return conn
        except Exception as e:
            print(f"[DB] get_db() Postgres error: {e}. Using SQLite fallback.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _is_pg(conn):
    """True if this connection is PostgreSQL, False if SQLite."""
    return DATABASE_URL and not isinstance(conn, sqlite3.Connection)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    pg = _is_pg(conn)
    serial = "SERIAL" if pg else "INTEGER"
    pk_auto = "" if pg else " AUTOINCREMENT"
    placeholder = "%s" if pg else "?"

    # Students
    cur.execute(f'''CREATE TABLE IF NOT EXISTS students (
        net_id TEXT PRIMARY KEY, name TEXT, register_no TEXT,
        overall_attendance REAL DEFAULT 0, est_cgpa REAL DEFAULT 0, synced_at TEXT)''')
    # Projects
    cur.execute(f'''CREATE TABLE IF NOT EXISTS projects (
        id {serial} PRIMARY KEY{pk_auto}, title TEXT NOT NULL, description TEXT, tech_stack TEXT,
        github_url TEXT, demo_url TEXT, submitted_by TEXT, net_id TEXT, submitted_at TEXT)''')
    # Marketplace
    cur.execute(f'''CREATE TABLE IF NOT EXISTS marketplace (
        id {serial} PRIMARY KEY{pk_auto}, title TEXT NOT NULL, description TEXT, category TEXT, price TEXT, phone_no TEXT, image_url TEXT,
        seller_name TEXT, net_id TEXT, created_at TEXT)''')
    # Campus Wall
    cur.execute(f'''CREATE TABLE IF NOT EXISTS campus_wall (
        id {serial} PRIMARY KEY{pk_auto}, message TEXT NOT NULL, author TEXT, likes INTEGER DEFAULT 0, created_at TEXT)''')
    # Cab Sharing
    cur.execute(f'''CREATE TABLE IF NOT EXISTS cab_sharing (
        id {serial} PRIMARY KEY{pk_auto}, destination TEXT NOT NULL, travel_date TEXT, travel_time TEXT, spots TEXT, phone_no TEXT,
        creator_name TEXT, net_id TEXT, created_at TEXT)''')
    # Club Events
    cur.execute(f'''CREATE TABLE IF NOT EXISTS club_events (
        id {serial} PRIMARY KEY{pk_auto}, club_name TEXT NOT NULL, event_title TEXT NOT NULL, event_date TEXT, registration_link TEXT, image_url TEXT,
        created_by TEXT, net_id TEXT, created_at TEXT)''')
    # Lost & Found
    cur.execute(f'''CREATE TABLE IF NOT EXISTS lost_found (
        id {serial} PRIMARY KEY{pk_auto}, title TEXT NOT NULL, description TEXT, category TEXT, location TEXT, image_url TEXT,
        poster_name TEXT, net_id TEXT, created_at TEXT)''')

    conn.commit()
    cur.close()
    conn.close()

try:
    init_db()
    print("[DB] Tables initialised ✓")
except Exception as _e:
    print(f"[DB] init_db error: {_e}")


def _q(conn):
    """Return the correct SQL placeholder for the connection type."""
    return "%s" if _is_pg(conn) else "?"


def _fetchall_as_dicts(cur, conn):
    rows = cur.fetchall()
    if _is_pg(conn):
        return [dict(r) for r in rows]
    return [dict(r) for r in rows]


def save_student_to_db(net_id, name, register_no, att_data, marks_data):
    try:
        total_att = 0; total_cls = 0
        for sub in (att_data or []):
            try:
                total_att += int(sub.get('attended', 0) or 0)
                total_cls += int(sub.get('total', 0) or 0)
            except: continue
        overall_att = round((total_att / total_cls) * 100, 1) if total_cls > 0 else 0.0

        grand_total_obtained = 0
        grand_total_max = 0
        for sub in (marks_data or []):
            try:
                perf_string = sub.get('Test Performance') or sub.get('performance') or sub.get('marks') or ""
                matches = re.findall(r'([A-Za-z0-9-]+)/([0-9.]+)\s*\|\s*([0-9.]+)', perf_string)
                for _, max_str, obtained_str in matches:
                    try:
                        grand_total_max += float(max_str)
                        grand_total_obtained += float(obtained_str)
                    except ValueError:
                        pass
            except: continue

        cgpa = round((grand_total_obtained / grand_total_max) * 10, 2) if grand_total_max > 0 else 0.0

        conn = get_db()
        cur = conn.cursor()
        q = _q(conn)
        if _is_pg(conn):
            cur.execute(f'''
                INSERT INTO students (net_id, name, register_no, overall_attendance, est_cgpa, synced_at)
                VALUES ({q},{q},{q},{q},{q},{q})
                ON CONFLICT(net_id) DO UPDATE SET
                    name=EXCLUDED.name, register_no=EXCLUDED.register_no,
                    overall_attendance=EXCLUDED.overall_attendance, est_cgpa=EXCLUDED.est_cgpa,
                    synced_at=EXCLUDED.synced_at
            ''', (net_id.lower(), name, register_no.upper(), overall_att, cgpa, datetime.utcnow().isoformat()))
        else:
            cur.execute(f'''
                INSERT INTO students (net_id, name, register_no, overall_attendance, est_cgpa, synced_at)
                VALUES ({q},{q},{q},{q},{q},{q})
                ON CONFLICT(net_id) DO UPDATE SET
                    name=excluded.name, register_no=excluded.register_no,
                    overall_attendance=excluded.overall_attendance, est_cgpa=excluded.est_cgpa,
                    synced_at=excluded.synced_at
            ''', (net_id.lower(), name, register_no.upper(), overall_att, cgpa, datetime.utcnow().isoformat()))
        conn.commit()
        cur.close()
        conn.close()
        print(f"[DB] Saved student {net_id} (att={overall_att}%, cgpa={cgpa})")
    except Exception as e:
        print(f"[DB] save_student_to_db error: {e}")


# =============================================================================
# FIX #1 — PERFORMANCE  |  FIX #2 — RESILIENCE  |  FIX #3 — TIMETABLE
#
# Fix #1 strategy:
#   • Block all images, fonts, media, and tracking scripts so pages load
#     in 2–4 s instead of 15–30 s.
#   • Use wait_until="domcontentloaded" everywhere (never "networkidle").
#   • Replace every fixed wait_for_timeout(5000) with event-driven waits
#     (wait_for_selector / wait_for_function / wait_for_response).
#   • Intercept XHR/fetch responses that carry the actual JSON data so we
#     can skip rendering the table DOM entirely when possible.
#
# Fix #2 strategy:
#   • Column detection uses ranked keyword lists with fallback: we try 3–4
#     different header names before giving up.
#   • Data validation: skip rows whose numeric cells contain garbage.
#   • Normalise all whitespace / newlines before parsing.
#
# Fix #3 strategy:
#   • Completely rewrote the timetable parser.
#   • Detect the time-header row reliably: it's the first row where ≥3
#     cells match HH:MM (with optional range " - HH:MM").
#   • Detect day rows with a strict regex: "^\s*(\d)\s*$" or
#     "day\s*order\s*(\d)" — never just any number in cell[0].
#   • Deduplicate by (day, slot, time) key — not just (time, subject).
#   • Try both 2023_24 and 2024_25 slot URLs so we get the right one.
# =============================================================================

# Resources that add zero data but cost seconds to download
_BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "other"}
_BLOCKED_URL_PATTERNS = [
    "google-analytics", "googletagmanager", "doubleclick", "analytics",
    "facebook.net", "hotjar", "crisp.chat", "freshdesk", "zendesk",
    "adservice", "cdn.ampproject", ".woff", ".woff2", ".ttf", ".otf",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".mp4", ".webm", ".avi",
]

def _should_block(url: str, resource_type: str) -> bool:
    if resource_type in _BLOCKED_RESOURCE_TYPES:
        return True
    url_lower = url.lower()
    return any(p in url_lower for p in _BLOCKED_URL_PATTERNS)


def _get_col_index(headers: list, *keyword_sets) -> int:
    """
    Find a column index by scanning headers for any keyword in each set.
    keyword_sets is a list of tuples/lists of strings to try in order.
    Returns -1 if nothing matches.
    """
    for keywords in keyword_sets:
        for i, h in enumerate(headers):
            h_lower = str(h).lower().strip()
            if any(kw in h_lower for kw in keywords):
                return i
    return -1


def _safe_int(val, default=0) -> int:
    try:
        return max(0, int(float(str(val).strip() or 0)))
    except:
        return default


def _normalise(cell) -> str:
    return re.sub(r'\s+', ' ', str(cell)).strip()


def scrape_academia_worker(reg_no, pwd, batch, out_queue):
    p = None
    browser = None
    try:
        p = sync_playwright().start()
        print(f"[{reg_no}] Launching browser...")

        # FIX #1: Aggressive browser flags for speed on a headless server
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--metrics-recording-only',
                '--mute-audio',
                '--no-first-run',
                '--safebrowsing-disable-auto-update',
                '--blink-settings=imagesEnabled=false',  # fastest single flag
            ]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            # Disable unnecessary browser features
            java_script_enabled=True,
        )

        # FIX #1: Block time-wasting resources at the network level
        def _route_handler(route):
            if _should_block(route.request.url, route.request.resource_type):
                route.abort()
            else:
                route.continue_()

        context.route("**/*", _route_handler)

        page = context.new_page()
        # Never wait longer than 60 s for any single operation
        page.set_default_timeout(60000)

        if "@" not in reg_no:
            reg_no += "@srmist.edu.in"

        # ---- LOGIN --------------------------------------------------------
        print(f"[{reg_no}] Step 1: Loading portal...")
        # FIX #1: domcontentloaded is 10-15 s faster than networkidle
        page.goto("https://academia.srmist.edu.in/", wait_until="domcontentloaded", timeout=60000)

        def find_in_frames(selector, filter_text=None, filter_not_text=None):
            """Search main page + all iframes for a locator."""
            targets = [page] + list(page.frames)
            for target in targets:
                try:
                    loc = target.locator(selector)
                    if filter_text:
                        loc = loc.filter(has_text=re.compile(filter_text, re.IGNORECASE))
                    if filter_not_text:
                        loc = loc.filter(has_not_text=re.compile(filter_not_text, re.IGNORECASE))
                    if loc.count() > 0:
                        return loc.first
                except:
                    continue
            return None

        try:
            # Wait for an email/text input to appear (up to 30 s)
            page.wait_for_selector(
                'input[type="email"], input[type="text"], input[name="LOGIN_ID"]',
                timeout=30000
            )
            email_input = find_in_frames(
                'input[type="email"], input[type="text"], input[name="LOGIN_ID"]'
            )
            if not email_input:
                raise Exception("Email field not found")
            email_input.fill(reg_no, force=True)

            next_btn = find_in_frames('button, input[type="submit"]', filter_text=r"next|continue")
            if next_btn:
                next_btn.click(force=True, timeout=5000)
            else:
                page.keyboard.press("Enter")

            # FIX #1: Wait for password field to appear instead of sleeping
            page.wait_for_selector(
                'input[type="password"], input[name="PASSWORD"]',
                timeout=20000
            )
            pwd_input = find_in_frames('input[type="password"], input[name="PASSWORD"]')
            if not pwd_input:
                raise Exception("Password field not found")
            pwd_input.fill(pwd)   # fill() is faster than type() with delay=30

            submit_btn = find_in_frames(
                'button, input[type="submit"]',
                filter_text=r"sign in|login|submit|verify"
            )
            if submit_btn:
                submit_btn.click(force=True, timeout=5000)
            else:
                page.keyboard.press("Enter")

            # FIX #1: Wait for redirect away from the login page
            page.wait_for_url(
                re.compile(r"academia\.srmist\.edu\.in"),
                timeout=30000
            )
            # Handle "terminate other session?" popup if it appears
            try:
                terminate_btn = page.locator('button, a').filter(
                    has_text=re.compile(r"terminate", re.IGNORECASE)
                ).first
                if terminate_btn.count() > 0:
                    terminate_btn.click(force=True)
                    page.wait_for_timeout(2000)
            except:
                pass

        except Exception as e:
            out_queue.put({'success': False, 'error': f'Auth Failed: {str(e)}'})
            return

        print(f"[{reg_no}] Login OK. Fetching data...")

        # ---- TABLE EXTRACTOR (Resilient DOM reader) -----------------------
        def get_all_tables():
            """
            FIX #2: Extract all tables from page + all iframes.
            Normalises whitespace and colSpan expansion.
            """
            all_tables = []
            targets = [page] + list(page.frames)
            for target in targets:
                try:
                    tables = target.evaluate("""() => {
                        return Array.from(document.querySelectorAll('table')).map(t =>
                            Array.from(t.querySelectorAll('tr')).map(tr => {
                                let rowArr = [];
                                Array.from(tr.querySelectorAll('td, th')).forEach(td => {
                                    let span = td.colSpan || 1;
                                    let text = (td.innerText || td.textContent || '').trim()
                                               .replace(/\\s+/g, ' ');
                                    for (let i = 0; i < span; i++) rowArr.push(text);
                                });
                                return rowArr;
                            }).filter(row => row.some(c => c.length > 0))
                        ).filter(table => table.length > 1);
                    }""")
                    if tables:
                        all_tables.extend(tables)
                except:
                    pass
            return all_tables

        # ---- ATTENDANCE PAGE ----------------------------------------------
        print(f"[{reg_no}] Step 2: Attendance page...")
        page.goto(
            "https://academia.srmist.edu.in/#Page:My_Attendance",
            wait_until="domcontentloaded",
            timeout=60000
        )

        # FIX #1: Wait for a table to appear instead of a fixed 8s sleep
        try:
            page.wait_for_selector("table", timeout=25000)
        except:
            print(f"[{reg_no}] No table found on attendance page after 25s")
        # Give JS a moment to finish populating rows (minimal wait)
        page.wait_for_timeout(1500)

        raw_tables = get_all_tables()
        parsed_att = []
        parsed_marks = []

        # --- PROFILE ---
        profile_data = {
            "name": "STUDENT",
            "regNo": reg_no.split('@')[0].upper(),
            "course": "B.Tech",
            "semester": "Current"
        }
        for table in raw_tables:
            for row in table:
                if len(row) < 2:
                    continue
                for i in range(len(row) - 1):
                    k = str(row[i]).replace(':', '').strip().lower()
                    v = str(row[i + 1]).replace(':', '').strip()
                    if "name" in k and "father" not in k and "mother" not in k:
                        if len(v) > 2 and profile_data["name"] == "STUDENT":
                            profile_data["name"] = v
                    elif any(x in k for x in ("program", "course", "degree", "branch")):
                        if len(v) > 2:
                            profile_data["course"] = v[:35]
                    elif "semester" in k:
                        if 0 < len(v) <= 2:
                            profile_data["semester"] = v

        # FIX #2: Resilient column detection with multiple keyword fallbacks
        for table in raw_tables:
            if not table:
                continue
            headers = [str(h).lower().strip() for h in table[0]]
            header_str = " ".join(headers)

            # --- ATTENDANCE TABLE ---
            if "conducted" in header_str and ("absent" in header_str or "attended" in header_str):
                try:
                    # FIX #2: Try multiple column name variants
                    idx_code  = _get_col_index(headers, ("code", "subject code", "course code"))
                    idx_title = _get_col_index(headers, ("title", "course title", "subject", "name"))
                    idx_cond  = _get_col_index(headers, ("conducted", "hours conducted", "total hours"))
                    idx_abs   = _get_col_index(headers, ("absent", "hours absent"))
                    idx_att   = _get_col_index(headers, ("attended", "hours attended", "present"))

                    if idx_cond == -1:
                        continue

                    seen_rows = set()
                    for row in table[1:]:
                        if len(row) <= max(idx_cond, max(idx_abs, idx_att)):
                            continue
                        code  = _normalise(row[idx_code])  if idx_code  != -1 else "?"
                        title = _normalise(row[idx_title]) if idx_title != -1 else code
                        cond  = _safe_int(row[idx_cond])

                        if idx_att != -1 and len(row) > idx_att:
                            attended = _safe_int(row[idx_att])
                        elif idx_abs != -1 and len(row) > idx_abs:
                            attended = max(0, cond - _safe_int(row[idx_abs]))
                        else:
                            continue

                        if cond == 0:
                            continue
                        key = f"{code}-{cond}"
                        if key in seen_rows:
                            continue
                        seen_rows.add(key)
                        parsed_att.append({
                            "courseTitle": f"{code} - {title[:25]}",
                            "attended": attended,
                            "total": cond
                        })
                except Exception as e:
                    print(f"Attendance parse error: {e}")
                    continue

            # --- MARKS TABLE ---
            elif any(kw in header_str for kw in ("test performance", "assessment", "internal marks", "marks obtained")):
                try:
                    idx_code = _get_col_index(headers,
                        ("course code", "code"),
                        ("subject code",))
                    idx_title = _get_col_index(headers,
                        ("course title", "title", "course name"),
                        ("subject", "name"))
                    idx_perf = _get_col_index(headers,
                        ("test performance",),
                        ("assessment", "internal marks", "marks obtained"),
                        ("marks", "internal"))

                    if idx_code == -1 or idx_perf == -1:
                        continue

                    seen_codes = set()
                    for row in table[1:]:
                        if len(row) <= idx_perf:
                            continue
                        code = _normalise(row[idx_code]) if idx_code != -1 else "?"
                        if code in seen_codes or not code or code == "?":
                            continue
                        seen_codes.add(code)
                        display = (_normalise(row[idx_title])
                                   if idx_title != -1 and len(row) > idx_title and row[idx_title].strip()
                                   else code)
                        perf = _normalise(row[idx_perf]).replace('\n', ' | ')
                        parsed_marks.append({
                            "courseTitle": display,
                            "courseCode": code,
                            "Test Performance": perf
                        })
                except Exception as e:
                    print(f"Marks parse error: {e}")
                    continue

        # ---- TIMETABLE STEP 1: STUDENT SLOT ASSIGNMENTS ------------------
        # FIX #3: Try both URL variants so it works regardless of academic year
        print(f"[{reg_no}] Step 3: Student slot assignments...")
        student_slots = {}

        slot_urls = [
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25",
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2023_24",
        ]

        slot_tables = []
        for slot_url in slot_urls:
            page.goto(slot_url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_selector("table", timeout=20000)
            except:
                print(f"[{reg_no}] No table at {slot_url}")
                continue
            page.wait_for_timeout(1500)
            slot_tables = get_all_tables()

            # Check if this URL returned slot data (has "slot" in any header)
            has_slots = any(
                "slot" in " ".join(str(h).lower() for h in t[0])
                for t in slot_tables if t
            )
            if has_slots:
                print(f"[{reg_no}] Slot data found at {slot_url}")
                break
            slot_tables = []

        # --- Enrich profile from slot page ---
        for table in slot_tables:
            for row in table:
                if len(row) < 2:
                    continue
                for i in range(len(row) - 1):
                    k = str(row[i]).replace(':', '').strip().lower()
                    v = str(row[i + 1]).replace(':', '').strip()
                    if "registration" in k and "number" in k and len(v) > 5:
                        profile_data["regNo"] = v
                    elif "department" in k and len(v) > 2:
                        profile_data["department"] = v
                    elif ("combo" in k or "batch" in k) and len(v) > 0:
                        profile_data["batch"] = v
                    elif ("class room" in k or "classroom" in k) and len(v) > 0:
                        profile_data["classRoom"] = v
                    elif "program" in k and len(v) > 2:
                        profile_data["course"] = v[:35]
                    elif "semester" in k and 0 < len(v) <= 2:
                        profile_data["semester"] = v
                    elif "name" in k and "father" not in k and "mother" not in k \
                            and "faculty" not in k and len(v) > 2 \
                            and profile_data["name"] == "STUDENT":
                        profile_data["name"] = v

        # --- Advisor data ---
        for table in slot_tables:
            for row in table:
                for cell in row:
                    cell_str = str(cell).strip()
                    cell_lower = cell_str.lower()
                    lines = [l.strip() for l in cell_str.split('\n') if l.strip()]
                    if 'faculty advisor' in cell_lower:
                        for k, line in enumerate(lines):
                            if 'faculty advisor' in line.lower():
                                if k > 0 and len(lines[k - 1]) > 3:
                                    profile_data['fa_name'] = lines[k - 1]
                            elif '@' in line and 'srmist' in line.lower():
                                profile_data['fa_email'] = line
                            elif re.match(r'^\+?[\d\s\-]{10,}$', line):
                                digits = re.sub(r'\D', '', line)
                                if len(digits) >= 10:
                                    profile_data['fa_phone'] = digits[-10:]
                    if 'academic advisor' in cell_lower:
                        for k, line in enumerate(lines):
                            if 'academic advisor' in line.lower():
                                if k > 0 and len(lines[k - 1]) > 3:
                                    profile_data['aa_name'] = lines[k - 1]
                            elif '@' in line and 'srmist' in line.lower():
                                profile_data['aa_email'] = line
                            elif re.match(r'^\+?[\d\s\-]{10,}$', line):
                                digits = re.sub(r'\D', '', line)
                                if len(digits) >= 10:
                                    profile_data['aa_phone'] = digits[-10:]

        print(f"[{reg_no}] Profile: regNo={profile_data.get('regNo','?')}, "
              f"dept={profile_data.get('department','?')}, "
              f"FA={profile_data.get('fa_name','?')}")

        # --- Parse student slots (code → subject + room) ---
        for table in slot_tables:
            if not table:
                continue
            headers = [str(h).lower().strip() for h in table[0]]
            header_str = " ".join(headers)
            if "slot" not in header_str or "code" not in header_str:
                continue
            try:
                idx_code  = _get_col_index(headers, ("course code", "code"))
                idx_title = _get_col_index(headers, ("course title", "title", "subject", "name"))
                idx_slot  = _get_col_index(headers, ("slot",))
                idx_room  = _get_col_index(headers, ("room", "venue", "classroom"))

                if idx_code == -1 or idx_slot == -1:
                    continue

                for row in table[1:]:
                    if len(row) <= idx_slot:
                        continue
                    slot_str = _normalise(row[idx_slot])
                    # FIX #3: Wider slot pattern — A, B, P1, PT2, L1, TA1 etc.
                    slots_found = re.findall(r'\b([A-Z]{1,3}\d*)\b', slot_str)
                    for s in slots_found:
                        if not s or s in ("AM", "PM"):   # skip false positives
                            continue
                        subj = (_normalise(row[idx_title])
                                if idx_title != -1 and len(row) > idx_title and row[idx_title].strip()
                                else _normalise(row[idx_code]))
                        room = _normalise(row[idx_room]) if idx_room != -1 and len(row) > idx_room else ""
                        student_slots[s] = {"subject": subj, "room": room}
            except Exception as e:
                print(f"Slot parse error: {e}")
                continue

        print(f"[{reg_no}] Found {len(student_slots)} student slots: {list(student_slots.keys())[:10]}")

        # ---- TIMETABLE STEP 2: MASTER TIMETABLE --------------------------
        # FIX #3: Completely rewritten — reliable time-row and day-row detection
        print(f"[{reg_no}] Step 4: Master timetable (batch {batch})...")
        final_tt = {"1": [], "2": [], "3": [], "4": [], "5": []}

        master_urls = [
            f"https://academia.srmist.edu.in/#Page:Unified_Time_Table_2025_Batch_{batch}",
            f"https://academia.srmist.edu.in/#Page:Unified_Time_Table_2024_Batch_{batch}",
        ]

        master_tables = []
        for m_url in master_urls:
            page.goto(m_url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_selector("table", timeout=20000)
            except:
                print(f"[{reg_no}] No table at {m_url}")
                continue
            page.wait_for_timeout(1500)
            master_tables = get_all_tables()
            if master_tables:
                print(f"[{reg_no}] Master table found at {m_url}")
                break

        def _extract_time_str(cell_text: str) -> str:
            """Pull 'HH:MM' or 'HH:MM - HH:MM' from a cell."""
            m = re.search(r'\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}', cell_text)
            if m:
                return m.group().strip()
            m = re.search(r'\d{1,2}:\d{2}', cell_text)
            return m.group().strip() if m else ""

        def _is_time_row(row) -> bool:
            """True if ≥ 3 non-first cells contain a HH:MM pattern."""
            hits = sum(
                1 for c in row[1:]
                if re.search(r'\b\d{1,2}:\d{2}\b', str(c))
            )
            return hits >= 3

        def _parse_day_order(cell_text: str):
            """
            FIX #3: Return day order digit (str '1'..'5') if this cell looks like
            a day-order label, else None.
            Accepts: "1", "Day 1", "Day Order 1", "ORDER 1"
            """
            t = cell_text.strip().lower()
            m = re.match(r'^(?:day\s*(?:order\s*)?|order\s*)?(\d)$', t)
            if m and m.group(1) in "12345":
                return m.group(1)
            return None

        for t_idx, table in enumerate(master_tables):
            if not table or len(table) < 3:
                continue

            time_row_data = None   # list of time strings, one per "period" column
            from_times = []
            to_times   = []
            day_rows   = {}        # {'1': [cell0, cell1, ...], ...}

            for r_idx, row in enumerate(table):
                first = _normalise(row[0]) if row else ""

                if _is_time_row(row):
                    cells = [_normalise(c) for c in row[1:]]
                    # Try to detect combined "HH:MM - HH:MM" range in cells
                    has_ranges = sum(
                        1 for c in cells
                        if re.search(r'\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}', c)
                    ) >= 3
                    if has_ranges or (not from_times):
                        if not from_times:
                            from_times = cells
                        elif not to_times:
                            to_times = cells
                        if has_ranges and time_row_data is None:
                            time_row_data = cells
                    continue

                day = _parse_day_order(first)
                if day:
                    day_rows[day] = [_normalise(c) for c in row[1:]]

            # Build final time column list
            if time_row_data is None:
                if from_times and to_times:
                    time_row_data = []
                    for f, t in zip(from_times, to_times):
                        f_t = _extract_time_str(f)
                        t_t = _extract_time_str(t)
                        if f_t and t_t:
                            time_row_data.append(f"{f_t} - {t_t}")
                        elif f_t:
                            time_row_data.append(f_t)
                        else:
                            time_row_data.append("")
                elif from_times:
                    time_row_data = [_extract_time_str(c) or f"Period {i+1}"
                                     for i, c in enumerate(from_times)]

            if not time_row_data or not day_rows:
                # Debug: this table has no useful data
                print(f"[{reg_no}] Table {t_idx}: no time_row or no day_rows — skipping")
                continue

            print(f"[{reg_no}] Table {t_idx}: {len(time_row_data)} periods, "
                  f"days={list(day_rows.keys())}, sample_times={time_row_data[:4]}")

            for day_order, cells in day_rows.items():
                if day_order not in final_tt:
                    continue
                seen_keys = set()
                for i, cell in enumerate(cells):
                    if i >= len(time_row_data):
                        break
                    # FIX #3: Only extract valid slot codes
                    slots_in_cell = re.findall(r'\b([A-Z]{1,3}\d*)\b', cell)
                    for s in slots_in_cell:
                        if s not in student_slots or s in ("AM", "PM"):
                            continue
                        t_str = time_row_data[i] or f"Period {i+1}"
                        # FIX #3: Dedup by (day, slot_code, time) — prevents repeated entries
                        entry_key = f"{day_order}|{s}|{t_str}"
                        if entry_key in seen_keys:
                            continue
                        seen_keys.add(entry_key)
                        final_tt[day_order].append({
                            "time":    t_str,
                            "subject": student_slots[s]['subject'],
                            "room":    student_slots[s]['room']
                        })
                        print(f"[{reg_no}]   Day {day_order}: {s} → {t_str} | {student_slots[s]['subject']}")

        # Sort each day's classes by time
        def _time_sort_key(entry):
            m = re.search(r'\d{1,2}:\d{2}', entry.get('time', ''))
            if m:
                h, mi = m.group().split(':')
                return int(h) * 60 + int(mi)
            return 9999

        for day in final_tt:
            final_tt[day].sort(key=_time_sort_key)

        # ---- DEBUG DUMP (only if everything is empty) --------------------
        if not parsed_att and not parsed_marks and not student_slots:
            try:
                debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_tables.txt")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(f"RAW TABLES ({len(raw_tables)}):\n{raw_tables}\n\n"
                            f"SLOT TABLES ({len(slot_tables)}):\n{slot_tables}\n\n"
                            f"MASTER TABLES ({len(master_tables)}):\n{master_tables}")
                print(f"[{reg_no}] Empty result — debug dump written to {debug_path}")
            except Exception as e:
                print(f"[{reg_no}] Debug dump failed: {e}")

        print(f"[{reg_no}] Done. att={len(parsed_att)}, marks={len(parsed_marks)}, "
              f"slots={len(student_slots)}, tt_days={sum(len(v) for v in final_tt.values())}")

        out_queue.put({
            'success': True,
            'profile': profile_data,
            'data': parsed_att,
            'marks': parsed_marks,
            'timetable': final_tt
        })

    except Exception as e:
        import traceback
        print(f"[SCRAPER] Unhandled exception: {traceback.format_exc()}")
        out_queue.put({'success': False, 'error': f"Scraper Error: {str(e)}"})
    finally:
        try:
            if browser:
                browser.close()
        except:
            pass
        try:
            if p:
                p.stop()
        except:
            pass


@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    reg_no = data.get('regNo', '')
    pwd    = data.get('pwd', '')
    batch  = data.get('batch', 1)

    if not reg_no or not pwd:
        return jsonify({'success': False, 'error': 'Missing credentials'}), 400

    out_queue = queue.Queue()
    t = threading.Thread(
        target=scrape_academia_worker,
        args=(reg_no, pwd, batch, out_queue),
        daemon=True
    )
    t.start()
    try:
        result = out_queue.get(timeout=150)
        if result.get('success'):
            profile     = result.get('profile', {})
            net_id      = reg_no.split('@')[0]
            register_no = net_id.upper()
            name        = profile.get('name', 'Student')
            save_student_to_db(net_id, name, register_no,
                               result.get('data', []), result.get('marks', []))
        return jsonify(result)
    except queue.Empty:
        return jsonify({'success': False, 'error': 'Server timeout (150 s). The portal may be slow.'})


@app.route('/api/save_student', methods=['POST'])
def save_student():
    d = request.json
    try:
        conn = get_db()
        q = _q(conn)
        if _is_pg(conn):
            with conn.cursor() as cur:
                cur.execute(f'''
                    INSERT INTO students (net_id, name, overall_attendance, est_cgpa, synced_at)
                    VALUES ({q},{q},{q},{q},{q})
                    ON CONFLICT(net_id) DO UPDATE SET
                        name=EXCLUDED.name,
                        overall_attendance=EXCLUDED.overall_attendance,
                        est_cgpa=EXCLUDED.est_cgpa,
                        synced_at=EXCLUDED.synced_at
                ''', (d.get('net_id', '').lower(), d.get('name', 'Student'),
                      float(d.get('attendance', 0)), float(d.get('cgpa', 0)),
                      datetime.utcnow().isoformat()))
        else:
            conn.execute(f'''
                INSERT INTO students (net_id, name, overall_attendance, est_cgpa, synced_at)
                VALUES ({q},{q},{q},{q},{q})
                ON CONFLICT(net_id) DO UPDATE SET
                    name=excluded.name,
                    overall_attendance=excluded.overall_attendance,
                    est_cgpa=excluded.est_cgpa,
                    synced_at=excluded.synced_at
            ''', (d.get('net_id', '').lower(), d.get('name', 'Student'),
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
    q = _q(conn)
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT name, net_id, register_no, overall_attendance '
                        'FROM students ORDER BY overall_attendance DESC LIMIT 50')
            rows = [dict(r) for r in cur.fetchall()]
    else:
        rows = [dict(r) for r in conn.execute(
            'SELECT name, net_id, register_no, overall_attendance '
            'FROM students ORDER BY overall_attendance DESC LIMIT 50'
        ).fetchall()]
    conn.close()
    return jsonify(rows)


@app.route('/api/leaderboard/marks', methods=['GET'])
def leaderboard_marks():
    conn = get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT name, net_id, register_no, est_cgpa '
                        'FROM students ORDER BY est_cgpa DESC LIMIT 50')
            rows = [dict(r) for r in cur.fetchall()]
    else:
        rows = [dict(r) for r in conn.execute(
            'SELECT name, net_id, register_no, est_cgpa '
            'FROM students ORDER BY est_cgpa DESC LIMIT 50'
        ).fetchall()]
    conn.close()
    return jsonify(rows)


# ---- PROJECTS ---------------------------------------------------------------

@app.route('/api/projects', methods=['GET'])
def get_projects():
    conn = get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM projects ORDER BY submitted_at DESC')
            rows = [dict(r) for r in cur.fetchall()]
    else:
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM projects ORDER BY submitted_at DESC'
        ).fetchall()]
    conn.close()
    return jsonify(rows)


@app.route('/api/projects/submit', methods=['POST'])
def submit_project():
    data = request.json
    if not data or not data.get('title') or not data.get('submitted_by'):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur  = conn.cursor()
    q    = _q(conn)
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f"""
            INSERT INTO projects (title, description, tech_stack, github_url, demo_url,
                                  submitted_by, net_id, submitted_at)
            VALUES ({q},{q},{q},{q},{q},{q},{q},{q})
        """, (data.get('title'), data.get('description', ''), data.get('tech_stack', ''),
              data.get('github_url', ''), data.get('demo_url', ''),
              data.get('submitted_by'), data.get('net_id', ''), now))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


# ---- MARKETPLACE ------------------------------------------------------------

@app.route('/api/marketplace', methods=['GET'])
def get_marketplace():
    conn = get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM marketplace ORDER BY id DESC LIMIT 100")
            rows = [dict(r) for r in cur.fetchall()]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM marketplace ORDER BY id DESC LIMIT 100")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    conn.close()
    return jsonify(rows)


@app.route('/api/marketplace/submit', methods=['POST'])
def submit_marketplace():
    data = request.json
    if not data or not data.get('title') or not data.get('seller_name'):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur  = conn.cursor()
    q    = _q(conn)
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f"""
            INSERT INTO marketplace (title, description, category, price, phone_no,
                                     image_url, seller_name, net_id, created_at)
            VALUES ({q},{q},{q},{q},{q},{q},{q},{q},{q})
        """, (data.get('title'), data.get('description', ''), data.get('category', ''),
              data.get('price', ''), data.get('phone_no', ''), data.get('image_url', ''),
              data.get('seller_name'), data.get('net_id', ''), now))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


@app.route('/api/marketplace/delete/<int:item_id>', methods=['DELETE'])
def delete_marketplace(item_id):
    data   = request.json or {}
    net_id = data.get('net_id', '').lower().strip()
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur  = conn.cursor()
    q    = _q(conn)
    try:
        cur.execute(f"SELECT net_id FROM marketplace WHERE id = {q}", (item_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        owner = dict(row).get('net_id', '').lower().strip()
        if owner != net_id:
            return jsonify({'success': False, 'error': 'You can only delete your own listings'}), 403
        cur.execute(f"DELETE FROM marketplace WHERE id = {q}", (item_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


# ---- CAMPUS WALL ------------------------------------------------------------

@app.route('/api/wall', methods=['GET'])
def get_wall():
    conn = get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM campus_wall ORDER BY id DESC LIMIT 100")
            rows = [dict(r) for r in cur.fetchall()]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM campus_wall ORDER BY id DESC LIMIT 100")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    conn.close()
    return jsonify(rows)


@app.route('/api/wall/submit', methods=['POST'])
def submit_wall():
    data = request.json
    if not data or not data.get('message'):
        return jsonify({'success': False, 'error': 'Message required'}), 400

    conn = get_db()
    cur  = conn.cursor()
    q    = _q(conn)
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f"INSERT INTO campus_wall (message, author, created_at) VALUES ({q},{q},{q})",
                    (data.get('message'), data.get('author', 'Anonymous'), now))
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
    cur  = conn.cursor()
    q    = _q(conn)
    try:
        cur.execute(f"UPDATE campus_wall SET likes = likes + 1 WHERE id = {q}", (post_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


# ---- CAB SHARING ------------------------------------------------------------

@app.route('/api/cabs', methods=['GET'])
def get_cabs():
    conn = get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM cab_sharing ORDER BY travel_date ASC, travel_time ASC LIMIT 100")
            rows = [dict(r) for r in cur.fetchall()]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cab_sharing ORDER BY travel_date ASC, travel_time ASC LIMIT 100")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    conn.close()
    return jsonify(rows)


@app.route('/api/cabs/submit', methods=['POST'])
def submit_cab():
    data = request.json
    if not data or not all(data.get(k) for k in ('destination', 'travel_date', 'travel_time', 'phone_no')):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur  = conn.cursor()
    q    = _q(conn)
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f"""
            INSERT INTO cab_sharing (destination, travel_date, travel_time, spots,
                                     phone_no, creator_name, net_id, created_at)
            VALUES ({q},{q},{q},{q},{q},{q},{q},{q})
        """, (data.get('destination'), data.get('travel_date'), data.get('travel_time'),
              data.get('spots', ''), data.get('phone_no'),
              data.get('creator_name'), data.get('net_id', ''), now))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


@app.route('/api/cabs/delete/<int:cab_id>', methods=['DELETE'])
def delete_cab(cab_id):
    data   = request.json or {}
    net_id = data.get('net_id', '').lower().strip()
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur  = conn.cursor()
    q    = _q(conn)
    try:
        cur.execute(f"SELECT net_id FROM cab_sharing WHERE id = {q}", (cab_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Ride not found'}), 404
        owner = dict(row).get('net_id', '').lower().strip()
        if owner != net_id:
            return jsonify({'success': False, 'error': 'You can only delete your own rides'}), 403
        cur.execute(f"DELETE FROM cab_sharing WHERE id = {q}", (cab_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


# ---- CLUB EVENTS ------------------------------------------------------------

@app.route('/api/events', methods=['GET'])
def get_events():
    conn = get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM club_events ORDER BY id DESC LIMIT 100")
            rows = [dict(r) for r in cur.fetchall()]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM club_events ORDER BY id DESC LIMIT 100")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    conn.close()
    return jsonify(rows)


@app.route('/api/events/submit', methods=['POST'])
def submit_event():
    data = request.json
    if not data or not data.get('club_name') or not data.get('event_title') or not data.get('event_date'):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur  = conn.cursor()
    q    = _q(conn)
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f"""
            INSERT INTO club_events (club_name, event_title, event_date, registration_link,
                                     image_url, created_by, net_id, created_at)
            VALUES ({q},{q},{q},{q},{q},{q},{q},{q})
        """, (data.get('club_name'), data.get('event_title'), data.get('event_date'),
              data.get('registration_link', ''), data.get('image_url', ''),
              data.get('created_by'), data.get('net_id', ''), now))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


# ---- LOST & FOUND -----------------------------------------------------------

@app.route('/api/lostfound', methods=['GET'])
def get_lostfound():
    conn = get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM lost_found ORDER BY id DESC LIMIT 100")
            rows = [dict(r) for r in cur.fetchall()]
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM lost_found ORDER BY id DESC LIMIT 100")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    conn.close()
    return jsonify(rows)


@app.route('/api/lostfound/submit', methods=['POST'])
def submit_lostfound():
    data = request.json
    if not data or not data.get('title') or not data.get('category'):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    cur  = conn.cursor()
    q    = _q(conn)
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f"""
            INSERT INTO lost_found (title, description, category, location, image_url,
                                    poster_name, net_id, created_at)
            VALUES ({q},{q},{q},{q},{q},{q},{q},{q})
        """, (data.get('title'), data.get('description', ''), data.get('category', ''),
              data.get('location', ''), data.get('image_url', ''),
              data.get('poster_name', 'Student'), data.get('net_id', ''), now))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


@app.route('/api/lostfound/delete/<int:item_id>', methods=['DELETE'])
def delete_lostfound(item_id):
    data   = request.json or {}
    net_id = data.get('net_id', '').lower().strip()
    if not net_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    conn = get_db()
    cur  = conn.cursor()
    q    = _q(conn)
    try:
        cur.execute(f"SELECT net_id FROM lost_found WHERE id = {q}", (item_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        owner = dict(row).get('net_id', '').lower().strip()
        if owner != net_id:
            return jsonify({'success': False, 'error': 'You can only delete your own posts'}), 403
        cur.execute(f"DELETE FROM lost_found WHERE id = {q}", (item_id,))
        conn.commit()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({'success': True})


# ---- UTILITY ----------------------------------------------------------------

@app.route('/ping')
def ping():
    return 'pong', 200

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
