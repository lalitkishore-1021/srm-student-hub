"""
SRM Student Hub - Indian Railways Real Live Train Running Status Service
Connects to official National Train Enquiry System (NTES) and optional RapidAPI / IRCTC live feeds.
Exposes clean, real-time telemetry (actual position, delay, platform, last passed station, next station).
"""

import os
import re
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# In-memory cache to prevent upstream rate-limiting
# { train_no: { 'data': dict, 'timestamp': float } }
_TRAIN_LIVE_CACHE = {}
_CACHE_TTL = 45  # 45 seconds cache

BASE_URL = 'https://enquiry.indianrail.gov.in/mntes'
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Origin': 'https://enquiry.indianrail.gov.in',
    'Referer': f'{BASE_URL}/',
    'X-Requested-With': 'XMLHttpRequest'
}

CHENNAI_EMU_REFERENCE_STATIONS = [
    { 'code': 'CGL', 'name': 'Chengalpattu Jn', 'km': 0.0, 'pf': '3' },
    { 'code': 'PWU', 'name': 'Paranur', 'km': 4.0, 'pf': '2' },
    { 'code': 'SKL', 'name': 'Singaperumal Koil', 'km': 8.0, 'pf': '3' },
    { 'code': 'MMNK', 'name': 'Maraimalai Nagar', 'km': 13.0, 'pf': '2' },
    { 'code': 'CTM', 'name': 'Kattangulathur', 'km': 14.0, 'pf': '3' },
    { 'code': 'POTI', 'name': 'Potheri (SRM University)', 'km': 16.0, 'pf': '2' },
    { 'code': 'GI', 'name': 'Guduvancheri', 'km': 19.0, 'pf': '3' },
    { 'code': 'UPM', 'name': 'Urapakkam', 'km': 22.0, 'pf': '2' },
    { 'code': 'VDR', 'name': 'Vandalur', 'km': 25.0, 'pf': '2' },
    { 'code': 'PRGL', 'name': 'Perungalathur', 'km': 27.0, 'pf': '2' },
    { 'code': 'TBM', 'name': 'Tambaram', 'km': 31.0, 'pf': '1' },
    { 'code': 'TBMS', 'name': 'Tambaram Sanatorium', 'km': 32.0, 'pf': '2' },
    { 'code': 'CMP', 'name': 'Chromepet', 'km': 34.0, 'pf': '2' },
    { 'code': 'PV', 'name': 'Pallavaram', 'km': 37.0, 'pf': '1' },
    { 'code': 'TLM', 'name': 'Tirusulam (Airport)', 'km': 39.0, 'pf': '2' },
    { 'code': 'MN', 'name': 'Minambakkam', 'km': 40.0, 'pf': '2' },
    { 'code': 'PZA', 'name': 'Palavanthangal', 'km': 41.0, 'pf': '2' },
    { 'code': 'STM', 'name': 'St. Thomas Mount', 'km': 43.0, 'pf': '1' },
    { 'code': 'GDY', 'name': 'Guindy', 'km': 44.0, 'pf': '2' },
    { 'code': 'SP', 'name': 'Saidapet', 'km': 47.0, 'pf': '2' },
    { 'code': 'MBM', 'name': 'Mambalam (T. Nagar)', 'km': 48.0, 'pf': '2' },
    { 'code': 'MKK', 'name': 'Kodambakkam', 'km': 50.0, 'pf': '1' },
    { 'code': 'NBK', 'name': 'Nungambakkam', 'km': 51.0, 'pf': '2' },
    { 'code': 'MSC', 'name': 'Chennai Chetpet', 'km': 53.0, 'pf': '2' },
    { 'code': 'MS', 'name': 'Chennai Egmore', 'km': 55.0, 'pf': '11' },
    { 'code': 'MPK', 'name': 'Chennai Park', 'km': 57.0, 'pf': '1' },
    { 'code': 'MSF', 'name': 'Chennai Fort', 'km': 58.0, 'pf': '2' },
    { 'code': 'MSB', 'name': 'Chennai Beach', 'km': 60.0, 'pf': '4' }
]


def fetch_live_ntes_html(train_no, timeout=9):
    """
    Connects to NTES, retrieves a fresh CSRF token, and requests live running HTML.
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.get(f'{BASE_URL}/', timeout=timeout)

    r_csrf = session.get(f'{BASE_URL}/GetCSRFToken?t={int(datetime.now().timestamp()*1000)}', timeout=timeout)
    m = re.search(r"name='([^']+)' value='([^']+)'", r_csrf.text)
    if not m:
        raise RuntimeError("Failed to obtain NTES CSRF security token")

    csrf_key, csrf_val = m.group(1), m.group(2)
    today_str = datetime.now().strftime('%d-%b-%Y')

    params = {'opt': 'TrainRunning', 'subOpt': 'FindRunningInstance', 'refDate': today_str}
    data = {'lan': 'en', 'jDate': today_str, 'trainNo': str(train_no), csrf_key: csrf_val}

    r_post = session.post(f'{BASE_URL}/tr', params=params, data=data, timeout=timeout)
    if r_post.status_code != 200 or len(r_post.text) < 500:
        raise RuntimeError(f"Upstream NTES returned invalid response: status {r_post.status_code}")

    return r_post.text


def parse_ntes_html(html, train_no):
    """
    Parses the official NTES live HTML into a clean, typed telemetry dictionary.
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Look for instance containers: id="train<date>"
    containers = soup.find_all('div', id=re.compile(r'^train\d+'))
    if not containers:
        text_content = soup.get_text(' ', strip=True)
        if 'yet to start' in text_content.lower():
            return {
                'success': True,
                'is_live': True,
                'source': 'Indian Railways NTES Official Feed',
                'train_no': str(train_no),
                'status': 'Yet to start',
                'status_headline': f'Train {train_no} - Yet to start from source station',
                'delay_mins': 0,
                'delay_text': 'On Time',
                'speed': None,
                'last_updated': datetime.now().strftime('%d-%b-%Y %H:%M'),
                'current_station_idx': 0,
                'current_station': None,
                'last_passed_station': None,
                'next_station': None,
                'potheri': None,
                'stations': []
            }
        return {
            'success': False,
            'is_live': False,
            'train_no': str(train_no),
            'status': 'Live data unavailable',
            'message': 'No active running instance reported by railway enquiry.'
        }

    # Select the active container (prefer the one with active train icon or most recent)
    target_container = containers[0]
    for c in containers:
        if c.find('img', src=re.compile(r'train_36')):
            target_container = c
            break

    # Headline status
    status_headline = ''
    b_tags = target_container.find_all('b')
    for b in b_tags:
        bt = b.get_text(strip=True)
        if any(w in bt.lower() for w in ['arrived', 'departed', 'yet to start', 'reached destination', 'running']):
            status_headline = bt
            break

    # Last update timestamp
    last_updated = ''
    last_update_m = re.search(r'Last Updates On\s*([^<\n\r]+)', target_container.get_text(), re.I)
    if last_update_m:
        last_updated = last_update_m.group(1).strip()
    if not last_updated:
        last_updated = datetime.now().strftime('%d-%b-%Y %H:%M')

    stop_rows = target_container.find_all('div', class_='stopRow')
    stations = []
    current_station_idx = -1
    last_passed_idx = -1
    overall_delay = 0

    for idx, row in enumerate(stop_rows):
        img = row.find('img', src=re.compile(r'(green_24|train_36|red_24)'))
        img_type = 'unknown'
        if img:
            src = img.get('src', '')
            if 'green_24' in src:
                img_type = 'passed'
                last_passed_idx = idx
            elif 'train_36' in src:
                img_type = 'current'
                current_station_idx = idx
            elif 'red_24' in src:
                img_type = 'upcoming'

        # Extract name and code
        containers_in_row = row.find_all('div', class_='w3-container')
        st_container = containers_in_row[2] if len(containers_in_row) > 2 else row
        b_elements = st_container.find_all('b')

        st_name = b_elements[0].get_text(strip=True) if len(b_elements) > 0 else 'Station'
        code_raw = b_elements[1].get_text(strip=True) if len(b_elements) > 1 else ''
        st_code = re.sub(r'PF\s*\d+', '', code_raw).strip()

        km_raw = b_elements[2].get_text(strip=True) if len(b_elements) > 2 else '0'
        km = float(km_raw) if km_raw.isdigit() else 0.0

        pf_tag = st_container.find('span', class_=re.compile(r'orange'))
        pf = pf_tag.get_text(strip=True).replace('PF', '').strip() if pf_tag else ''

        # Times & Delays
        text_all = row.get_text(' ', strip=True)
        time_matches = re.findall(r'(\d{1,2}:\d{2})\s*(\d{1,2}-[A-Za-z]{3})?', text_all)
        sched_time = time_matches[0][0] if len(time_matches) > 0 else ''
        actual_time = time_matches[1][0] if len(time_matches) > 1 else sched_time

        delay_m = re.search(r'(\d+)\s*Min', text_all, re.I)
        st_delay = int(delay_m.group(1)) if delay_m else (0 if 'on time' in text_all.lower() else 0)
        if st_delay > overall_delay:
            overall_delay = st_delay

        stations.append({
            'index': idx,
            'name': st_name,
            'code': st_code,
            'km': km,
            'platform': pf,
            'sched_time': sched_time,
            'actual_time': actual_time,
            'delay_mins': st_delay,
            'icon_type': img_type,
            'is_passed': (img_type == 'passed') or (current_station_idx >= 0 and idx < current_station_idx),
            'is_current': (img_type == 'current') or (idx == current_station_idx)
        })

    # Resolve train operational status
    if current_station_idx == -1:
        if last_passed_idx == len(stations) - 1:
            current_station_idx = len(stations) - 1
            train_status = 'Reached Destination'
        elif last_passed_idx >= 0:
            current_station_idx = last_passed_idx
            train_status = 'Running'
        else:
            current_station_idx = 0
            train_status = 'Yet to start'
    else:
        if current_station_idx == len(stations) - 1:
            train_status = 'Reached Destination'
        elif current_station_idx == 0:
            train_status = 'At Origin'
        else:
            train_status = 'Running'

    # Mark current on resolved stations
    for idx, s in enumerate(stations):
        s['is_current'] = (idx == current_station_idx)
        s['is_passed'] = (idx < current_station_idx) or (idx == current_station_idx and train_status == 'Reached Destination')

    current_station = stations[current_station_idx] if 0 <= current_station_idx < len(stations) else None
    next_station = stations[current_station_idx + 1] if 0 <= current_station_idx < len(stations) - 1 else None
    last_passed = stations[last_passed_idx] if 0 <= last_passed_idx < len(stations) else None

    # Potheri reference
    poti_station = next((s for s in stations if s['code'] == 'POTI'), None)
    poti_info = None
    if poti_station:
        poti_info = {
            'code': 'POTI',
            'name': 'Potheri (SRM University)',
            'platform': poti_station['platform'] or '2',
            'sched_time': poti_station['sched_time'],
            'actual_time': poti_station['actual_time'],
            'delay_mins': poti_station['delay_mins'],
            'is_passed': poti_station['is_passed'],
            'is_current': poti_station['is_current'],
            'km': poti_station['km']
        }

    return {
        'success': True,
        'is_live': True,
        'source': 'Indian Railways NTES Official Feed',
        'train_no': str(train_no),
        'status': train_status,
        'status_headline': status_headline or f'Train {train_no} - {train_status}',
        'current_station_idx': current_station_idx,
        'current_station': current_station,
        'next_station': next_station,
        'last_passed_station': last_passed,
        'delay_mins': overall_delay,
        'delay_text': f'Delayed +{overall_delay}m' if overall_delay > 0 else 'On Time',
        'speed': None,  # GPS speedometer telemetry is null unless hardware provider reports it
        'last_updated': last_updated,
        'potheri': poti_info,
        'stations': stations
    }


def fetch_rapidapi_train_status(train_no):
    """
    Secure server-side connector for RapidAPI Indian Railway Live Train Status.
    Keeps API key completely confidential on the server.
    """
    rapidapi_key = os.environ.get('RAPIDAPI_KEY') or os.environ.get('IRCTC_API_KEY')
    if not rapidapi_key:
        return None

    try:
        url = "https://indian-railway-irctc.p.rapidapi.com/api/trains/v1/train/status"
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "indian-railway-irctc.p.rapidapi.com"
        }
        params = {"train_number": str(train_no)}
        res = requests.get(url, headers=headers, params=params, timeout=7)
        if res.status_code == 200:
            json_data = res.json()
            if json_data.get('success'):
                # Normalize RapidAPI schema to unified SRM Hub schema
                return {
                    'success': True,
                    'is_live': True,
                    'source': 'Indian Railways Live API (RapidAPI/IRCTC)',
                    'train_no': str(train_no),
                    'status': json_data.get('train', {}).get('status', 'Running'),
                    'status_headline': json_data.get('position', f'Train {train_no} Running'),
                    'delay_mins': int(re.search(r'\d+', str(json_data.get('train', {}).get('delay', '0'))).group() if re.search(r'\d+', str(json_data.get('train', {}).get('delay', '0'))) else 0),
                    'delay_text': str(json_data.get('train', {}).get('delay', 'On Time')),
                    'speed': json_data.get('train', {}).get('speed'),  # Provided if GPS exists
                    'last_updated': json_data.get('last_updated', datetime.now().strftime('%d-%b-%Y %H:%M')),
                    'current_station': json_data.get('current_station'),
                    'next_station': json_data.get('next_station'),
                    'route': json_data.get('route', [])
                }
    except Exception as e:
        print(f"[RAPIDAPI] Error querying live status for {train_no}: {e}")
    return None


def get_live_train_status(train_no):
    """
    Unified public method to fetch legitimate live train running status.
    Uses in-memory caching to protect upstream endpoints and provide rapid responses.
    """
    train_no_str = str(train_no).strip()
    now_ts = time.time()

    # 1. Check in-memory cache
    if train_no_str in _TRAIN_LIVE_CACHE:
        cached_entry = _TRAIN_LIVE_CACHE[train_no_str]
        if (now_ts - cached_entry['timestamp']) < _CACHE_TTL:
            cached_data = cached_entry['data'].copy()
            cached_data['cached'] = True
            cached_data['cache_age_secs'] = int(now_ts - cached_entry['timestamp'])
            return cached_data

    # 2. Try RapidAPI provider if configured
    rapid_data = fetch_rapidapi_train_status(train_no_str)
    if rapid_data:
        _TRAIN_LIVE_CACHE[train_no_str] = {'data': rapid_data, 'timestamp': now_ts}
        return rapid_data

    # 3. Query NTES Official Live Railway System
    try:
        ntes_html = fetch_live_ntes_html(train_no_str)
        ntes_data = parse_ntes_html(ntes_html, train_no_str)
        if ntes_data.get('success'):
            _TRAIN_LIVE_CACHE[train_no_str] = {'data': ntes_data, 'timestamp': now_ts}
            return ntes_data
    except Exception as e:
        print(f"[RAILWAY SERVICE] NTES error for {train_no_str}: {e}")

    # 4. Fallback when train live telemetry is not actively reporting in railway feed
    return {
        'success': False,
        'is_live': False,
        'source': 'Indian Railways Schedule Directory',
        'train_no': train_no_str,
        'status': 'Live data unavailable',
        'status_headline': f'Train {train_no_str} - Live running data not reported yet by railway control',
        'stale_message': 'Live data unavailable from railway control',
        'delay_mins': 0,
        'delay_text': 'Scheduled',
        'speed': None,
        'last_updated': datetime.now().strftime('%d-%b-%Y %H:%M'),
        'current_station_idx': 0,
        'current_station': None,
        'last_passed_station': None,
        'next_station': None,
        'potheri': None,
        'stations': []
    }
