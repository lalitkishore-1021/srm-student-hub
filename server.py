import time
import threading
import queue
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.sync_api import sync_playwright

# Initialize Flask
app = Flask(__name__, static_folder='.')
CORS(app)

# ---------------------------------------------------------
# 1. THE GRADEX SNIPER ROBOT
# ---------------------------------------------------------
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
        
        # Pretend to be a Pixel 7 phone to match your screenshot layout
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            viewport={'width': 390, 'height': 844}
        )
        page = context.new_page()

        intercepted_data = {'attendance': None, 'marks': None, 'timetable': None, 'raw': []}

        # Sniff JSON responses from GradeX
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
        
        # 🚨 THE IMAGE FIX: Block external GradeX images but ALLOW your local images
        def handle_route(route):
            rt = route.request.resource_type
            url = route.request.url
            if rt in ["media", "font"]:
                route.abort()
            elif rt == "image" and "gradex" in url:
                route.abort() # Block GradeX's heavy images
            else:
                route.continue_() # Allow your STEP class images

        page.route("**/*", handle_route)
        
        print(f"[{reg_no}] Navigating to GradeX...")
        page.goto("https://gradex.bond/", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        if "@" not in reg_no: reg_no += "@srmist.edu.in"
            
        # Login Logic
        page.locator('input').first.fill(reg_no)
        page.locator('input[type="password"]').first.fill(pwd)
        page.keyboard.press("Enter")
        
        print(f"[{reg_no}] Logged in. Clearing popups...")
        page.wait_for_timeout(6000) 
        page.keyboard.press("Escape") # Close any WhatsApp popups

        # 🚨 Force-Click Nav Tabs (Bypasses invisible popups)
        print(f"[{reg_no}] Intercepting API data...")
        try:
            page.locator('text="Attendance"').first.evaluate("node => node.click()")
            page.wait_for_timeout(2000)
            page.locator('text="Marks"').first.evaluate("node => node.click()")
            page.wait_for_timeout(2000)
        except: pass
        
        att_data = intercepted_data['attendance']
        
        # Fallback if specific route wasn't found
        if not att_data:
            for item in intercepted_data['raw']:
                if isinstance(item, dict) and ('attendance' in str(item).lower()):
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
                'marks': intercepted_data.get('marks'),
                'timetable': intercepted_data.get('timetable')
            })
        else:
            out_queue.put({'success': False, 'error': 'Failed to sniff data. Check credentials.'})

    except Exception as e:
        out_queue.put({'success': False, 'error': str(e)})
    finally:
        if browser: browser.close()
        if p: p.stop()

# ---------------------------------------------------------
# 2. FLASK ROUTES
# ---------------------------------------------------------

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    out_queue = queue.Queue()
    t = threading.Thread(target=scrape_gradex_worker, args=(data.get('regNo'), data.get('pwd'), out_queue))
    t.start()
    try:
        result = out_queue.get(timeout=60)
        return jsonify(result)
    except queue.Empty:
        return jsonify({'success': False, 'error': 'Server Timeout.'})

# 🚨 THE FRONTEND FIX: Serve your website and images
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # This serves everything (images, manifest, css) automatically
    return send_from_directory('.', path)

if __name__ == '__main__':
    # Get port from environment for Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
