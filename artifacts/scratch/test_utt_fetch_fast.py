import sys
import json
from bs4 import BeautifulSoup
import re

# Add temp path so we can import the module
sys.path.append("d:\\sshbackup\\3aprfully_working\\srm-student-hub\\temp_academia_scraper")
from studentinfo_scrap import AcademiaClient

def test_utt_fetch(email, password):
    print("Testing login...")
    client = AcademiaClient(email, password)
    lookup = client.lookup_user()
    if not lookup:
        print("Lookup failed")
        return
    login = client.login()
    if not login.get("success"):
        print("Login failed")
        return
    
    print("Login success! Fetching UTT page...")
    
    # Try different UTT variations
    utt_urls = [
        f"{client.BASE_URL}/srm_university/academia-academic-services/page/Unified_Time_Table_2025_Batch_1",
        f"{client.BASE_URL}/srm_university/academia-academic-services/page/Unified_Time_Table_2025_26",
        f"{client.BASE_URL}/srm_university/academia-academic-services/page/Unified_Time_Table"
    ]
    
    for url in utt_urls:
        print(f"Fetching: {url}")
        res = client.session.get(url, headers=client._get_page_headers())
        html_content = res.text
        
        # Check if it has escaped innerHTML
        match = re.search(r"innerHTML = pageSanitizer\.sanitize\('(.+?)'\);", html_content, re.DOTALL)
        if match:
            escaped_html = match.group(1)
            html_decoded = escaped_html
            html_decoded = html_decoded.replace("\\'", "'")
            html_decoded = html_decoded.replace('\\"', '"')
            html_decoded = html_decoded.replace('\\/', '/')
            html_decoded = html_decoded.replace('\\-', '-')
            html_decoded = html_decoded.replace('\\n', '\n')
            html_decoded = html_decoded.replace('\\t', '\t')
            html_decoded = html_decoded.replace('\\r', '\r')
            html_decoded = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), html_decoded)
            
            soup = BeautifulSoup(html_decoded, 'html.parser')
            tables = soup.find_all('table')
            
            print(f"Found {len(tables)} tables in {url}")
            for t in tables:
                text = t.get_text().lower()
                if 'day' in text and '1' in text and '2' in text:
                    print("--> FOUND UTT GRID TABLE!")
                    return
        else:
            print("No sanitized HTML found, maybe not logged in properly or wrong page.")
            
if __name__ == "__main__":
    # Test credentials
    test_utt_fetch("as0711@srmist.edu.in", "Srm@2021") # Use the ones in studentinfo_scrap.py main()
