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
# DATABASE  (Fix #4 from previous session — postgres:// → postgresql://)
# =============================================================================
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL:
    try:
        import psycopg2
        import psycopg2.extras
        _test = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        _test.close()
        print("[DB] PostgreSQL OK ✓")
    except Exception as _e:
        print(f"[DB] PostgreSQL failed ({_e}), falling back to SQLite")
        DATABASE_URL = ''

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hub.db')

def get_db():
    if DATABASE_URL:
        try:
            return psycopg2.connect(DATABASE_URL, connect_timeout=10)
        except Exception as e:
            print(f"[DB] Reconnect error: {e}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _is_pg(conn):
    return DATABASE_URL and not isinstance(conn, sqlite3.Connection)

def _q(conn):
    return "%s" if _is_pg(conn) else "?"

def init_db():
    conn = get_db(); cur = conn.cursor(); pg = _is_pg(conn)
    s = "SERIAL" if pg else "INTEGER"; a = "" if pg else " AUTOINCREMENT"
    cur.execute(f'CREATE TABLE IF NOT EXISTS students (net_id TEXT PRIMARY KEY, name TEXT, register_no TEXT, overall_attendance REAL DEFAULT 0, est_cgpa REAL DEFAULT 0, synced_at TEXT)')
    cur.execute(f'CREATE TABLE IF NOT EXISTS projects (id {s} PRIMARY KEY{a}, title TEXT NOT NULL, description TEXT, tech_stack TEXT, github_url TEXT, demo_url TEXT, submitted_by TEXT, net_id TEXT, submitted_at TEXT)')
    cur.execute(f'CREATE TABLE IF NOT EXISTS marketplace (id {s} PRIMARY KEY{a}, title TEXT NOT NULL, description TEXT, category TEXT, price TEXT, phone_no TEXT, image_url TEXT, seller_name TEXT, net_id TEXT, created_at TEXT)')
    cur.execute(f'CREATE TABLE IF NOT EXISTS campus_wall (id {s} PRIMARY KEY{a}, message TEXT NOT NULL, author TEXT, likes INTEGER DEFAULT 0, created_at TEXT)')
    cur.execute(f'CREATE TABLE IF NOT EXISTS cab_sharing (id {s} PRIMARY KEY{a}, destination TEXT NOT NULL, travel_date TEXT, travel_time TEXT, spots TEXT, phone_no TEXT, creator_name TEXT, net_id TEXT, created_at TEXT)')
    cur.execute(f'CREATE TABLE IF NOT EXISTS club_events (id {s} PRIMARY KEY{a}, club_name TEXT NOT NULL, event_title TEXT NOT NULL, event_date TEXT, registration_link TEXT, image_url TEXT, created_by TEXT, net_id TEXT, created_at TEXT)')
    cur.execute(f'CREATE TABLE IF NOT EXISTS lost_found (id {s} PRIMARY KEY{a}, title TEXT NOT NULL, description TEXT, category TEXT, location TEXT, image_url TEXT, poster_name TEXT, net_id TEXT, created_at TEXT)')
    conn.commit(); cur.close(); conn.close()

try:
    init_db(); print("[DB] Tables ready ✓")
except Exception as _e:
    print(f"[DB] init error: {_e}")

def save_student_to_db(net_id, name, register_no, att_data, marks_data):
    try:
        ta = tc = 0
        for s in (att_data or []):
            try: ta += int(s.get('attended',0) or 0); tc += int(s.get('total',0) or 0)
            except: pass
        att = round((ta/tc)*100,1) if tc>0 else 0.0
        go = gm = 0
        for s in (marks_data or []):
            for _,mx,ob in re.findall(r'([A-Za-z0-9-]+)/([0-9.]+)\s*\|\s*([0-9.]+)', s.get('Test Performance','')):
                try: gm+=float(mx); go+=float(ob)
                except: pass
        cgpa = round((go/gm)*10,2) if gm>0 else 0.0
        conn=get_db(); cur=conn.cursor(); q=_q(conn)
        if _is_pg(conn):
            cur.execute(f'INSERT INTO students (net_id,name,register_no,overall_attendance,est_cgpa,synced_at) VALUES ({q},{q},{q},{q},{q},{q}) ON CONFLICT(net_id) DO UPDATE SET name=EXCLUDED.name,register_no=EXCLUDED.register_no,overall_attendance=EXCLUDED.overall_attendance,est_cgpa=EXCLUDED.est_cgpa,synced_at=EXCLUDED.synced_at',
                (net_id.lower(),name,register_no.upper(),att,cgpa,datetime.utcnow().isoformat()))
        else:
            cur.execute(f'INSERT INTO students (net_id,name,register_no,overall_attendance,est_cgpa,synced_at) VALUES ({q},{q},{q},{q},{q},{q}) ON CONFLICT(net_id) DO UPDATE SET name=excluded.name,register_no=excluded.register_no,overall_attendance=excluded.overall_attendance,est_cgpa=excluded.est_cgpa,synced_at=excluded.synced_at',
                (net_id.lower(),name,register_no.upper(),att,cgpa,datetime.utcnow().isoformat()))
        conn.commit(); cur.close(); conn.close()
        print(f"[DB] Saved {net_id} att={att}% cgpa={cgpa}")
    except Exception as e:
        print(f"[DB] save error: {e}")


# =============================================================================
# SCRAPER HELPERS
# =============================================================================

_BLOCK_TYPES = {"image","media","font","other"}
_BLOCK_URLS  = ["google-analytics","googletagmanager","doubleclick","facebook.net",
                "hotjar",".woff",".woff2",".ttf",".otf",
                ".png",".jpg",".jpeg",".gif",".webp",".ico",".mp4"]

def _should_block(url, rtype):
    if rtype in _BLOCK_TYPES: return True
    u = url.lower()
    return any(p in u for p in _BLOCK_URLS)

def _get_col(headers, *kw_sets):
    for kws in kw_sets:
        for i,h in enumerate(headers):
            if any(k in str(h).lower() for k in kws): return i
    return -1

def _sint(v):
    try: return max(0,int(float(str(v).strip() or 0)))
    except: return 0

def _norm(c): return re.sub(r'\s+',' ',str(c)).strip()


# =============================================================================
# MAIN SCRAPER  — with API interception + robust iframe-aware login
# =============================================================================

def scrape_academia_worker(reg_no, pwd, batch, out_queue):
    p = browser = None
    try:
        p = sync_playwright().start()
        print(f"[{reg_no}] Launching browser...")

        browser = p.chromium.launch(headless=True, args=[
            '--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage',
            '--disable-gpu','--disable-extensions','--disable-background-networking',
            '--disable-default-apps','--disable-sync','--disable-translate',
            '--hide-scrollbars','--mute-audio','--no-first-run',
            '--safebrowsing-disable-auto-update',
            '--blink-settings=imagesEnabled=false',
        ])

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width':1280,'height':720}
        )

        # Block time-wasting resources
        context.route("**/*", lambda route: route.abort()
            if _should_block(route.request.url, route.request.resource_type)
            else route.continue_())

        page = context.new_page()
        page.set_default_timeout(60000)

        if "@" not in reg_no: reg_no += "@srmist.edu.in"

        # ------------------------------------------------------------------
        # HELPER: find element in main page OR any iframe
        # ------------------------------------------------------------------
        def find_in_frames(selector, filter_text=None, filter_not_text=None):
            for target in [page] + list(page.frames):
                try:
                    loc = target.locator(selector)
                    if filter_text:    loc = loc.filter(has_text=re.compile(filter_text, re.IGNORECASE))
                    if filter_not_text:loc = loc.filter(has_not_text=re.compile(filter_not_text, re.IGNORECASE))
                    if loc.count() > 0: return loc.first
                except: continue
            return None

        # ------------------------------------------------------------------
        # HELPER: poll for element across all frames (handles late-loading iframes)
        # KEY FIX: page.wait_for_selector only checks MAIN frame; Academia
        # login form lives inside an iframe → we must poll all frames manually.
        # ------------------------------------------------------------------
        def wait_for_in_frames(selector, timeout_ms=35000, poll_ms=800):
            deadline = time.time() + timeout_ms/1000
            while time.time() < deadline:
                el = find_in_frames(selector)
                if el: return el
                page.wait_for_timeout(poll_ms)
            return None

        # ------------------------------------------------------------------
        # STEP 1 — LOGIN
        # ------------------------------------------------------------------
        print(f"[{reg_no}] Loading Academia portal...")
        page.goto("https://academia.srmist.edu.in/",
                  wait_until="domcontentloaded", timeout=60000)

        # Wait for email field in ANY frame (solves the iframe timeout bug)
        print(f"[{reg_no}] Waiting for login form (any frame)...")
        email_input = wait_for_in_frames(
            'input[type="email"], input[type="text"], input[name="LOGIN_ID"]',
            timeout_ms=40000
        )
        if not email_input:
            out_queue.put({'success': False, 'error': 'Login form not found (portal may be down)'})
            return

        email_input.fill(reg_no, force=True)
        print(f"[{reg_no}] Email filled. Looking for Next/Continue...")

        next_btn = find_in_frames('button, input[type="submit"]', filter_text=r"next|continue")
        if next_btn:
            next_btn.click(force=True, timeout=5000)
        else:
            page.keyboard.press("Enter")

        # Wait for password field — again polls all frames
        print(f"[{reg_no}] Waiting for password field...")
        pwd_input = wait_for_in_frames(
            'input[type="password"], input[name="PASSWORD"]',
            timeout_ms=25000
        )
        if not pwd_input:
            out_queue.put({'success': False, 'error': 'Password field not found'})
            return

        pwd_input.fill(pwd)
        print(f"[{reg_no}] Password filled. Submitting...")

        submit_btn = find_in_frames('button, input[type="submit"]',
                                    filter_text=r"sign in|login|submit|verify")
        if submit_btn:
            submit_btn.click(force=True, timeout=5000)
        else:
            page.keyboard.press("Enter")

        # FIX: Do NOT use wait_for_url here — it only works if the URL
        # actually navigates away and back. Instead wait for the login
        # inputs to disappear (= page has moved on) with a generous timeout.
        print(f"[{reg_no}] Waiting for post-login navigation...")
        deadline = time.time() + 35
        logged_in = False
        while time.time() < deadline:
            page.wait_for_timeout(1200)
            # Check if login form is gone (good sign) or we see a terminate button
            terminate = find_in_frames('button, a', filter_text=r"terminate")
            if terminate:
                terminate.click(force=True)
                page.wait_for_timeout(2000)
                logged_in = True
                break
            still_login = find_in_frames('input[type="password"], input[name="PASSWORD"]')
            if not still_login:
                # Password field gone → we navigated away from login
                logged_in = True
                break

        if not logged_in:
            # Last chance: check if any post-login page elements exist
            post_login = find_in_frames('a[href*="#Page"], .portal-menu, .dashboard, #main-content')
            if post_login:
                logged_in = True

        if not logged_in:
            out_queue.put({'success': False, 'error': 'Login failed or wrong credentials'})
            return

        print(f"[{reg_no}] ✓ Login successful!")

        # ------------------------------------------------------------------
        # STEP 2 — TABLE EXTRACTOR (resilient, all frames)
        # ------------------------------------------------------------------
        def get_all_tables():
            all_tables = []
            for target in [page] + list(page.frames):
                try:
                    tables = target.evaluate("""() => {
                        return Array.from(document.querySelectorAll('table')).map(t =>
                            Array.from(t.querySelectorAll('tr')).map(tr => {
                                let row = [];
                                tr.querySelectorAll('td,th').forEach(td => {
                                    let span = td.colSpan || 1;
                                    let text = (td.innerText||td.textContent||'')
                                               .trim().replace(/\\s+/g,' ');
                                    for(let i=0;i<span;i++) row.push(text);
                                });
                                return row;
                            }).filter(r => r.some(c => c.length > 0))
                        ).filter(t => t.length > 1);
                    }""")
                    if tables: all_tables.extend(tables)
                except: pass
            return all_tables

        # ------------------------------------------------------------------
        # STEP 3 — API INTERCEPTION (new: grab raw JSON before parsing DOM)
        # Academia is Zoho Creator — all data is loaded via hidden XHR calls.
        # We capture those JSON responses; if they contain useful data we use
        # them directly (fast + resilient). DOM scraping is the fallback.
        # ------------------------------------------------------------------
        intercepted = {}   # url_key → parsed JSON body

        def _capture(response):
            try:
                ct = response.headers.get("content-type","")
                if "json" not in ct: return
                url = response.url
                # Only capture Academia / Zoho Creator data endpoints
                if not any(k in url for k in ("ERA","zylker","zoho","srmist","report","fetch","data")):
                    return
                body = response.json()
                if not body or not isinstance(body,(dict,list)): return
                if len(str(body)) < 50: return
                # Classify by URL fragment
                key = "attendance"  if any(k in url.lower() for k in ("attendance","absent")) else \
                      "marks"       if any(k in url.lower() for k in ("marks","assessment","internal")) else \
                      "timetable"   if any(k in url.lower() for k in ("timetable","time_table","slot")) else \
                      "profile"     if any(k in url.lower() for k in ("profile","student")) else \
                      f"misc_{len(intercepted)}"
                intercepted[key] = {"url": url, "data": body}
                print(f"[{reg_no}] [INTERCEPT] {key} ← {url[:70]} ({len(str(body))} chars)")
            except: pass

        page.on("response", _capture)

        # ------------------------------------------------------------------
        # STEP 4 — ATTENDANCE PAGE
        # ------------------------------------------------------------------
        print(f"[{reg_no}] Fetching attendance...")
        page.goto("https://academia.srmist.edu.in/#Page:My_Attendance",
                  wait_until="domcontentloaded", timeout=60000)
        # Smart wait: as soon as a table appears, we're ready
        try:
            page.wait_for_selector("table", timeout=22000)
        except:
            print(f"[{reg_no}] No <table> on attendance page (may still have intercepted data)")
        page.wait_for_timeout(1800)   # let remaining XHRs land

        raw_tables = get_all_tables()
        parsed_att   = []
        parsed_marks = []

        profile_data = {
            "name": "STUDENT", "regNo": reg_no.split('@')[0].upper(),
            "course": "B.Tech", "semester": "Current"
        }

        # --- Try intercepted JSON first ---
        att_from_api = _parse_intercepted_attendance(intercepted)
        if att_from_api:
            parsed_att = att_from_api
            print(f"[{reg_no}] ✓ Attendance from API interception ({len(parsed_att)} subjects)")

        marks_from_api = _parse_intercepted_marks(intercepted)
        if marks_from_api:
            parsed_marks = marks_from_api
            print(f"[{reg_no}] ✓ Marks from API interception ({len(parsed_marks)} subjects)")

        # --- Profile always from DOM (it's in a simple key-value layout) ---
        for table in raw_tables:
            for row in table:
                if len(row) < 2: continue
                for i in range(len(row)-1):
                    k = str(row[i]).replace(':','').strip().lower()
                    v = str(row[i+1]).replace(':','').strip()
                    if "name" in k and "father" not in k and "mother" not in k:
                        if len(v)>2 and profile_data["name"]=="STUDENT": profile_data["name"]=v
                    elif any(x in k for x in ("program","course","degree","branch")):
                        if len(v)>2: profile_data["course"]=v[:35]
                    elif "semester" in k:
                        if 0<len(v)<=2: profile_data["semester"]=v

        # --- DOM fallback for attendance if interception missed ---
        if not parsed_att:
            print(f"[{reg_no}] Fallback: parsing attendance from DOM tables...")
            for table in raw_tables:
                if not table: continue
                headers=[str(h).lower().strip() for h in table[0]]
                hstr=" ".join(headers)
                if "conducted" in hstr and ("absent" in hstr or "attended" in hstr):
                    try:
                        ic=_get_col(headers,("code","subject code","course code"))
                        it=_get_col(headers,("title","course title","subject","name"))
                        ico=_get_col(headers,("conducted","hours conducted","total hours"))
                        ia=_get_col(headers,("absent","hours absent"))
                        iatt=_get_col(headers,("attended","hours attended","present"))
                        if ico==-1: continue
                        seen=set()
                        for row in table[1:]:
                            code=_norm(row[ic]) if ic!=-1 else "?"
                            if code in seen or not code or code=="?": continue
                            cond=_sint(row[ico])
                            if iatt!=-1 and len(row)>iatt: att=_sint(row[iatt])
                            elif ia!=-1 and len(row)>ia: att=max(0,cond-_sint(row[ia]))
                            else: continue
                            if cond==0: continue
                            seen.add(code)
                            title=_norm(row[it]) if it!=-1 and len(row)>it and row[it].strip() else code
                            parsed_att.append({"courseTitle":f"{code} - {title[:25]}","attended":att,"total":cond})
                    except Exception as e:
                        print(f"DOM att parse error: {e}")

        # --- DOM fallback for marks ---
        if not parsed_marks:
            print(f"[{reg_no}] Fallback: parsing marks from DOM tables...")
            for table in raw_tables:
                if not table: continue
                headers=[str(h).lower().strip() for h in table[0]]
                hstr=" ".join(headers)
                if any(kw in hstr for kw in ("test performance","assessment","internal marks")):
                    try:
                        ic=_get_col(headers,("course code","code"),("subject code",))
                        it=_get_col(headers,("course title","title","course name"),("subject","name"))
                        ip=_get_col(headers,("test performance",),("assessment","internal marks"),("marks","internal"))
                        if ic==-1 or ip==-1: continue
                        seen=set()
                        for row in table[1:]:
                            code=_norm(row[ic]) if ic!=-1 else "?"
                            if code in seen or not code or code=="?": continue
                            seen.add(code)
                            disp=_norm(row[it]) if it!=-1 and len(row)>it and row[it].strip() else code
                            perf=_norm(row[ip]).replace('\n',' | ') if len(row)>ip else ""
                            parsed_marks.append({"courseTitle":disp,"courseCode":code,"Test Performance":perf})
                    except Exception as e:
                        print(f"DOM marks parse error: {e}")

        # ------------------------------------------------------------------
        # STEP 5 — STUDENT TIMETABLE SLOTS (try 2024_25 first, then 2023_24)
        # ------------------------------------------------------------------
        print(f"[{reg_no}] Fetching student slots...")
        student_slots = {}
        slot_tables   = []

        for slot_url in [
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25",
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2023_24",
        ]:
            page.goto(slot_url, wait_until="domcontentloaded", timeout=60000)
            try: page.wait_for_selector("table", timeout=18000)
            except: pass
            page.wait_for_timeout(1800)
            slot_tables = get_all_tables()
            if any("slot" in " ".join(str(h).lower() for h in t[0]) for t in slot_tables if t):
                print(f"[{reg_no}] Slot data found at {slot_url}")
                break
            slot_tables = []

        # Enrich profile from slot page
        for table in slot_tables:
            for row in table:
                if len(row)<2: continue
                for i in range(len(row)-1):
                    k=str(row[i]).replace(':','').strip().lower(); v=str(row[i+1]).replace(':','').strip()
                    if "registration" in k and "number" in k and len(v)>5: profile_data["regNo"]=v
                    elif "department" in k and len(v)>2: profile_data["department"]=v
                    elif ("combo" in k or "batch" in k) and len(v)>0: profile_data["batch"]=v
                    elif ("class room" in k or "classroom" in k) and len(v)>0: profile_data["classRoom"]=v
                    elif "program" in k and len(v)>2: profile_data["course"]=v[:35]
                    elif "semester" in k and 0<len(v)<=2: profile_data["semester"]=v
                    elif "name" in k and "father" not in k and "mother" not in k and "faculty" not in k and len(v)>2 and profile_data["name"]=="STUDENT":
                        profile_data["name"]=v

        # Advisor extraction
        for table in slot_tables:
            for row in table:
                for cell in row:
                    cs=str(cell).strip(); cl=cs.lower()
                    lines=[l.strip() for l in cs.split('\n') if l.strip()]
                    for role,prefix in [('fa','faculty advisor'),('aa','academic advisor')]:
                        if prefix in cl:
                            for k,line in enumerate(lines):
                                if prefix in line.lower():
                                    if k>0 and len(lines[k-1])>3: profile_data[f'{role}_name']=lines[k-1]
                                elif '@' in line and 'srmist' in line.lower(): profile_data[f'{role}_email']=line
                                elif re.match(r'^\+?[\d\s\-]{10,}$',line):
                                    d=re.sub(r'\D','',line)
                                    if len(d)>=10: profile_data[f'{role}_phone']=d[-10:]

        # Parse student slot → subject mapping
        for table in slot_tables:
            if not table: continue
            headers=[str(h).lower().strip() for h in table[0]]
            hstr=" ".join(headers)
            if "slot" not in hstr or "code" not in hstr: continue
            try:
                ic=_get_col(headers,("course code","code"))
                it=_get_col(headers,("course title","title","subject","name"))
                isl=_get_col(headers,("slot",))
                ir=_get_col(headers,("room","venue","classroom"))
                if ic==-1 or isl==-1: continue
                for row in table[1:]:
                    if len(row)<=isl: continue
                    for s in re.findall(r'\b([A-Z]{1,3}\d*)\b', _norm(row[isl])):
                        if s in ("AM","PM"): continue
                        subj=_norm(row[it]) if it!=-1 and len(row)>it and row[it].strip() else _norm(row[ic])
                        room=_norm(row[ir]) if ir!=-1 and len(row)>ir else ""
                        student_slots[s]={"subject":subj,"room":room}
            except Exception as e:
                print(f"Slot parse error: {e}")

        print(f"[{reg_no}] {len(student_slots)} slots: {list(student_slots.keys())[:10]}")

        # ------------------------------------------------------------------
        # STEP 6 — MASTER TIMETABLE
        # ------------------------------------------------------------------
        print(f"[{reg_no}] Fetching master timetable (batch {batch})...")
        final_tt = {"1":[],"2":[],"3":[],"4":[],"5":[]}
        master_tables = []

        for m_url in [
            f"https://academia.srmist.edu.in/#Page:Unified_Time_Table_2025_Batch_{batch}",
            f"https://academia.srmist.edu.in/#Page:Unified_Time_Table_2024_Batch_{batch}",
        ]:
            page.goto(m_url, wait_until="domcontentloaded", timeout=60000)
            try: page.wait_for_selector("table", timeout=18000)
            except: pass
            page.wait_for_timeout(1800)
            master_tables = get_all_tables()
            if master_tables:
                print(f"[{reg_no}] Master TT found at {m_url}")
                break

        def _is_time_row(row):
            return sum(1 for c in row[1:] if re.search(r'\b\d{1,2}:\d{2}\b',str(c))) >= 3

        def _parse_day(cell):
            t=str(cell).strip().lower()
            m=re.match(r'^(?:day\s*(?:order\s*)?|order\s*)?(\d)$',t)
            return m.group(1) if m and m.group(1) in "12345" else None

        def _tstr(c):
            m=re.search(r'\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}',str(c))
            if m: return m.group().strip()
            m=re.search(r'\d{1,2}:\d{2}',str(c))
            return m.group().strip() if m else ""

        for t_idx, table in enumerate(master_tables):
            if not table or len(table)<3: continue
            from_t=[]; to_t=[]; time_row=None; day_rows={}
            for row in table:
                first=_norm(row[0]) if row else ""
                if _is_time_row(row):
                    cells=[_norm(c) for c in row[1:]]
                    has_ranges=sum(1 for c in cells if re.search(r'\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}',c))>=3
                    if has_ranges and time_row is None: time_row=cells
                    elif not from_t: from_t=cells
                    elif not to_t:   to_t=cells
                    continue
                day=_parse_day(first)
                if day: day_rows[day]=[_norm(c) for c in row[1:]]

            if time_row is None:
                if from_t and to_t:
                    time_row=[]
                    for f,t in zip(from_t,to_t):
                        ft=_tstr(f); tt=_tstr(t)
                        time_row.append(f"{ft} - {tt}" if ft and tt else ft or f"P{len(time_row)+1}")
                elif from_t:
                    time_row=[_tstr(c) or f"P{i+1}" for i,c in enumerate(from_t)]

            if not time_row or not day_rows: continue
            print(f"[{reg_no}] TT table {t_idx}: {len(time_row)} periods, days={list(day_rows.keys())}")

            for day,cells in day_rows.items():
                if day not in final_tt: continue
                seen=set()
                for i,cell in enumerate(cells):
                    if i>=len(time_row): break
                    for s in re.findall(r'\b([A-Z]{1,3}\d*)\b',cell):
                        if s not in student_slots or s in ("AM","PM"): continue
                        tstr=time_row[i] or f"P{i+1}"
                        key=f"{day}|{s}|{tstr}"
                        if key in seen: continue
                        seen.add(key)
                        final_tt[day].append({"time":tstr,"subject":student_slots[s]["subject"],"room":student_slots[s]["room"]})

        # Sort each day chronologically
        def _tsort(e):
            m=re.search(r'\d{1,2}:\d{2}',e.get('time',''))
            if not m: return 9999
            h,mi=m.group().split(':'); return int(h)*60+int(mi)
        for d in final_tt: final_tt[d].sort(key=_tsort)

        # Debug dump if all empty
        if not parsed_att and not parsed_marks and not student_slots:
            try:
                dbg=os.path.join(os.path.dirname(os.path.abspath(__file__)),"debug_tables.txt")
                open(dbg,"w",encoding="utf-8").write(
                    f"RAW({len(raw_tables)}):\n{raw_tables}\n\nSLOT({len(slot_tables)}):\n{slot_tables}\n\nMASTER({len(master_tables)}):\n{master_tables}\n\nINTERCEPTED:\n{intercepted}")
                print(f"[{reg_no}] Empty result — debug saved to {dbg}")
            except: pass

        print(f"[{reg_no}] Done — att={len(parsed_att)}, marks={len(parsed_marks)}, slots={len(student_slots)}, tt={sum(len(v) for v in final_tt.values())} classes")
        out_queue.put({'success':True,'profile':profile_data,'data':parsed_att,'marks':parsed_marks,'timetable':final_tt})

    except Exception as e:
        import traceback
        print(f"[SCRAPER] Crash: {traceback.format_exc()}")
        out_queue.put({'success':False,'error':f"Server error: {str(e)}"})
    finally:
        try:
            if browser: browser.close()
        except: pass
        try:
            if p: p.stop()
        except: pass


# =============================================================================
# API INTERCEPTION PARSERS
# These try to extract structured data from captured XHR/JSON responses.
# They are best-effort — if they return empty, DOM scraping takes over.
# =============================================================================

def _parse_intercepted_attendance(intercepted):
    """Try to extract attendance rows from any captured JSON response."""
    results = []
    candidates = [v for k,v in intercepted.items()
                  if any(x in k for x in ("attendance","misc"))]
    for c in candidates:
        data = c.get("data")
        # Zoho Creator returns data as {"data": [...]} or a list directly
        rows = data if isinstance(data, list) else \
               data.get("data") if isinstance(data, dict) else None
        if not rows: continue
        for row in rows:
            if not isinstance(row, dict): continue
            # Look for keys that smell like attendance fields
            code = row.get("Course_Code") or row.get("course_code") or \
                   row.get("Code") or row.get("Subject_Code") or ""
            title= row.get("Course_Title") or row.get("course_title") or \
                   row.get("Title") or row.get("Subject") or code
            conducted = 0; attended = 0
            for fk in row:
                fl = fk.lower()
                if "conduct" in fl or "total" in fl:
                    try: conducted = int(float(str(row[fk]) or 0))
                    except: pass
                elif "attend" in fl or "present" in fl:
                    try: attended = int(float(str(row[fk]) or 0))
                    except: pass
                elif "absent" in fl:
                    try: attended = max(0, conducted - int(float(str(row[fk]) or 0)))
                    except: pass
            if conducted > 0 and code:
                results.append({"courseTitle": f"{code} - {str(title)[:25]}",
                                 "attended": attended, "total": conducted})
    return results


def _parse_intercepted_marks(intercepted):
    """Try to extract marks rows from any captured JSON response."""
    results = []
    candidates = [v for k,v in intercepted.items()
                  if any(x in k for x in ("marks","misc","attendance"))]
    for c in candidates:
        data = c.get("data")
        rows = data if isinstance(data, list) else \
               data.get("data") if isinstance(data, dict) else None
        if not rows: continue
        for row in rows:
            if not isinstance(row, dict): continue
            code = row.get("Course_Code") or row.get("course_code") or \
                   row.get("Code") or ""
            title= row.get("Course_Title") or row.get("course_title") or \
                   row.get("Title") or code
            perf = ""
            for fk in row:
                fl = fk.lower()
                if any(x in fl for x in ("performance","assessment","marks","internal")):
                    perf = str(row[fk] or "")
                    break
            if code and perf:
                results.append({"courseTitle": str(title), "courseCode": code,
                                 "Test Performance": perf})
    return results


# =============================================================================
# FLASK ROUTES
# =============================================================================

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data   = request.json
    reg_no = data.get('regNo','')
    pwd    = data.get('pwd','')
    batch  = data.get('batch',1)
    if not reg_no or not pwd:
        return jsonify({'success':False,'error':'Missing credentials'}), 400
    oq = queue.Queue()
    threading.Thread(target=scrape_academia_worker,
                     args=(reg_no,pwd,batch,oq), daemon=True).start()
    try:
        result = oq.get(timeout=150)
        if result.get('success'):
            prof=result.get('profile',{}); net_id=reg_no.split('@')[0]
            save_student_to_db(net_id,prof.get('name','Student'),net_id.upper(),
                               result.get('data',[]),result.get('marks',[]))
        return jsonify(result)
    except queue.Empty:
        return jsonify({'success':False,'error':'Server timeout (150s). Portal may be slow.'})


@app.route('/api/save_student', methods=['POST'])
def save_student():
    d=request.json
    try:
        conn=get_db(); q=_q(conn)
        if _is_pg(conn):
            with conn.cursor() as cur:
                cur.execute(f'INSERT INTO students(net_id,name,overall_attendance,est_cgpa,synced_at) VALUES({q},{q},{q},{q},{q}) ON CONFLICT(net_id) DO UPDATE SET name=EXCLUDED.name,overall_attendance=EXCLUDED.overall_attendance,est_cgpa=EXCLUDED.est_cgpa,synced_at=EXCLUDED.synced_at',
                    (d.get('net_id','').lower(),d.get('name','Student'),float(d.get('attendance',0)),float(d.get('cgpa',0)),datetime.utcnow().isoformat()))
        else:
            conn.execute(f'INSERT INTO students(net_id,name,overall_attendance,est_cgpa,synced_at) VALUES({q},{q},{q},{q},{q}) ON CONFLICT(net_id) DO UPDATE SET name=excluded.name,overall_attendance=excluded.overall_attendance,est_cgpa=excluded.est_cgpa,synced_at=excluded.synced_at',
                (d.get('net_id','').lower(),d.get('name','Student'),float(d.get('attendance',0)),float(d.get('cgpa',0)),datetime.utcnow().isoformat()))
        conn.commit(); conn.close()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)})

@app.route('/api/leaderboard/attendance', methods=['GET'])
def leaderboard_attendance():
    conn=get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT name,net_id,register_no,overall_attendance FROM students ORDER BY overall_attendance DESC LIMIT 50')
            rows=[dict(r) for r in cur.fetchall()]
    else:
        rows=[dict(r) for r in conn.execute('SELECT name,net_id,register_no,overall_attendance FROM students ORDER BY overall_attendance DESC LIMIT 50').fetchall()]
    conn.close(); return jsonify(rows)

@app.route('/api/leaderboard/marks', methods=['GET'])
def leaderboard_marks():
    conn=get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT name,net_id,register_no,est_cgpa FROM students ORDER BY est_cgpa DESC LIMIT 50')
            rows=[dict(r) for r in cur.fetchall()]
    else:
        rows=[dict(r) for r in conn.execute('SELECT name,net_id,register_no,est_cgpa FROM students ORDER BY est_cgpa DESC LIMIT 50').fetchall()]
    conn.close(); return jsonify(rows)

@app.route('/api/projects', methods=['GET'])
def get_projects():
    conn=get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM projects ORDER BY submitted_at DESC')
            rows=[dict(r) for r in cur.fetchall()]
    else:
        rows=[dict(r) for r in conn.execute('SELECT * FROM projects ORDER BY submitted_at DESC').fetchall()]
    conn.close(); return jsonify(rows)

@app.route('/api/projects/submit', methods=['POST'])
def submit_project():
    d=request.json
    if not d or not d.get('title') or not d.get('submitted_by'):
        return jsonify({'success':False,'error':'Missing fields'}),400
    conn=get_db(); cur=conn.cursor(); q=_q(conn); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f'INSERT INTO projects(title,description,tech_stack,github_url,demo_url,submitted_by,net_id,submitted_at) VALUES({q},{q},{q},{q},{q},{q},{q},{q})',
            (d.get('title'),d.get('description',''),d.get('tech_stack',''),d.get('github_url',''),d.get('demo_url',''),d.get('submitted_by'),d.get('net_id',''),now))
        conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/api/marketplace', methods=['GET'])
def get_marketplace():
    conn=get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM marketplace ORDER BY id DESC LIMIT 100')
            rows=[dict(r) for r in cur.fetchall()]
    else:
        cur=conn.cursor(); cur.execute('SELECT * FROM marketplace ORDER BY id DESC LIMIT 100')
        rows=[dict(r) for r in cur.fetchall()]; cur.close()
    conn.close(); return jsonify(rows)

@app.route('/api/marketplace/submit', methods=['POST'])
def submit_marketplace():
    d=request.json
    if not d or not d.get('title') or not d.get('seller_name'):
        return jsonify({'success':False,'error':'Missing fields'}),400
    conn=get_db(); cur=conn.cursor(); q=_q(conn); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f'INSERT INTO marketplace(title,description,category,price,phone_no,image_url,seller_name,net_id,created_at) VALUES({q},{q},{q},{q},{q},{q},{q},{q},{q})',
            (d.get('title'),d.get('description',''),d.get('category',''),d.get('price',''),d.get('phone_no',''),d.get('image_url',''),d.get('seller_name'),d.get('net_id',''),now))
        conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/api/marketplace/delete/<int:item_id>', methods=['DELETE'])
def delete_marketplace(item_id):
    d=request.json or {}; net_id=d.get('net_id','').lower().strip()
    if not net_id: return jsonify({'success':False,'error':'Auth required'}),401
    conn=get_db(); cur=conn.cursor(); q=_q(conn)
    try:
        cur.execute(f'SELECT net_id FROM marketplace WHERE id={q}',(item_id,))
        row=cur.fetchone()
        if not row: return jsonify({'success':False,'error':'Not found'}),404
        if dict(row).get('net_id','').lower().strip()!=net_id:
            return jsonify({'success':False,'error':'Not your listing'}),403
        cur.execute(f'DELETE FROM marketplace WHERE id={q}',(item_id,)); conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/api/wall', methods=['GET'])
def get_wall():
    conn=get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM campus_wall ORDER BY id DESC LIMIT 100')
            rows=[dict(r) for r in cur.fetchall()]
    else:
        cur=conn.cursor(); cur.execute('SELECT * FROM campus_wall ORDER BY id DESC LIMIT 100')
        rows=[dict(r) for r in cur.fetchall()]; cur.close()
    conn.close(); return jsonify(rows)

@app.route('/api/wall/submit', methods=['POST'])
def submit_wall():
    d=request.json
    if not d or not d.get('message'): return jsonify({'success':False,'error':'Message required'}),400
    conn=get_db(); cur=conn.cursor(); q=_q(conn); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f'INSERT INTO campus_wall(message,author,created_at) VALUES({q},{q},{q})',
            (d.get('message'),d.get('author','Anonymous'),now))
        conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/api/wall/like/<int:post_id>', methods=['POST'])
def like_wall(post_id):
    conn=get_db(); cur=conn.cursor(); q=_q(conn)
    try:
        cur.execute(f'UPDATE campus_wall SET likes=likes+1 WHERE id={q}',(post_id,)); conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/api/cabs', methods=['GET'])
def get_cabs():
    conn=get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM cab_sharing ORDER BY travel_date ASC,travel_time ASC LIMIT 100')
            rows=[dict(r) for r in cur.fetchall()]
    else:
        cur=conn.cursor(); cur.execute('SELECT * FROM cab_sharing ORDER BY travel_date ASC,travel_time ASC LIMIT 100')
        rows=[dict(r) for r in cur.fetchall()]; cur.close()
    conn.close(); return jsonify(rows)

@app.route('/api/cabs/submit', methods=['POST'])
def submit_cab():
    d=request.json
    if not d or not all(d.get(k) for k in ('destination','travel_date','travel_time','phone_no')):
        return jsonify({'success':False,'error':'Missing fields'}),400
    conn=get_db(); cur=conn.cursor(); q=_q(conn); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f'INSERT INTO cab_sharing(destination,travel_date,travel_time,spots,phone_no,creator_name,net_id,created_at) VALUES({q},{q},{q},{q},{q},{q},{q},{q})',
            (d.get('destination'),d.get('travel_date'),d.get('travel_time'),d.get('spots',''),d.get('phone_no'),d.get('creator_name'),d.get('net_id',''),now))
        conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/api/cabs/delete/<int:cab_id>', methods=['DELETE'])
def delete_cab(cab_id):
    d=request.json or {}; net_id=d.get('net_id','').lower().strip()
    if not net_id: return jsonify({'success':False,'error':'Auth required'}),401
    conn=get_db(); cur=conn.cursor(); q=_q(conn)
    try:
        cur.execute(f'SELECT net_id FROM cab_sharing WHERE id={q}',(cab_id,))
        row=cur.fetchone()
        if not row: return jsonify({'success':False,'error':'Not found'}),404
        if dict(row).get('net_id','').lower().strip()!=net_id:
            return jsonify({'success':False,'error':'Not your ride'}),403
        cur.execute(f'DELETE FROM cab_sharing WHERE id={q}',(cab_id,)); conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/api/events', methods=['GET'])
def get_events():
    conn=get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM club_events ORDER BY id DESC LIMIT 100')
            rows=[dict(r) for r in cur.fetchall()]
    else:
        cur=conn.cursor(); cur.execute('SELECT * FROM club_events ORDER BY id DESC LIMIT 100')
        rows=[dict(r) for r in cur.fetchall()]; cur.close()
    conn.close(); return jsonify(rows)

@app.route('/api/events/submit', methods=['POST'])
def submit_event():
    d=request.json
    if not d or not d.get('club_name') or not d.get('event_title') or not d.get('event_date'):
        return jsonify({'success':False,'error':'Missing fields'}),400
    conn=get_db(); cur=conn.cursor(); q=_q(conn); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f'INSERT INTO club_events(club_name,event_title,event_date,registration_link,image_url,created_by,net_id,created_at) VALUES({q},{q},{q},{q},{q},{q},{q},{q})',
            (d.get('club_name'),d.get('event_title'),d.get('event_date'),d.get('registration_link',''),d.get('image_url',''),d.get('created_by'),d.get('net_id',''),now))
        conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/api/lostfound', methods=['GET'])
def get_lostfound():
    conn=get_db()
    if _is_pg(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM lost_found ORDER BY id DESC LIMIT 100')
            rows=[dict(r) for r in cur.fetchall()]
    else:
        cur=conn.cursor(); cur.execute('SELECT * FROM lost_found ORDER BY id DESC LIMIT 100')
        rows=[dict(r) for r in cur.fetchall()]; cur.close()
    conn.close(); return jsonify(rows)

@app.route('/api/lostfound/submit', methods=['POST'])
def submit_lostfound():
    d=request.json
    if not d or not d.get('title') or not d.get('category'):
        return jsonify({'success':False,'error':'Missing fields'}),400
    conn=get_db(); cur=conn.cursor(); q=_q(conn); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(f'INSERT INTO lost_found(title,description,category,location,image_url,poster_name,net_id,created_at) VALUES({q},{q},{q},{q},{q},{q},{q},{q})',
            (d.get('title'),d.get('description',''),d.get('category',''),d.get('location',''),d.get('image_url',''),d.get('poster_name','Student'),d.get('net_id',''),now))
        conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/api/lostfound/delete/<int:item_id>', methods=['DELETE'])
def delete_lostfound(item_id):
    d=request.json or {}; net_id=d.get('net_id','').lower().strip()
    if not net_id: return jsonify({'success':False,'error':'Auth required'}),401
    conn=get_db(); cur=conn.cursor(); q=_q(conn)
    try:
        cur.execute(f'SELECT net_id FROM lost_found WHERE id={q}',(item_id,))
        row=cur.fetchone()
        if not row: return jsonify({'success':False,'error':'Not found'}),404
        if dict(row).get('net_id','').lower().strip()!=net_id:
            return jsonify({'success':False,'error':'Not your post'}),403
        cur.execute(f'DELETE FROM lost_found WHERE id={q}',(item_id,)); conn.commit()
    except Exception as e: return jsonify({'success':False,'error':str(e)}),500
    finally: cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/ping')
def ping(): return 'pong', 200

@app.route('/')
def serve_index(): return send_from_directory('.','index.html')

@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.',path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))
PYEOF
echo "Done writing"
