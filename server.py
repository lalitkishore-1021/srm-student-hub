import time
import threading
import queue
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__)
CORS(app)

def scrape_vercel_worker(reg_no, pwd, out_queue):
    p = None
    browser = None
    try:
        p = sync_playwright().start()
        print(f"[{reg_no}] Launching Chromium to sniff Vercel App...")
        
        # Low memory mode
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--single-process'
            ]
        )
        page = browser.new_page()

        # 🚨 THE SNIFFER: Catching the hidden API data
        intercepted_data = {}

        def handle_response(response):
            try:
                # We only want to steal JSON API responses
                if response.request.resource_type in ["fetch", "xhr"] and response.status == 200:
                    json_data = response.json()
                    url = response.url.lower()
                    
                    if "attendance" in url:
                        intercepted_data['attendance'] = json_data
                        print("✅ Caught Attendance Data!")
                    elif "mark" in url:
                        intercepted_data['marks'] = json_data
                        print("✅ Caught Marks Data!")
                    elif "time" in url or "schedule" in url:
                        intercepted_data['timetable'] = json_data
                        print("✅ Caught Timetable Data!")
            except:
                pass

        # Attach our sniffer to the browser
        page.on("response", handle_response)
        
        print(f"[{reg_no}] Going to Vercel App...")
        page.goto("https://console-x-academia.vercel.app/")
        
        page.wait_for_timeout(3000) # Let their animations load
        
        # Fix email formatting if needed
        if "@" not in reg_no:
            reg_no += "@srmist.edu.in"
            
        print(f"[{reg_no}] Typing credentials...")
        
        # Fill in the login boxes
        inputs = page.locator('input')
        if inputs.count() >= 2:
            inputs.nth(0).fill(reg_no)
            inputs.nth(1).fill(pwd)
        else:
            out_queue.put({'success': False, 'error': 'Could not find login boxes on Vercel app.'})
            return
        
        # Click the login button
        page.locator('button').first.click()
        
        print(f"[{reg_no}] Logged in. Waiting for dashboard to load...")
        page.wait_for_timeout(5000)

        # ==========================================
        # 🚨 YOUR FIX: CLICKING THE LOCATIONS
        # ==========================================
        print(f"[{reg_no}] Clicking around to trigger the hidden APIs...")

        # 1. Try to click anything that says "Attendance"
        try:
            page.locator('text="Attendance"').first.click(timeout=3000)
            page.wait_for_timeout(2000)
        except:
            print("Couldn't find Attendance button, maybe it auto-loaded?")

        # 2. Try to click anything that says "Marks"
        try:
            page.locator('text="Marks"').first.click(timeout=3000)
            page.wait_for_timeout(2000)
        except:
            pass

        # 3. Try to click anything that says "Timetable" or "Schedule"
        try:
            page.locator('text="Timetable"').first.click(timeout=3000)
            page.wait_for_timeout(2000)
        except:
            pass
        # ==========================================
        
        print(f"[{reg_no}] Done clicking. Checking what we caught...")
        
        # Now we extract what we sniffed!
        if 'attendance' in intercepted_data:
            att_data = intercepted_data['attendance']
            
            # Drill down to the actual array if their API wrapped it in an object
            if isinstance(att_data, dict):
                if 'attendance' in att_data:
                    att_data = att_data['attendance']
                elif 'data' in att_data:
                    att_data = att_data['data']

            # Return it perfectly formatted for your frontend!
            out_queue.put({
                'success': True, 
                'requires_captcha': False, 
                'data': att_data,
                'marks': intercepted_data.get('marks'),
                'timetable': intercepted_data.get('timetable')
            })
        else:
            out_queue.put({'success': False, 'error': 'Login failed or app layout changed.'})

    except Exception as e:
        print(f"Error: {str(e)}")
        out_queue.put({'success': False, 'error': str(e)})
    finally:
        if browser: browser.close()
        if p: p.stop()

# ... (Keep the rest of your app.route functions below exactly the same!)

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    reg_no = data.get('regNo')
    pwd = data.get('pwd')

    out_queue = queue.Queue()
    t = threading.Thread(target=scrape_vercel_worker, args=(reg_no, pwd, out_queue))
    t.start()

    try:
        # Wait up to 60 seconds
        result = out_queue.get(timeout=60)
        if result.get('success'):
            return jsonify({'success': True, 'requires_captcha': False, 'data': result.get('data')})
        else:
            return jsonify({'success': False, 'error': result.get('error')})
    except queue.Empty:
        return jsonify({'success': False, 'error': 'Timeout waiting for Vercel app.'})

@app.route('/api/submit_captcha', methods=['POST'])
def submit_captcha():
    return jsonify({'success': False, 'error': 'Captcha is not needed.'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)