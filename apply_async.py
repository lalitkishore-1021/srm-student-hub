import re

def apply():
    with open('server.py', 'r', encoding='utf-8') as f:
        code = f.read()
        
    if 'import srm_scraper_async' not in code:
        code = "import srm_scraper_async\nimport asyncio\n" + code

    # Remove old Attendance & Marks fetching
    old_att = """        # --- ATTENDANCE & MARKS ---
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
            navigate_to_page(att_url)
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
            navigate_to_page(att_urls[0])
            page.wait_for_timeout(2000)
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
                clean_text = ' | '.join([line.strip() for line in page_text.split('\\n') if line.strip()][:25])
                print(f"[{reg_no}] DIAGNOSTIC ATTENDANCE PAGE TEXT: {clean_text}")
                for i, f in enumerate(page.frames):
                    try:
                        f_text = f.evaluate("document.body.innerText")
                        f_clean = ' | '.join([line.strip() for line in f_text.split('\\n') if line.strip()][:10])
                        if f_clean:
                            print(f"[{reg_no}] DIAGNOSTIC ATTENDANCE FRAME {i} TEXT: {f_clean}")
                    except: pass
            except Exception as e:
                print(f"[{reg_no}] Failed to log attendance diagnostics: {e}")"""
    
    new_att = """        # --- ASYNC PARALLEL FETCH ---
        print(f"[{reg_no}] 5. Switching to Async Playwright for Parallel Fetch...")
        cookies = context.cookies()
        browser.close()
        p.stop()
        
        raw_tables, slot_tables = asyncio.run(srm_scraper_async.fetch_and_parse_concurrently(reg_no, cookies, unique_links))
        """

    if old_att in code:
        code = code.replace(old_att, new_att)
    else:
        print("old_att not found!")

    # Remove old Timetable fetching
    old_tt = """        # --- TIMETABLE STEP 1 (STUDENT SLOTS) ---
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
            navigate_to_page(url)
            slot_tables = wait_for_data_tables(["slot", "course", "code"], timeout=5000)
            if any(k in str(c).lower() for k in ["slot", "course", "code"] for t in slot_tables for row in t for c in row):
                print(f"[{reg_no}] Successfully loaded timetable from {url}")
                break
        else:
            print(f"[{reg_no}] Warning: No slot tables found with primary URLs. Attempting page reload on primary...")
            navigate_to_page(timetable_urls[0])
            page.wait_for_timeout(2000)
            slot_tables = wait_for_data_tables(["slot", "course", "code"], timeout=8000)
            if not slot_tables:
                try:
                    print(f"[{reg_no}] DIAGNOSTIC: Timetable page has NO tables. URL: {page.url}")
                    page_text = page.evaluate("document.body.innerText")
                    clean_text = ' | '.join([line.strip() for line in page_text.split('\\n') if line.strip()][:25])
                    print(f"[{reg_no}] DIAGNOSTIC TIMETABLE PAGE TEXT: {clean_text}")
                    for i, f in enumerate(page.frames):
                        try:
                            f_text = f.evaluate("document.body.innerText")
                            f_clean = ' | '.join([line.strip() for line in f_text.split('\\n') if line.strip()][:10])
                            if f_clean:
                                print(f"[{reg_no}] DIAGNOSTIC TIMETABLE FRAME {i} TEXT: {f_clean}")
                        except: pass
                except: pass"""
                
    new_tt = """        # --- TIMETABLE STEP 1 (STUDENT SLOTS) ---
        print(f"[{reg_no}] 6. Scoping Registered Slots...")
        student_slots = {}"""

    if old_tt in code:
        code = code.replace(old_tt, new_tt)
    else:
        print("old_tt not found!")

    with open('server.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Patched server.py successfully.")

apply()
