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
                '--window-size=1920,1080',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-extensions',
                '--blink-settings=imagesEnabled=false',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--mute-audio',
                '--no-first-run',
                '--disable-logging',
                '--disable-notifications',
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        
        # Load ZOHO auth cookies
        await context.add_cookies(cookies)
        
        # --- Attendance URL (dynamic year detection) ---
        att_url = "https://academia.srmist.edu.in/#Page:My_Attendance"
        att_url_pool = [
            "https://academia.srmist.edu.in/#Page:My_Attendance_2025_26",
            "https://academia.srmist.edu.in/#Page:My_Attendance_2024_25",
            "https://academia.srmist.edu.in/#Page:My_Attendance_2023_24",
            "https://academia.srmist.edu.in/#Page:My_Attendance",
        ]
        for candidate in att_url_pool:
            page_key = candidate.split('#Page:')[1]
            if any(page_key in link for link in unique_links):
                att_url = candidate
                break
        
        # Marks are on the SAME attendance page in SRM (no separate My_Marks page)
        # So we only need att_url for both attendance + marks data
        
        # --- Timetable URL (dynamic year detection) ---
        tt_url = None
        tt_url_pool = [
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2025_26",
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2024_25",
            "https://academia.srmist.edu.in/#Page:My_Time_Table_2023_24",
            "https://academia.srmist.edu.in/#Page:My_Time_Table"
        ]
        for candidate in tt_url_pool:
            page_key = candidate.split('#Page:')[1]
            if any(page_key in link for link in unique_links):
                tt_url = candidate
                break
        if not tt_url:
            tt_url = tt_url_pool[0]

        # Only 2 tabs needed: Attendance+Marks (same page) and Slot Timetable
        page_att = await context.new_page()
        page_slots = await context.new_page()

        # Concurrent Navigation (2 tabs in parallel)
        print(f"[{reg_no}] Opening 2 tabs simultaneously: att={att_url}, slots={tt_url}")
        await asyncio.gather(
            page_att.goto(att_url, wait_until="domcontentloaded", timeout=30000),
            page_slots.goto(tt_url, wait_until="domcontentloaded", timeout=30000),
            return_exceptions=True
        )

        async def get_all_tables(page):
            try:
                await page.wait_for_selector("iframe", state="attached", timeout=3000)
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

        print(f"[{reg_no}] Fetching data tables concurrently (2 tabs)...")
        results = await asyncio.gather(
            wait_for_data_tables(page_att, ["attn", "attendance", "conducted", "absent", "code", "test performance", "assessment"]),
            wait_for_data_tables(page_slots, ["slot", "course", "code", "credit", "room"]),
            return_exceptions=True
        )

        raw_tables = results[0] if not isinstance(results[0], Exception) else []
        slot_tables = results[1] if not isinstance(results[1], Exception) else []
        
        if not raw_tables: raw_tables = []
        if not slot_tables: slot_tables = []

        print(f"[{reg_no}] Data fetched. Parsed {len(raw_tables)} att+marks tables, {len(slot_tables)} slot tables.")

        await browser.close()
        return raw_tables, slot_tables
