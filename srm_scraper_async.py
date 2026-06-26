import asyncio
from playwright.async_api import async_playwright
import re

async def fetch_and_parse_concurrently(reg_no, cookies, unique_links):
    print(f"[{reg_no}] 5. Launching Async Playwright for Parallel Scraping...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1920,1080'
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Load ZOHO auth cookies
        await context.add_cookies(cookies)
        
        att_url = "https://academia.srmist.edu.in/#Page:My_Attendance"
        if any("My_Attendance_2024_25" in link for link in unique_links):
            att_url = "https://academia.srmist.edu.in/#Page:My_Attendance_2024_25"
        elif any("My_Attendance_2025_26" in link for link in unique_links):
            att_url = "https://academia.srmist.edu.in/#Page:My_Attendance_2025_26"
            
        marks_url = "https://academia.srmist.edu.in/#Page:My_Marks"
        
        tt_url = "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25_Even"
        if any("My_Time_Table_2024_25_Odd" in link for link in unique_links):
            tt_url = "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25_Odd"

        page_att = await context.new_page()
        page_marks = await context.new_page()
        page_tt = await context.new_page()

        # Concurrent Navigation
        print(f"[{reg_no}] Opening 3 tabs simultaneously...")
        await asyncio.gather(
            page_att.goto(att_url, wait_until="domcontentloaded", timeout=30000),
            page_marks.goto(marks_url, wait_until="domcontentloaded", timeout=30000),
            page_tt.goto(tt_url, wait_until="domcontentloaded", timeout=30000),
            return_exceptions=True
        )

        async def get_all_tables(page):
            try:
                await page.wait_for_selector("iframe", state="attached", timeout=5000)
            except: pass
            all_tables = []
            for frame in page.frames:
                try:
                    tables = await frame.evaluate("""() => {
                        return Array.from(document.querySelectorAll('table')).map(t => 
                            Array.from(t.querySelectorAll('tr')).map(tr => {
                                let rowArr = [];
                                Array.from(tr.querySelectorAll('td, th')).forEach(td => {
                                    let span = td.colSpan || 1;
                                    let text = (td.innerText || td.textContent || "").trim();
                                    for(let i=0; i<span; i++) rowArr.push(text);
                                });
                                return rowArr;
                            }).filter(row => row.length > 0)
                        ).filter(table => table.length > 0);
                    }""")
                    if tables: all_tables.extend(tables)
                except: pass
            return all_tables

        async def wait_for_data_tables(page, keywords, timeout=15000):
            if isinstance(keywords, str): keywords = [keywords]
            keywords = [k.lower() for k in keywords]
            
            for _ in range(int(timeout / 500)):
                tables = await get_all_tables(page)
                if tables:
                    for t in tables:
                        for row in t:
                            for c in row:
                                c_str = str(c).lower()
                                if any(k in c_str for k in keywords):
                                    return tables
                await page.wait_for_timeout(500)
            return await get_all_tables(page)

        print(f"[{reg_no}] Fetching data tables concurrently...")
        results = await asyncio.gather(
            wait_for_data_tables(page_att, ["attn", "attendance", "conducted", "absent", "hour", "code"]),
            wait_for_data_tables(page_marks, ["test performance", "assessment", "marks", "internal"]),
            wait_for_data_tables(page_tt, ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]),
            return_exceptions=True
        )

        att_tables = results[0] if not isinstance(results[0], Exception) else []
        marks_tables = results[1] if not isinstance(results[1], Exception) else []
        tt_tables = results[2] if not isinstance(results[2], Exception) else []
        
        if not att_tables: att_tables = []
        if not marks_tables: marks_tables = []
        if not tt_tables: tt_tables = []

        print(f"[{reg_no}] Data fetched. Parsed {len(att_tables)} att tables, {len(marks_tables)} marks tables, {len(tt_tables)} tt tables.")
        
        # Combine att and marks tables for the parser (since old logic expected them together)
        raw_tables = att_tables + marks_tables

        return raw_tables, tt_tables
