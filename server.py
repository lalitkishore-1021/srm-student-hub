import time
import threading
import queue
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__, static_folder='.')
CORS(app)

def scrape_academia_worker(email, pwd, out_queue):
    p = None
    browser = None
    try:
        p = sync_playwright().start()
        print(f"[{email}] Launching Official Academia Sniper...")
        
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        # Removed the image blocker so Zoho doesn't think we are a bot!

        print(f"[{email}] 1. Navigating to Academia...")
        try:
            # wait_until="commit" stops it from infinitely loading if Zoho is slow
            page.goto("https://academia.srmist.edu.in/", wait_until="commit", timeout=45000)
            page.wait_for_timeout(8000) # Give Zoho time to render the login box
        except Exception as e:
            print(f"[{email}] Page load warning, pushing through: {str(e)}")
        
        print(f"[{email}] 2. Entering Email...")
        try:
            page.wait_for_selector('input[id="login_id"], input[type="email"]', timeout=15000)
            page.locator('input[id="login_id"], input[type="email"]').first.fill(email, force=True)
            
            try:
                page.locator('button:has-text("Next"), button[id="nextbtn"]').first.click(force=True, timeout=5000)
            except:
                page.keyboard.press("Enter")
        except Exception as e:
            out_queue.put({'success': False, 'error': 'Could not find the Zoho Email box.'})
            return
            
        page.wait_for_timeout(5000)

        print(f"[{email}] 3. Entering Password...")
        try:
            page.wait_for_selector('input[type="password"], input[id="password"]', timeout=15000)
            page.locator('input[type="password"], input[id="password"]').first.fill(pwd, force=True)
            
            try:
                page.locator('button:has-text("Sign in"), button[id="nextbtn"]').first.click(force=True, timeout=5000)
            except:
                page.keyboard.press("Enter")
        except Exception as e:
            out_queue.put({'success': False, 'error': 'Could not find the Zoho Password box. Check your email.'})
            return

        print(f"[{email}] 4. Checking for 'Terminate All Sessions' limit...")
        page.wait_for_timeout(6000)
        
        try:
            terminate_btn = page.locator('text="Terminate All Sessions", button:has-text("Terminate")').first
            if terminate_btn.is_visible(timeout=5000):
                print(f"[{email}] Limit exceeded found! Terminating old sessions...")
                terminate_btn.click(force=True)
                page.wait_for_timeout(6000)
        except:
            print(f"[{email}] No session limits detected, proceeding.")

        print(f"[{email}] 5. Waiting for main dashboard to load...")
        page.wait_for_timeout(10000)

        print(f"[{email}] 6. Teleporting to My_Attendance page...")
        try:
            page.goto("https://academia.srmist.edu.in/#Page:My_Attendance", wait_until="commit", timeout=45000)
            page.wait_for_timeout(10000) # Give Zoho tables 10 full seconds to render
        except Exception as e:
            print(f"[{email}] Warning during teleport: {str(e)}")

        print(f"[{email}] 7. Scanning all frames for data tables...")
        all_tables_data = []
        for frame in page.frames:
            try:
                frame_data = frame.evaluate("""() => {
                    let tables = Array.from(document.querySelectorAll('table'));
                    let extracted = [];
                    tables.forEach(table => {
                        let rows = Array.from(table.querySelectorAll('tr'));
                        let tableData = rows.map(tr => {
                            let cells = Array.from(tr.querySelectorAll('td, th'));
                            return cells.map(cell => cell.innerText.trim()).filter(text => text !== '');
                        }).filter(row => row.length > 0);
                        if(tableData.length > 1) extracted.push(tableData);
                    });
                    return extracted;
                }""")
                if frame_data:
                    all_tables_data.extend(frame_data)
            except: pass

        if all_tables_data:
            out_queue.put({
                'success': True, 
                'data': [], 
                'marks': [{'Academia Raw Data': 'Check below'}, {'Raw': all_tables_data}],
                'timetable': []
            })
        else:
            out_queue.put({'success': False, 'error': 'Logged in successfully, but could not read the data tables.'})

    except Exception as e:
        out_queue.put({'success': False, 'error': f"Academia Error: {str(e)}"})
    finally:
        if browser: browser.close()
        if p: p.stop()

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    out_queue = queue.Queue()
    t = threading.Thread(target=scrape_academia_worker, args=(data.get('regNo'), data.get('pwd'), out_queue))
    t.start()
    try:
        result = out_queue.get(timeout=110)
        return jsonify(result)
    except queue.Empty:
        return jsonify({'success': False, 'error': 'Server Timeout. Academia took too long to load.'})

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
