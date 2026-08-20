import re

with open('server.py', 'r', encoding='utf-8') as f:
    content = f.read()

import_sp = 'import sp_scraper\n'

routes = '''
@app.route('/api/sp/captcha', methods=['GET'])
def api_sp_captcha():
    try:
        data = sp_scraper.get_captcha()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sp/login', methods=['POST'])
def api_sp_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    captcha = data.get('captcha')
    temp_id = data.get('tempId')
    batch = data.get('batch', 'B.Tech')
    
    try:
        login_data = sp_scraper.sp_login(username, password, captcha, temp_id)
        session_id = login_data['token']
        profile = login_data['profile']
        
        # Fetch data immediately
        all_data = sp_scraper.get_all_data(session_id)
        
        # We need to map this data to our users table
        name = all_data['profile'].get('Name', 'Unknown')
        reg_no = all_data['profile'].get('RegistrationNumber', username)
        
        # Just update the DB
        conn = get_db()
        cur = conn.cursor()
        now = datetime.now().isoformat()
        
        try:
            if DATABASE_URL:
                cur.execute("""
                    INSERT INTO users (net_id, name, batch, last_sync, data_payload)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (net_id) DO UPDATE SET 
                        name = EXCLUDED.name,
                        batch = EXCLUDED.batch,
                        last_sync = EXCLUDED.last_sync,
                        data_payload = EXCLUDED.data_payload
                """, (username, name, batch, now, json.dumps(all_data)))
            else:
                cur.execute("""
                    INSERT INTO users (net_id, name, batch, last_sync, data_payload)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(net_id) DO UPDATE SET
                        name = excluded.name,
                        batch = excluded.batch,
                        last_sync = excluded.last_sync,
                        data_payload = excluded.data_payload
                """, (username, name, batch, now, json.dumps(all_data)))
            conn.commit()
        except Exception as e:
            print("DB error:", e)
        finally:
            cur.close()
            conn.close()
            
        return jsonify({'success': True, 'data': all_data})
    except Exception as e:
        print("Login error:", e)
        return jsonify({'success': False, 'error': str(e)})
'''

# insert import
if 'import sp_scraper' not in content:
    content = content.replace('import json\n', 'import json\n' + import_sp)

# insert routes before chat
if '/api/sp/captcha' not in content:
    content = content.replace("# --- CHAT & SPOTTED ENDPOINTS ---", routes + "\n# --- CHAT & SPOTTED ENDPOINTS ---")

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated server.py!')
