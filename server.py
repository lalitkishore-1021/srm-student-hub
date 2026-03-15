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

# ----- RENDER.COM SETUP -----
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
print("Starting backend... Verifying Chromium installation...")
subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=False)
print("Chromium Verification Complete.")

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return send_file("index.html")

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory('images', filename)

@app.route('/<path:filename>')
def serve_root_files(filename):
    return send_from_directory('.', filename)

# =========================================================
# SESSION STORE
# Each session has:
#   in_queue  – main thread sends captcha text to worker
#   result    – worker writes final result here (dict or None)
#   status    – 'waiting_captcha' | 'scraping' | 'done' | 'error'
# =========================================================
active_sessions = {}
session_lock = threading.Lock()


def playwright_worker(session_id, reg_no, pwd, in_queue):
    """
    Runs entirely in a background thread.
    Writes its outcome back into active_sessions[session_id]['result']
    so the polling endpoint can return it whenever it is ready.
    """
    p = None
    browser = None

    def set_status(status):
        with session_lock:
            if session_id in active_sessions:
                active_sessions[session_id]['status'] = status

    def set_result(result):
        with session_lock:
            if session_id in active_sessions:
                active_sessions[session_id]['result'] = result
                active_sessions[session_id]['status'] = 'done'

    try:
        p = sync_playwright().start()
        print(f"[{reg_no}] [Thread] Launching Chromium...")

        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',  # Critical for Render (no /dev/shm)
                '--disable-gpu',
                '--no-zygote',
                # NOTE: --single-process removed — it breaks JS-heavy portals like SRM
            ]
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={'width': 1280, 'height': 720},
        )
        page = context.new_page()

        print(f"[{reg_no}] [Thread] Navigating to SRM Portal...")
        page.goto(
            "https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp",
            timeout=20000,
        )

        print(f"[{reg_no}] [Thread] Waiting for login form...")
        page.wait_for_selector('input[type="text"]', timeout=15000)

        print(f"[{reg_no}] [Thread] Filling credentials...")
        page.fill('input[type="text"]', reg_no)
        page.fill('input[type="password"]', pwd)

        captcha_input = page.locator(
            'input[placeholder*="captcha" i], input[placeholder*="Captcha" i]'
        ).first

        if captcha_input.count() > 0:
            print(f"[{reg_no}] [Thread] CAPTCHA detected — taking screenshot...")
            captcha_img_el = page.locator(
                'img[src*="captcha" i], img[id*="captcha" i]'
            ).first

            if captcha_img_el.count() == 0:
                captcha_img_el = captcha_input.locator("xpath=..").locator("xpath=..")
            if captcha_img_el.count() == 0:
                captcha_img_el = captcha_input

            time.sleep(1)
            img_bytes = captcha_img_el.screenshot()
            b64_img = base64.b64encode(img_bytes).decode('utf-8')

            # Tell the API layer the CAPTCHA image is ready
            with session_lock:
                if session_id in active_sessions:
                    active_sessions[session_id]['captcha_base64'] = (
                        f"data:image/png;base64,{b64_img}"
                    )
                    active_sessions[session_id]['status'] = 'waiting_captcha'

            print(f"[{reg_no}] [Thread] Waiting up to 3 minutes for user to solve CAPTCHA...")
            try:
                user_msg = in_queue.get(timeout=180)
            except queue.Empty:
                print(f"[{reg_no}] [Thread] CAPTCHA timeout — user took too long.")
                set_result({'success': False, 'error': 'CAPTCHA timeout — please try again.'})
                return

            if user_msg.get('action') == 'kill':
                return

            captcha_text = user_msg.get('captcha_text', '')
            print(f"[{reg_no}] [Thread] Got CAPTCHA answer: '{captcha_text}'. Submitting...")
            set_status('scraping')

            captcha_input.fill(captcha_text)

            login_btn = page.locator(
                'input[type="submit"], button:has-text("Login"), a:has-text("Login")'
            ).first
            if login_btn.count() > 0:
                login_btn.click()
            else:
                captcha_input.press('Enter')

        else:
            print(f"[{reg_no}] [Thread] No CAPTCHA — submitting directly...")
            set_status('scraping')
            page.press('input[type="password"]', 'Enter')

        print(f"[{reg_no}] [Thread] Waiting for portal to respond after login...")
        # Wait for navigation to complete (JS-heavy portals need this)
        try:
            page.wait_for_load_state('networkidle', timeout=20000)
        except Exception:
            print(f"[{reg_no}] [Thread] networkidle wait timed out — continuing...")
        time.sleep(2)

        current_url = page.url
        print(f"[{reg_no}] [Thread] URL after login: {current_url}")

        # Check if we were kicked back to the login page (wrong password/CAPTCHA)
        if 'youLogin' in current_url or 'loginManager' in current_url:
            set_result({'success': False, 'error': 'Login failed — wrong CAPTCHA or password. Please try again.'})
            return

        # Check for any visible error messages on the page
        try:
            error_el = page.locator("span, td, div, p").filter(has_text="Invalid").first
            if error_el.count() > 0:
                error_text = error_el.inner_text().strip()
                print(f"[{reg_no}] [Thread] Portal error message: {error_text}")
                set_result({'success': False, 'error': f'Portal error: {error_text}'})
                return
        except Exception:
            pass

        # --- Strategy 1: Try clicking the Attendance link from the dashboard ---
        print(f"[{reg_no}] [Thread] Trying to click Attendance link...")
        clicked = False
        try:
            # Wait for ANY attendance link to appear in the navbar
            page.wait_for_selector(
                "a:has-text('Attendance'), #link_8",
                timeout=10000
            )
            att_link = page.locator("a:has-text('Attendance Details')").first
            if att_link.count() == 0:
                att_link = page.locator("a:has-text('Attendance')").first
            if att_link.count() == 0:
                att_link = page.locator("#link_8").first

            if att_link.count() > 0:
                att_link.click(timeout=8000)
                page.wait_for_load_state('networkidle', timeout=15000)
                time.sleep(1)
                clicked = True
                print(f"[{reg_no}] [Thread] Clicked attendance link. URL: {page.url}")
        except Exception as e:
            print(f"[{reg_no}] [Thread] Attendance link strategy failed: {e}")

        # --- Strategy 2: Direct URL if click failed or didn't land on attendance page ---
        if not clicked or 'viewAttendance' not in page.url:
            print(f"[{reg_no}] [Thread] Going directly to attendance URL...")
            try:
                page.goto(
                    "https://sp.srmist.edu.in/srmiststudentportal/students/report/viewAttendance.jsp",
                    timeout=25000,
                    wait_until='domcontentloaded'
                )
                page.wait_for_load_state('networkidle', timeout=15000)
                time.sleep(2)
                print(f"[{reg_no}] [Thread] Direct URL loaded. URL: {page.url}")
            except Exception as e:
                print(f"[{reg_no}] [Thread] Direct URL failed: {e}")

        # Check again if we got redirected to login (session invalid)
        if 'youLogin' in page.url or 'loginManager' in page.url:
            set_result({'success': False, 'error': 'Session expired after login. Please try again.'})
            return

        # --- Search for attendance table in main frame AND all iframes ---
        # SRM portal often loads content inside iframes (old JSP/Java portal pattern)
        print(f"[{reg_no}] [Thread] Searching for attendance table (including iframes)...")

        # Log all frames so we know what we're working with
        all_frames = page.frames
        print(f"[{reg_no}] [Thread] Frames on page ({len(all_frames)}): {[f.url for f in all_frames]}")

        data_frame = None  # The frame that contains the attendance table

        # First try main page
        for selector in ["table tr td", "table tr", "table"]:
            try:
                page.wait_for_selector(selector, timeout=5000)
                data_frame = page
                print(f"[{reg_no}] [Thread] Table found in MAIN frame with '{selector}'")
                break
            except Exception:
                pass

        # If not in main frame, check each iframe
        if data_frame is None:
            print(f"[{reg_no}] [Thread] Table not in main frame — checking iframes...")
            for frame in all_frames:
                if frame == page.main_frame:
                    continue
                try:
                    frame.wait_for_selector("table tr td", timeout=8000)
                    data_frame = frame
                    print(f"[{reg_no}] [Thread] Table found in IFRAME: {frame.url}")
                    break
                except Exception:
                    print(f"[{reg_no}] [Thread] Table not in frame: {frame.url}")

        # Last resort: wait a bit more and re-check all frames
        if data_frame is None:
            print(f"[{reg_no}] [Thread] Waiting 5s more for lazy-loaded content...")
            time.sleep(5)
            for frame in page.frames:
                try:
                    frame.wait_for_selector("table", timeout=5000)
                    data_frame = frame
                    print(f"[{reg_no}] [Thread] Table found after extra wait in: {frame.url}")
                    break
                except Exception:
                    pass

        if data_frame is None:
            # Capture page text for diagnostics
            try:
                body_text = page.inner_text("body")[:500]
            except Exception:
                body_text = "(could not read body)"
            print(f"[{reg_no}] [Thread] ALL selectors failed. Page body: {body_text}")
            set_result({
                'success': False,
                'error': f'Could not find attendance table on any frame. URL was: {page.url}. Please try again.'
            })
            return

        # --- Parse attendance rows from the found frame ---
        print(f"[{reg_no}] [Thread] Parsing attendance rows from frame...")
        rows_locator = data_frame.locator("table tr")
        rows_count = rows_locator.count()
        print(f"[{reg_no}] [Thread] Found {rows_count} table rows to parse.")
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
                            'total': int(max_hours_str),
                        })
                except Exception as parse_err:
                    print(f"[{reg_no}] Row parse skipped: {parse_err}")

        if live_scraped_data:
            print(f"[{reg_no}] [Thread] Scraping successful! {len(live_scraped_data)} subjects.")
            set_result({'success': True, 'data': live_scraped_data})
        else:
            set_result({'success': False, 'error': 'Table was found but appears to be empty.'})

    except Exception as fn_err:
        print(f"[{reg_no}] [Thread] Critical failure: {fn_err}")
        set_result({'success': False, 'error': f'Backend error: {str(fn_err)}'})
    finally:
        print(f"[{reg_no}] [Thread] Tearing down browser...")
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if p:
            try:
                p.stop()
            except Exception:
                pass


# =========================================================
# API ENDPOINTS
# =========================================================

@app.route('/api/start_session', methods=['POST'])
def start_session():
    """
    Kicks off a background Playwright worker.
    Returns quickly (within ~25s) with either:
      - requires_captcha=True  + session_id  → frontend shows CAPTCHA
      - success result directly (if no CAPTCHA needed)
      - error
    """
    data = request.json
    reg_no = data.get('regNo', '').strip()
    pwd = data.get('pwd', '').strip()

    if not reg_no or not pwd:
        return jsonify({'success': False, 'error': 'Registration number and password are required.'}), 400

    session_id = str(uuid.uuid4())
    in_queue = queue.Queue()

    with session_lock:
        active_sessions[session_id] = {
            'in_queue': in_queue,
            'status': 'starting',       # starting | waiting_captcha | scraping | done
            'result': None,
            'captcha_base64': None,
            'reg_no': reg_no,
            'timestamp': time.time(),
        }

    t = threading.Thread(
        target=playwright_worker,
        args=(session_id, reg_no, pwd, in_queue),
        daemon=True,
    )
    t.start()

    # Poll our own session store for up to 25 seconds waiting for the CAPTCHA image
    # (well within Render's 30-second limit)
    deadline = time.time() + 25
    while time.time() < deadline:
        time.sleep(0.5)
        with session_lock:
            sess = active_sessions.get(session_id, {})
            status = sess.get('status')
            result = sess.get('result')

        if status == 'waiting_captcha':
            with session_lock:
                captcha_b64 = active_sessions[session_id]['captcha_base64']
            return jsonify({
                'success': True,
                'requires_captcha': True,
                'session_id': session_id,
                'captcha_base64': captcha_b64,
            })

        if status == 'done' and result is not None:
            # No CAPTCHA needed — scraping already finished
            return jsonify(result)

    # 25s passed and still starting — timeout
    with session_lock:
        active_sessions.pop(session_id, None)
    return jsonify({'success': False, 'error': 'Portal took too long to respond. Please try again.'}), 502


@app.route('/api/submit_captcha', methods=['POST'])
def submit_captcha():
    """
    Forwards the solved CAPTCHA text to the worker thread and returns
    IMMEDIATELY with status='pending'.  The frontend must then poll
    /api/poll_result to find out when scraping is complete.

    This keeps this HTTP request well under Render's 30-second timeout.
    """
    data = request.json
    session_id = data.get('session_id', '').strip()
    captcha_text = data.get('captcha_text', '').strip()

    if not session_id or not captcha_text:
        return jsonify({'success': False, 'error': 'Missing session_id or captcha_text.'}), 400

    with session_lock:
        session_data = active_sessions.get(session_id)

    if not session_data:
        return jsonify({'success': False, 'error': 'Session expired or not found. Please start again.'}), 400

    # Send the answer to the worker; it will now continue scraping in the background
    session_data['in_queue'].put({'action': 'submit', 'captcha_text': captcha_text})

    # Update status so poll endpoint knows we're working
    with session_lock:
        if session_id in active_sessions:
            active_sessions[session_id]['status'] = 'scraping'

    # Return immediately — frontend polls for the result
    return jsonify({'success': True, 'status': 'pending', 'session_id': session_id})


@app.route('/api/poll_result', methods=['POST'])
def poll_result():
    """
    Lightweight polling endpoint.
    Frontend calls this every 3 seconds after submitting CAPTCHA.
    Returns:
      { status: 'pending' }           – still scraping
      { status: 'done', ...result }   – scraping finished (success or error)
    """
    data = request.json
    session_id = data.get('session_id', '').strip()

    with session_lock:
        session_data = active_sessions.get(session_id)

    if not session_data:
        return jsonify({'status': 'done', 'success': False, 'error': 'Session expired. Please start again.'})

    status = session_data.get('status')
    result = session_data.get('result')

    if status == 'done' and result is not None:
        # Clean up session
        with session_lock:
            active_sessions.pop(session_id, None)
        return jsonify({'status': 'done', **result})

    return jsonify({'status': 'pending'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
