import time
import threading
import queue
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__, static_folder='.')
CORS(app)

def scrape_vercel_worker(reg_no, pwd, out_queue):
    p = None
    browser = None
    try:
        p = sync_playwright().start()
        print(f"[{reg_no}] Launching Smart Sniffer...")
        
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--single-process']
        )
        page = browser.new_page()

        intercepted_data = {'attendance': None, 'marks': None, 'timetable': None, 'raw': []}

        def handle_response(response):
            try:
                if response.request.resource_type in ["fetch", "xhr"] and response.status == 200:
                    json_data = response.json()
                    url_str = response.url.lower()
                    
                    # Store everything we find just in case!
                    intercepted_data['raw'].append(json_data)
                    
                    if "attendance" in url_str: intercepted_data['attendance'] = json_data
                    elif "mark" in url_str: intercepted_data['marks'] = json_data
                    elif "time" in url_str or "schedule" in url_str: intercepted_data['timetable'] = json_data
                    elif "login" in url_str or "auth" in url_str: 
                        # Sometimes the login API returns ALL data at once!
                        intercepted_data['login_api'] = json_data
            except: pass

        page.on("response", handle_response)
        
        # Block heavy images/CSS to save RAM
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
        
        page.goto("https://console-x-academia.vercel.app/")
        page.wait_for_timeout(3000)
        
        if "@" not in reg_no: reg_no += "@srmist.edu.in"
            
        print(f"[{reg_no}] Injecting credentials smartly...")
        
        # Super robust login logic (finds text/email inputs instead of just any input)
        page.locator('input[type="text"], input[type="email"], input[placeholder*="ID" i], input[placeholder*="mail" i]').first.fill(reg_no)
        page.locator('input[type="password"]').first.fill(pwd)
        
        # Hit Enter instead of trying to find the button
        page.keyboard.press("Enter")
        
        print(f"[{reg_no}] Hit Enter. Waiting for API data...")
        # Wait up to 10 seconds for the network to calm down
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(3000) # Buffer
        
        # Try to extract the data from whatever we sniffed
        att_data = intercepted_data['attendance']
        marks_data = intercepted_data['marks']
        time_data = intercepted_data['timetable']
        
        # If the API returned everything inside the login response
        if not att_data and 'login_api' in intercepted_data:
            api_res = intercepted_data['login_api']
            if isinstance(api_res, dict):
                att_data = api_res.get('attendance', api_res.get('data', None))
                marks_data = api_res.get('marks')
                time_data = api_res.get('timetable')

        # Fallback: search all raw responses if still missing
        if not att_data and len(intercepted_data['raw']) > 0:
            for item in intercepted_data['raw']:
                if isinstance(item, dict) and ('attendance' in str(item).lower() or 'present' in str(item).lower()):
                    att_data = item
                    break

        if att_data:
            # Format correction
            if isinstance(att_data, dict):
                if 'attendance' in att_data: att_data = att_data['attendance']
                elif 'data' in att_data: att_data = att_data['data']

            out_queue.put({
                'success': True, 
                'data': att_data,
                'marks': marks_data,
                'timetable': time_data
            })
        else:
            out_queue.put({'success': False, 'error': 'Incorrect Password or Vercel App is down.'})

    except Exception as e:
        out_queue.put({'success': False, 'error': str(e)})
    finally:
        if browser: browser.close()
        if p: p.stop()

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    out_queue = queue.Queue()
    t = threading.Thread(target=scrape_vercel_worker, args=(data.get('regNo'), data.get('pwd'), out_queue))
    t.start()
    try:
        result = out_queue.get(timeout=60)
        if result.get('success'): return jsonify(result)
        return jsonify({'success': False, 'error': result.get('error')})
    except queue.Empty:
        return jsonify({'success': False, 'error': 'Timeout waiting for API.'})

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename): return send_from_directory('.', filename)

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000)
