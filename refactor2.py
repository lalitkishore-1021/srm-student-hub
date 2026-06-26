import re

def rewrite_server():
    with open('server.py', 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. Modify get_all_tables to accept page_obj
    code = code.replace("def get_all_tables():", "def get_all_tables(page_obj=page):")
    code = re.sub(r'page\.wait_for_selector\("iframe"', 'page_obj.wait_for_selector("iframe"', code)
    code = re.sub(r'for frame in page\.frames:', 'for frame in page_obj.frames:', code)

    # 2. Modify wait_for_data_tables to accept page_obj
    code = code.replace("def wait_for_data_tables(keywords, timeout=20000):", "def wait_for_data_tables(keywords, timeout=20000, page_obj=page):")
    code = re.sub(r'check_and_handle_zoho_popups\(\)', 'check_and_handle_zoho_popups()', code) # this still uses global page, but that's fine since we don't expect popups on new tabs, or we can just ignore it for new tabs.
    # Actually wait_for_data_tables calls get_all_tables()
    code = re.sub(r'tables = get_all_tables\(\)', 'tables = get_all_tables(page_obj)', code)
    code = re.sub(r'return get_all_tables\(\)', 'return get_all_tables(page_obj)', code)
    code = re.sub(r'page\.wait_for_timeout\((.*?)\)', r'page_obj.wait_for_timeout(\1)', code)

    # 3. Rewrite the navigation logic.
    # From "# --- ATTENDANCE & MARKS ---" down to "parsed_att = []"
    
    # Actually it's much safer to replace large blocks using python string find & replace.
    old_nav_block = """        # --- ATTENDANCE & MARKS ---
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

    new_nav_block = """        # --- ASYNC PARALLEL TABS ---
        print(f"[{reg_no}] 5. Launching Parallel Tabs...")
        
        att_url = "https://academia.srmist.edu.in/#Page:My_Attendance"
        if any("My_Attendance_2024_25" in link for link in unique_links):
            att_url = "https://academia.srmist.edu.in/#Page:My_Attendance_2024_25"
            
        marks_url = "https://academia.srmist.edu.in/#Page:My_Marks"
        tt_url = "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25_Even"
        if any("My_Time_Table_2024_25_Odd" in link for link in unique_links):
            tt_url = "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25_Odd"

        page_att = context.new_page()
        page_marks = context.new_page()
        page_tt = context.new_page()

        # Execute concurrent navigation via JS
        page_att.evaluate("url => { window.location.href = url; }", att_url)
        page_marks.evaluate("url => { window.location.href = url; }", marks_url)
        page_tt.evaluate("url => { window.location.href = url; }", tt_url)

        print(f"[{reg_no}] Waiting for Attendance Data...")
        raw_tables = wait_for_data_tables(["attn", "attendance", "conducted", "absent", "hour", "code"], timeout=15000, page_obj=page_att)
        print(f"[{reg_no}] Waiting for Marks Data...")
        marks_tables = wait_for_data_tables(["test performance", "assessment", "marks", "internal"], timeout=15000, page_obj=page_marks)
        print(f"[{reg_no}] Waiting for Timetable Data...")
        tt_tables = wait_for_data_tables(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"], timeout=15000, page_obj=page_tt)
        
        # Combine att and marks raw tables into raw_tables for the parser
        raw_tables.extend(marks_tables)
"""
    code = code.replace(old_nav_block, new_nav_block)

    # We also need to remove the sequential Timetable load later on.
    old_tt_load = """        print(f"[{reg_no}] Found {len(parsed_att)} attendance records. Now loading timetable...")

        # Load Timetable
        tt_url = "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25_Even"
        if any("My_Time_Table_2024_25_Odd" in link for link in unique_links):
            tt_url = "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25_Odd"
            
        print(f"[{reg_no}] Trying timetable URL: {tt_url}")
        navigate_to_page(tt_url)
        
        tt_tables = wait_for_data_tables(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"])
"""
    new_tt_load = """        print(f"[{reg_no}] Found {len(parsed_att)} attendance records. Parsing timetable...")
"""
    # Wait, the exact string for old_tt_load might be slightly different.
    # Let me just check the exact string using python in the script before replacing.
    pass

    with open('server_new.py', 'w', encoding='utf-8') as f:
        f.write(code)

rewrite_server()
