import urllib.request
import json
import ssl

def ping_engines():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    sitemap_url = "https://srm-student-hub-1.onrender.com/sitemap.xml"
    site_url = "https://srm-student-hub-1.onrender.com/"

    print("[*] Pinging Search Engines for SRM Student Hub...")

    # 1. Bing Ping
    try:
        bing_url = f"https://www.bing.com/ping?sitemap={sitemap_url}"
        req = urllib.request.Request(bing_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as res:
            print(f"[OK] Bing Sitemap Ping status: {res.status}")
    except Exception as e:
        print(f"[NOTE] Bing ping note: {e}")

    # 2. Google Ping
    try:
        google_url = f"https://www.google.com/ping?sitemap={sitemap_url}"
        req = urllib.request.Request(google_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as res:
            print(f"[OK] Google Sitemap Ping status: {res.status}")
    except Exception as e:
        print(f"[NOTE] Google ping note: {e}")

    # 3. IndexNow API Submission (notifies Bing, Yandex, and index partner networks immediately)
    try:
        indexnow_payload = {
            "host": "srm-student-hub-1.onrender.com",
            "key": "srmhubindexnow2026",
            "keyLocation": "https://srm-student-hub-1.onrender.com/srmhubindexnow2026.txt",
            "urlList": [
                site_url,
                sitemap_url
            ]
        }
        data = json.dumps(indexnow_payload).encode('utf-8')
        req = urllib.request.Request(
            "https://api.indexnow.org/indexnow",
            data=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "SRM-Student-Hub-SEO/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=10, context=ctx) as res:
            print(f"[OK] IndexNow API Status: {res.status} (Notified Bing & IndexNow Search Engine Network)")
    except Exception as e:
        print(f"[NOTE] IndexNow notification note: {e}")

if __name__ == "__main__":
    ping_engines()
