import time
import threading
import queue
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__, static_folder='.')
CORS(app)

def scrape_gradex_worker(reg_no, pwd, out_queue):
    p = None
    browser = None
    try:
        p = sync_playwright().start()
        print(f"[{reg_no}] Launching GradeX Sniper...")
        
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--single-process']
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()
        page.set_default_timeout(90000)

        intercepted_data = {'attendance': None, 'marks': None, 'timetable': None, 'raw': []}

        def handle_response(response):
            try:
                if response.request.resource_type in ["fetch", "xhr"] and response.status == 200:
                    json_data = response.json()
                    url_str = response.url.lower()
                    intercepted_data['raw'].append(json_data)
                    
                    if "attendance" in url_str: intercepted_data['attendance'] = json_data
                    elif "mark" in url_str: intercepted_data['marks'] = json_data
                    elif "schedule" in url_str or "time" in url_str: intercepted_data['timetable'] = json_data
            except: pass

        page.on("response", handle_response)
        
        def handle_route(route):
            rt = route.request.resource_type
            url = route.request.url
            if rt in ["media", "font"] or ("image" == rt and "gradex" in url):
                route.abort() 
            else:
                route.continue_()

        page.route("**/*", handle_route)
        
        print(f"[{reg_no}] 1. Loading /srm-login and waiting 15s for animation...")
        try:
            page.goto("https://gradex.bond/srm-login", wait_until="load", timeout=60000)
            page.wait_for_timeout(15000) # Wait out the animation
        except Exception:
            out_queue.put({'success': False, 'error': 'GradeX login page failed to load.'})
            return
            
        # Mash escape to clear the WhatsApp popup
        for _ in range(3):
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            
        # Safety Net: If we got redirected to the Home page, click "Login to SRM"
        try:
            btn = page.locator('text="Login to SRM"').first
            if btn.is_visible(timeout=3000):
                btn.click(force=True)
                page.wait_for_timeout(5000)
        except: pass

        if "@" not in reg_no: reg_no += "@srmist.edu.in"
            
        print(f"[{reg_no}] 2. Entering credentials (Forcing through popups)...")
        try:
            # Wait for any input box to exist in the code
            page.wait_for_selector('input', timeout=15000)
            
            # 🚨 FORCE=TRUE: Ignore the dark popup overlay and type anyway!
            page.locator('input').nth(0).fill(reg_no, force=True)
            page.locator('input[type="password"]').first.fill(pwd, force=True)
            
            try:
                page.locator('button:has-text("CONNECT")').first.click(force=True, timeout=3000)
            except:
                page.keyboard.press("Enter")
        except Exception as e:
            out_queue.put({'success': False, 'error': f'Could not inject credentials. Error: {str(e)}'})
            return
        
        print(f"[{reg_no}] 3. Waiting for dashboard to load (10s)...")
        page.wait_for_timeout(10000) 
        
        # Mash Escape again just in case the dashboard has a popup
        for _ in range(3):
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

        print(f"[{reg_no}] 4. Clicking Navigation Tabs to sniff API...")
        try:
            page.locator('text="Attendance"').first.evaluate("node => node.click()", timeout=5000)
            page.wait_for_timeout(3000)
            page.locator('text="Marks"').first.evaluate("node => node.click()", timeout=5000)
            page.wait_for_timeout(3000)
        except Exception:
            print(f"[{reg_no}] Could not click tabs automatically.")
        
        att_data = intercepted_data['attendance']
        
        if not att_data:
            for item in intercepted_data['raw']:
                if isinstance(item, dict) and ('attendance' in str(item).lower()):
                    att_data = item
                    break

        if att_data:
            if isinstance(att_data, dict):
                if 'attendance' in att_data: att_data = att_data['attendance']
                elif 'data' in att_data: att_data = att_data['data']

            out_queue.put({
                'success': True, 
                'data': att_data,
                'marks': intercepted_data.get('marks'),
                'timetable': intercepted_data.get('timetable')
            })
        else:
            out_queue.put({'success': False, 'error': 'Logged in successfully, but no data was received. GradeX API might be empty.'})

    except Exception as e:
        out_queue.put({'success': False, 'error': f"Unexpected Error: {str(e)}"})
    finally:
        if browser: browser.close()
        if p: p.stop()

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    out_queue = queue.Queue()
    t = threading.Thread(target=scrape_gradex_worker, args=(data.get('regNo'), data.get('pwd'), out_queue))
    t.start()
    try:
        result = out_queue.get(timeout=110)
        return jsonify(result)
    except queue.Empty:
        return jsonify({'success': False, 'error': 'Server Timeout. GradeX took too long to respond.'})

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
