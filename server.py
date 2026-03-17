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
            user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            viewport={'width': 390, 'height': 844}
        )
        page = context.new_page()

        # 🚨 THE FIX: Tell Playwright to wait up to 90 seconds instead of 30!
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
            if rt in ["media", "font"]:
                route.abort()
            elif rt == "image" and "gradex" in url:
                route.abort() 
            else:
                route.continue_()

        page.route("**/*", handle_route)
        
        print(f"[{reg_no}] Navigating to GradeX...")
        page.goto("https://gradex.bond/", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        if "@" not in reg_no: reg_no += "@srmist.edu.in"
            
        page.locator('input').first.fill(reg_no)
        page.locator('input[type="password"]').first.fill(pwd)
        page.keyboard.press("Enter")
        
        print(f"[{reg_no}] Logged in. Clearing popups...")
        # Give the dashboard plenty of time to load
        page.wait_for_timeout(8000) 
        page.keyboard.press("Escape") 

        print(f"[{reg_no}] Intercepting API data...")
        try:
            page.locator('text="Attendance"').first.evaluate("node => node.click()")
            page.wait_for_timeout(3000)
            page.locator('text="Marks"').first.evaluate("node => node.click()")
            page.wait_for_timeout(3000)
        except: pass
        
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
            out_queue.put({'success': False, 'error': 'Failed to sniff data. GradeX took too long to load.'})

    except Exception as e:
        out_queue.put({'success': False, 'error': f"Playwright Error: {str(e)}"})
    finally:
        if browser: browser.close()
        if p: p.stop()
