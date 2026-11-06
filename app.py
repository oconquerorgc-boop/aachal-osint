import threading, asyncio, re, sqlite3, secrets, string, os, time
from datetime import datetime
from flask import Flask, request, render_template_string, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import telebot
    from telebot import types
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
except ImportError:
    pass

# ================= CONFIG =================
API_ID = 37325833
API_HASH = '8d82b6543b9631209aebf4b5e03409fc'
SESSION_STR = '1BVtsOHUBu8J5LUCLkS6vRb7Sn86yjfPWuaWejjvfWClLLgvvdptBpa0lNXwg0RPO5yn5Wh61VgXy_UBEWX5jeXcWOnEu2CqXCkvjierGj730SpMwoSCzGi35phwBAayzzvXNcL-OXoDugc28Wfop-FkgTaHItalB4gObWpbST748Il6GJ4YXKKa8Gsrw9uavs_tJB8rCqOr31B0JdOBMn5szfBBnx2dLF6fArrZ3CSv1QSmE2UkhDm--qFPP4uc5Ytet5HT-k7BW5JDzHC7xcRVtweNr_T45-gVASzzXXxzaBnJCIeN7AWPn-KuQJvn3W8niq54TZf4fCWYD8-u9PDF9d1VNraI='
TARGET_BOT = '@Osint2_info_bot'
BOT_TOKEN = '9249884434:AAFIQieRI5vaydKvHRI6IC2PTeMpOm0q4pA'
WEB_USER = "RICH"
WEB_PASS = "DK124421"
SEARCH_COST = 100
SIGNUP_BONUS = 50
REFERRAL_BONUS = 100
DB = "osint.db"
TG_HELP_ID = "https://t.me/MrRichYT"

if not os.path.exists('static'):
    os.makedirs('static')
LOGO_FILE = os.path.join('static', 'custom_logo.jpg')
BG_FILE = os.path.join('static', 'custom_bg.bin')
BG_EXT_FILE = os.path.join('static', 'bg_ext.txt')

# ================= DATABASE =================
def init_db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,username TEXT UNIQUE,mobile TEXT,password_hash TEXT,raw_password TEXT,referral_code TEXT UNIQUE,referred_by TEXT,wallet REAL DEFAULT 0,is_admin INTEGER DEFAULT 0,is_blocked INTEGER DEFAULT 0,created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS redeem_codes(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE,amount REAL,created_by TEXT,used_by TEXT,status TEXT DEFAULT 'active',created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT UNIQUE, value TEXT)")
    
    if not c.execute("SELECT 1 FROM users WHERE username=?", (WEB_USER,)).fetchone():
        c.execute("INSERT INTO users(name,username,mobile,password_hash,raw_password,referral_code,wallet,is_admin,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  ("Admin", WEB_USER, "0000000000", generate_password_hash(WEB_PASS), WEB_PASS, "RICH-ADMIN1", 999999999, 1, datetime.now().isoformat()))
    else:
        c.execute("UPDATE users SET password_hash=?, raw_password=? WHERE username=?", 
                  (generate_password_hash(WEB_PASS), WEB_PASS, WEB_USER))
    
    if not c.execute("SELECT 1 FROM settings WHERE key='panel_name'").fetchone():
        c.execute("INSERT INTO settings(key, value) VALUES('panel_name', 'RICH')")
    c.commit(); c.close()

def get_setting(key):
    c = sqlite3.connect(DB)
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    c.close()
    return row[0] if row else ""

def set_setting(key, val):
    c = sqlite3.connect(DB)
    c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, val))
    c.commit(); c.close()

def gen_ref():
    while True:
        code = "RICH-" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        c = sqlite3.connect(DB)
        if not c.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone():
            c.close(); return code
        c.close()

def get_user(u):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    r = c.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
    c.close(); return dict(r) if r else None

def update_wallet(u, amt):
    c = sqlite3.connect(DB)
    row = c.execute("SELECT is_admin,wallet FROM users WHERE username=?", (u,)).fetchone()
    if not row: c.close(); return False
    if row[0] == 1: c.close(); return True
    if row[1] + amt < 0: c.close(); return False
    c.execute("UPDATE users SET wallet=wallet+? WHERE username=?", (amt, u))
    c.commit(); c.close(); return True

init_db()

# ================= BOT SETUP =================
try:
    bot = telebot.TeleBot(BOT_TOKEN, num_threads=2, threaded=False)
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH, loop=loop)
    lock = threading.Lock()
    captured = None
    ev = None
    last_result_id = None

    MENU = [
        ("🔍 Num Lookup", "🔍 Num Lookup", "10 Digit Mobile..."),
        ("🧠 TG ID ➔ Num", "🧠 TG ID ➔ Num", "Telegram ID..."),
        ("👤 TG User ➔ Num", "👤 TG User ➔ Num", "Username @..."),
        ("📁 Num ➔ All Info", "📁 Num ➔ All Info", "10 Digit Mobile..."),
        ("🪪 Aadhaar Info", "🪪 Aadhaar Info", "12 Digit Aadhaar..."),
        ("👨‍👩‍👧‍👦 Aadhaar Family", "👨‍👩‍👧‍👦 Aadhaar Family", "Aadhaar Number..."),
        ("🆔 Aadhaar ➔ PAN", "🆔 Aadhaar ➔ PAN", "Aadhaar Number..."),
        ("✉️ Email ➔ Num", "✉️ Email ➔ Num", "Email..."),
        ("🌐 Web Scraper", "🌐 Web Scraper", "URL..."),
        ("🚗 Vehicle ➔ Num", "🚗 Vehicle ➔ Num", "Vehicle Number..."),
        ("🏡 Vehicle Address", "🏡 Vehicle Address", "Vehicle Number..."),
        ("📄 RC ➔ PDF", "📄 RC ➔ PDF", "Vehicle Number..."),
        ("📝 Name Info", "📝 Name Info", "Full Name..."),
        ("🆔 Aadhaar ➔ Ration", "🆔 Aadhaar ➔ Ration", "Aadhaar Number..."),
        ("💳 PAN Info", "💳 PAN Info", "PAN Number..."),
        ("💼 PAN ➔ GST", "💼 PAN ➔ GST", "PAN Number..."),
        ("🚗 Vehicle V3", "🚗 Vehicle V3", "Vehicle Number..."),
        ("🎮 FF Info", "🎮 FF Info", "Free Fire UID..."),
        ("📄 UPI Info", "📄 UPI Info", "UPI ID..."),
        ("🗳️ Voter Info", "🗳️ Voter Info", "Voter ID..."),
        ("🚗 Vehicle to Owner", "🚗 Vehicle to Owner", "Vehicle Number..."),
        ("🐙 GitHub Info", "🐙 GitHub Info", "GitHub Username..."),
        ("👻 Snapchat Info", "👻 Snapchat Info", "Snapchat Username..."),
        ("🚨 Vehicle Challan", "🚨 Vehicle Challan", "Vehicle Number..."),
        ("📸 Challan Photo", "📸 Challan Photo", "Vehicle Number..."),
        ("⬜ LPG Info", "⬜ LPG Info", "LPG ID..."),
    ]

    def main_menu():
        m = types.InlineKeyboardMarkup(row_width=2)
        m.add(*[types.InlineKeyboardButton(text=d, callback_data="cmd|"+a) for d, a, p in MENU])
        return m

    def extract_text(msg):
        if not msg: return ""
        return msg.raw_text or msg.text or ""

    # ✅ File & Text Extraction (Update for PDF/Photo)
    def extract_result(msg):
        if not msg: return {"text": "", "file": None}
        text = extract_text(msg)
        
        # Agar target bot file ya photo bhejta hai
        if msg.document or msg.photo:
            return {"text": text, "file": f"/download/{msg.chat_id}/{msg.id}"}

        lines = text.split('\n')
        clean_lines = []
        for ln in lines:
            s = ln.strip()
            if not s: continue
            if "@suryaxz" in s or "COPY CODE" in s or "By :" in s: continue
            clean_lines.append(ln)
            
        return {"text": "\n".join(clean_lines), "file": None}

    def setup_handlers():
        global ev, captured
        if ev is None: ev = asyncio.Event()
        
        @client.on(events.NewMessage(incoming=True))
        async def h(e):
            global captured, ev, last_result_id
            if e.sender_id == (await client.get_entity(TARGET_BOT)).id:
                t = extract_text(e.message).lower()
                if "fetching" in t or "wait" in t: return
                # Text ya File capture karo
                if (len(t) > 30 and ("number" in t or "record" in t or "name" in t or "address" in t)) or e.message.document or e.message.photo:
                    if e.message.id != last_result_id:
                        last_result_id = e.message.id
                        captured = e.message
                        ev.set()

    def start_userbot():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.connect())
            setup_handlers()
            print("☠️ Userbot Active")
            loop.run_forever()
        except Exception as ex:
            print("❌ Userbot Error: " + str(ex))

    threading.Thread(target=start_userbot, daemon=True).start()

    async def send_wait(cmd, query):
        global captured, ev
        ev.clear(); captured = None
        await client.send_message(TARGET_BOT, cmd)
        await asyncio.sleep(1.5)
        await client.send_message(TARGET_BOT, query)
        try:
            await asyncio.wait_for(ev.wait(), timeout=30.0)
            await asyncio.sleep(1.0)
            return captured
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            return None

    @bot.message_handler(commands=['start'])
    def start(m):
        bot.send_message(m.chat.id, "⚡ RICH OSINT ⚡\nMenu:", reply_markup=main_menu())

    @bot.callback_query_handler(func=lambda c: True)
    def cb(call):
        if call.data.startswith("cmd|"):
            a = call.data.split("|")[1]
            bot.answer_callback_query(call.id, a)
            msg = bot.send_message(call.message.chat.id, "📡 " + a + "...")
            with lock:
                r = asyncio.run_coroutine_threadsafe(send_wait(a, a), loop).result()
                try: bot.delete_message(call.message.chat.id, msg.message_id)
                except: pass
                if r:
                    res = extract_result(r)
                    if res["text"]:
                        bot.send_message(call.message.chat.id, f"<pre>{res['text']}</pre>", parse_mode='HTML')
                    if res["file"]:
                        bot.send_document(call.message.chat.id, r.document)
                else:
                    bot.send_message(call.message.chat.id, "❌ Timeout or No Result", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: True)
    def txt(m):
        msg = bot.send_message(m.chat.id, "📡 Search: " + m.text)
        with lock:
            r = asyncio.run_coroutine_threadsafe(send_wait("🔍 Num Lookup", m.text), loop).result()
            try: bot.delete_message(m.chat.id, msg.message_id)
            except: pass
            if r:
                res = extract_result(r)
                if res["text"]:
                    bot.send_message(m.chat.id, f"<pre>{res['text']}</pre>", parse_mode='HTML')
                if res["file"]:
                    bot.send_document(m.chat.id, r.document)
            else:
                bot.send_message(m.chat.id, "❌ Timeout or No Result", reply_markup=main_menu())

    def run_bot():
        try:
            bot.remove_webhook() # Fix 409 Conflict
            time.sleep(2)
            print("🤖 Telegram Bot Started...")
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print("Bot Error:", e)

except Exception as e:
    print("⚠️ Bot libraries error: " + str(e))
    def run_bot(): pass
    def send_wait(cmd, query): return None
    def extract_result(msg): return {"text": "", "file": None}
    MENU = [("🔍 Num Lookup", "🔍 Num Lookup", "10 Digit Mobile...")]

# ================= FLASK WEB =================
app = Flask(__name__)
app.secret_key = "rich_secret_123_change_me"

# ✅ DOWNLOAD FILE ROUTE (PDF / HTML / IMAGE)
@app.route('/download/<int:chat_id>/<int:msg_id>')
def download_file(chat_id, msg_id):
    if 'user' not in session: 
        return "Unauthorized", 401
    try:
        async def get_file():
            msg = await client.get_messages(chat_id, ids=msg_id)
            if msg:
                path = await client.download_media(msg, file="static/dl_")
                return path
            return None
        
        file_path = asyncio.run_coroutine_threadsafe(get_file(), loop).result()
        if file_path and os.path.exists(file_path):
            ext = file_path.split('.')[-1]
            return send_file(file_path, as_attachment=True, download_name=f"Result.{ext}")
        return "File not found", 404
    except Exception as e:
        return f"Error: {e}", 500

def get_bg_html():
    if os.path.exists(BG_FILE) and os.path.exists(BG_EXT_FILE):
        with open(BG_EXT_FILE, 'r') as f:
            ext = f.read().strip()
        if ext in ['mp4', 'webm']:
            return f"<video autoplay loop muted playsinline style='position:fixed; top:0; left:0; width:100%; height:100%; object-fit:cover; z-index:-2;'><source src='/static/custom_bg.bin?t={datetime.now().timestamp()}' type='video/{ext}'></video>"
        else:
            return f"<div style='position:fixed; top:0; left:0; width:100%; height:100%; background:url(\"/static/custom_bg.bin?t={datetime.now().timestamp()}\") center/cover; z-index:-2;'></div>"
    return "<div style='position:fixed; top:0; left:0; width:100%; height:100%; background: radial-gradient(circle at top, #2b0505 0%, #050505 100%); z-index:-2;'></div>"

LOGIN = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{panel_name}} Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}
body{color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}
body::before{content:"";position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:-1;}
.box{background: rgba(15,15,15,0.95);padding:35px 25px;border-radius:16px;max-width:380px;width:100%;border:1px solid #ff3333;text-align:center;box-shadow: 0 0 20px rgba(255, 51, 51, 0.2);position:relative;}
.tg-help{position:absolute;top:15px;right:15px;width:35px;height:35px;border-radius:50%;background:#229ED9;display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px rgba(34,158,217,0.5);transition:0.2s;border:2px solid #fff;}
.tg-help:hover{transform:scale(1.1);}
.tg-help svg{width:20px;height:20px;fill:#fff;}
.logo{width:130px;height:130px;border-radius:50%;border:2px solid #ff3333;margin:0 auto 20px auto;display:flex;align-items:center;justify-content:center;background: radial-gradient(circle, #ff0000 0%, #000 70%);box-shadow: 0 0 25px #ff0000;position:relative;flex-direction:column;overflow:hidden;}
.logo img{width:100%;height:100%;object-fit:cover;}
.logo .crown{font-size:30px;position:absolute;top:-10px;z-index:2;}
.logo .letter{font-size:50px;font-weight:900;color:#fff;text-shadow:0 0 10px #ff0000;font-family: 'Times New Roman', serif;z-index:1;}
.logo-text{position:absolute;bottom:12px;font-size:9px;letter-spacing:2px;color:#fff;font-weight:bold;border-top:1px solid #ff3333;padding-top:2px;width:60%;z-index:2;}
h2{color:#fff;margin-bottom:5px;font-weight:bold;letter-spacing:1px;font-size:18px;}
h2 span{color:#ff6600;}
p.subtitle{font-size:11px;color:#888;margin-bottom:20px;letter-spacing:1px;}
.input-group{text-align:left;margin-bottom:12px;}
.input-group label{font-size:11px;color:#ccc;margin-bottom:5px;display:block;letter-spacing:1px;}
.input-group input{width:100%;padding:12px;background:#111;border:1px solid #333;border-radius:8px;color:#fff;font-size:14px;}
.input-group input:focus{border-color:#ff3333;outline:none;}
button{width:100%;padding:14px;background: linear-gradient(90deg, #ff3333, #ff6600);color:#fff;font-weight:900;border:none;border-radius:8px;cursor:pointer;font-size:15px;letter-spacing:1px;margin-top:10px;box-shadow: 0 0 15px rgba(255,102,0,0.4);transition:0.3s;}
button:hover{transform:scale(1.02);}
.error{color:#f33;font-size:13px;margin-bottom:10px;background:rgba(255,0,0,0.1);padding:8px;border-radius:5px;}
.link{margin-top:20px;font-size:12px;color:#888;display:flex;justify-content:space-between;}
.link a{color:#ff6600;text-decoration:none;font-weight:bold;}
.checkbox-row{display:flex;align-items:center;justify-content:flex-start;margin-bottom:15px;font-size:12px;color:#aaa;}
.checkbox-row input{width:auto;margin:0 10px 0 0;}
</style></head><body>
""" + get_bg_html() + """
<div class="box">
    <a href="{{tg_link}}" target="_blank" class="tg-help">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.02-1.96 1.25-5.54 3.69-.52.36-1 .53-1.42.52-.47-.01-1.37-.26-2.03-.48-.82-.27-1.47-.42-1.42-.88.03-.24.36-.48.99-.74 3.86-1.68 6.44-2.79 7.73-3.32 3.68-1.53 4.44-1.8 4.94-1.8.11 0 .35.03.51.15.13.09.2.23.22.37.01.1.01.2-.01.27z"/></svg>
    </a>
    <div class="logo">
        {% if has_logo %}<img src="/static/custom_logo.jpg?t={{time}}" alt="Logo">
        {% else %}<span class="crown">👑</span><span class="letter">R</span><span class="logo-text">VIP PANEL</span>{% endif %}
    </div>
    <h2>Welcome to <span>{{panel_name}}</span></h2>
    <p class="subtitle">⚡ PREMIUM OSINT PANEL ⚡</p>
    {% if error %}<div class="error">{{error}}</div>{% endif %}
    {% if msg %}<div class="error" style="color:#00e676;background:rgba(0,230,118,0.1);">{{msg}}</div>{% endif %}
    <form method="POST">
        <div class="input-group"><label>USERNAME</label><input type="text" name="username" placeholder="Enter username" required></div>
        <div class="input-group"><label>PASSWORD</label><input type="password" name="password" placeholder="Enter password" required></div>
        <div class="checkbox-row"><input type="checkbox" id="rem"><label for="rem">Remember me (stay logged in 24h)</label></div>
        <button type="submit">⚡ ENTER THE {{panel_name|upper}} ⚡</button>
    </form>
    <div class="link"><a href="/forgot">Forgot password?</a> <a href="/signup">Create Account</a></div>
</div></body></html>"""

# ✅ UPDATED DASHBOARD (Owner Control, No Redeem Code, Animation & Download Fix)
DASHBOARD = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RICH OSINT</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}

/* 👇 Yahan padding-top: 80px; add kiya hai taaki upar premium space aaye */
body{background:#050505;color:#fff;padding:80px 15px 15px 15px;min-height:100vh;}

/* Top Bar */
.top-bar{display:flex;align-items:center;justify-content:space-between;background:#111;border:1px solid #ff3333;padding:10px 15px;border-radius:12px;margin-bottom:20px;box-shadow:0 0 15px rgba(255,51,51,0.2);}
.profile-pic{width:45px;height:45px;border-radius:50%;border:2px solid #ff3333;object-fit:cover;}
.owner-badge{background:linear-gradient(90deg, #ff3333, #ff6600);color:#fff;padding:8px 20px;border-radius:30px;font-weight:900;font-size:14px;letter-spacing:1px;display:flex;align-items:center;gap:5px;box-shadow:0 0 15px rgba(255,102,0,0.5);}
.tg-btn{width:40px;height:40px;border-radius:50%;background:#229ED9;display:flex;align-items:center;justify-content:center;color:#fff;text-decoration:none;font-weight:bold;}

/* Main Card */
.card{background:#111;border:1px solid #ff3333;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 0 15px rgba(255,51,51,0.1);}
.card h1{font-size:22px;text-align:center;margin-bottom:5px;letter-spacing:2px;}
.card h1 span{color:#ff3333;}
.card p{text-align:center;color:#ff6600;font-size:12px;margin-bottom:20px;letter-spacing:1px;}
.search-box{display:flex;background:#050505;border:1px solid #333;border-radius:8px;overflow:hidden;}
.search-box input{flex:1;padding:14px;background:transparent;border:none;color:#fff;font-size:14px;outline:none;}
.search-box button{background:linear-gradient(90deg, #ff3333, #ff6600);color:#fff;border:none;padding:0 25px;font-weight:bold;cursor:pointer;font-size:14px;}

/* Grid */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px;}
.grid button{padding:14px 5px;background:#0a0a0a;border:1px solid #333;color:#ddd;border-radius:8px;cursor:pointer;font-size:13px;font-weight:bold;transition:0.2s;}
.grid button:hover{border-color:#ff3333;color:#fff;box-shadow:0 0 10px rgba(255,51,51,0.3);}

/* Result Box */
.res-box{background:#0a0a0a;border:1px dashed #555;padding:15px;border-radius:8px;min-height:100px;white-space:pre-wrap;font-family:monospace;font-size:13px;color:#00ff66;line-height:1.5;}
.res-box::-webkit-scrollbar{width:5px;}
.res-box::-webkit-scrollbar-thumb{background:#ff3333;}

/* Loading */
.loader{text-align:center;color:#ff6600;font-weight:bold;animation:pulse 1s infinite;}
@keyframes pulse{0%{opacity:0.5;}50%{opacity:1;}100%{opacity:0.5;}}

/* Footer */
.footer{text-align:center;font-size:10px;color:#555;margin-top:30px;letter-spacing:1px;}
</style>
<script>
async function doSearch(cmd, btn) {
    let val = document.getElementById('query').value;
    if(!val) return alert('⚠️ Please enter a value to search!');
    
    let box = document.getElementById('result');
    box.innerHTML = "<div class='loader'>⏳ Fetching Data from Server...</div>";
    
    let originalText = btn.innerHTML;
    btn.innerHTML = "⏳";
    btn.disabled = true;
    
    try {
        let res = await fetch('/api/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cmd: cmd, query: val})
        });
        let data = await res.json();
        
        if(data.status === 'success') {
            let html = data.text ? `<div style="color:#fff;">${data.text}</div>` : '<div style="color:#888;">No text data found.</div>';
            if(data.file) {
                html += `<br><a href="${data.file}" target="_blank" style="display:block; text-align:center; background:linear-gradient(90deg,#00b09b,#96c93d); color:#fff; padding:12px; border-radius:8px; text-decoration:none; font-weight:bold; margin-top:10px;">📥 DOWNLOAD FILE / PDF</a>`;
            }
            box.innerHTML = html;
        } else {
            box.innerHTML = "<div style='color:#ff3333;'>❌ " + data.message + "</div>";
        }
    } catch(e) {
        box.innerHTML = "<div style='color:#ff3333;'>❌ Network Error!</div>";
    }
    
    btn.innerHTML = originalText;
    btn.disabled = false;
}
</script>
</head><body>

<!-- 🔴 TOP BAR: OWNER CONTROL 🔴 -->
<div class="top-bar">
    <img src="/static/custom_logo.jpg" class="profile-pic" onerror="this.src='https://ui-avatars.com/api/?name=Rich&background=ff3333&color=fff'">
    
    <div class="owner-badge">
        👑 OWNER CONTROL
    </div>
    
    <a href="https://t.me/MrRichYT" target="_blank" class="tg-btn">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="#fff"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.02-1.96 1.25-5.54 3.69-.52.36-1 .53-1.42.52-.47-.01-1.37-.26-2.03-.48-.82-.27-1.47-.42-1.42-.88.03-.24.36-.48.99-.74 3.86-1.68 6.44-2.79 7.73-3.32 3.68-1.53 4.44-1.8 4.94-1.8.11 0 .35.03.51.15.13.09.2.23.22.37.01.1.01.2-.01.27z"/></svg>
    </a>
</div>

<!-- 🔍 SEARCH CARD -->
<div class="card">
    <h1>⚡ <span>RICH</span> OSINT ⚡</h1>
    <p>₹100/SEARCH • FAST & SECURE</p>
    <div class="search-box">
        <input type="text" id="query" placeholder="Enter value (Number, Aadhaar, Vehicle)...">
        <button onclick="doSearch('📁 Num ➔ All Info', this)">Search</button>
    </div>
</div>

<!-- 📱 ALL COMMANDS GRID -->
<div class="grid">
""" + "".join([f'<button onclick="doSearch(\'{cmd}\', this)">{label}</button>' for label, cmd, ph in MENU]) + """
</div>

<!-- 📄 RESULT BOX -->
<div class="res-box" id="result">> System Ready...<br>> Select a command and enter query to start.</div>

<div class="footer">
    POWERED BY RICH • MY REF: RICH-ADMIN1
</div>

</body></html>"""

SIGNUP = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Signup</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}
body{color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}
body::before{content:"";position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:-1;}
.box{background: rgba(15,15,15,0.95);padding:30px 25px;border-radius:16px;max-width:400px;width:100%;border:1px solid #ff3333;}
h2{color:#fff;margin-bottom:20px;text-align:center;letter-spacing:2px;} h2 span{color:#ff6600;}
.input-group{text-align:left;margin-bottom:10px;} .input-group label{font-size:11px;color:#ccc;display:block;margin-bottom:3px;}
.input-group input{width:100%;padding:12px;background:#111;border:1px solid #333;border-radius:8px;color:#fff;font-size:14px;}
.input-group input:focus{border-color:#ff3333;outline:none;}
button{width:100%;padding:14px;background: linear-gradient(90deg, #ff3333, #ff6600);color:#fff;font-weight:900;border:none;border-radius:8px;cursor:pointer;font-size:15px;margin-top:10px;}
.error{color:#f33;font-size:13px;margin-bottom:10px;text-align:center;background:rgba(255,0,0,0.1);padding:8px;border-radius:5px;}
.link{margin-top:15px;font-size:13px;color:#888;text-align:center;}.link a{color:#ff6600;text-decoration:none;font-weight:bold;}
</style></head><body>
""" + get_bg_html() + """
<div class="box"><h2>JOIN <span>{{panel_name}}</span></h2>{% if error %}<div class="error">{{error}}</div>{% endif %}
<form method="POST">
    <div class="input-group"><label>FULL NAME</label><input type="text" name="name" placeholder="Full Name" required></div>
    <div class="input-group"><label>USERNAME</label><input type="text" name="username" placeholder="Username" required></div>
    <div class="input-group"><label>MOBILE NUMBER</label><input type="text" name="mobile" placeholder="10 Digits Mobile" pattern="[0-9]{10}" required></div>
    <div class="input-group"><label>PASSWORD</label><input type="password" name="password" placeholder="Min 6 characters" minlength="6" required></div>
    <div class="input-group"><label>REFERRAL CODE (Optional)</label><input type="text" name="referral" placeholder="Enter Referral Code (Optional)"></div>
    <button type="submit">Create Account 🚀</button>
</form>
<div class="link">Have account? <a href="/login">Login ➜</a></div></div></body></html>"""

FORGOT = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forgot Password</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}
body{color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}
body::before{content:"";position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:-1;}
.box{background: rgba(15,15,15,0.95);padding:30px 25px;border-radius:16px;max-width:400px;width:100%;border:1px solid #ff3333;}
h2{color:#fff;margin-bottom:20px;text-align:center;letter-spacing:2px;} h2 span{color:#ff6600;}
.input-group{text-align:left;margin-bottom:10px;} .input-group label{font-size:11px;color:#ccc;display:block;margin-bottom:3px;}
.input-group input{width:100%;padding:12px;background:#111;border:1px solid #333;border-radius:8px;color:#fff;font-size:14px;}
.input-group input:focus{border-color:#ff3333;outline:none;}
button{width:100%;padding:14px;background: linear-gradient(90deg, #ff3333, #ff6600);color:#fff;font-weight:900;border:none;border-radius:8px;cursor:pointer;font-size:15px;margin-top:10px;}
.error{color:#f33;font-size:13px;margin-bottom:10px;text-align:center;background:rgba(255,0,0,0.1);padding:8px;border-radius:5px;}
.link{margin-top:15px;font-size:13px;color:#888;text-align:center;}.link a{color:#ff6600;text-decoration:none;font-weight:bold;}
</style></head><body>
""" + get_bg_html() + """
<div class="box"><h2>RESET <span>PASSWORD</span></h2>
{% if error %}<div class="error">{{error}}</div>{% endif %}
<form method="POST">
    <div class="input-group"><label>USERNAME OR MOBILE</label><input type="text" name="username" placeholder="Enter Username/Mobile" required></div>
    <button type="submit">Reset Password 🔐</button>
</form>
<div class="link">Remember? <a href="/login">Login ➜</a></div></div></body></html>"""

# ================= ROUTES =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        user = get_user(u)
        if user and check_password_hash(user['password_hash'], p):
            session['user'] = u
            return redirect(url_for('dashboard'))
        return render_template_string(LOGIN, panel_name="RICH", error="Invalid Credentials", has_logo=os.path.exists(LOGO_FILE), time=time.time(), tg_link=TG_HELP_ID)
    return render_template_string(LOGIN, panel_name="RICH", has_logo=os.path.exists(LOGO_FILE), time=time.time(), tg_link=TG_HELP_ID)

@app.route('/')
def dashboard():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template_string(DASHBOARD)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        u = request.form.get('username')
        m = request.form.get('mobile')
        p = request.form.get('password')
        ref = request.form.get('referral')
        
        c = sqlite3.connect(DB)
        if c.execute("SELECT 1 FROM users WHERE username=?", (u,)).fetchone():
            c.close()
            return render_template_string(SIGNUP, panel_name="RICH", error="Username already exists!", has_logo=os.path.exists(LOGO_FILE), time=time.time())
        
        code = gen_ref()
        c.execute("INSERT INTO users(name,username,mobile,password_hash,raw_password,referral_code,referred_by,wallet,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (name, u, m, generate_password_hash(p), p, code, ref, SIGNUP_BONUS, datetime.now().isoformat()))
        c.commit(); c.close()
        return redirect(url_for('login'))
    return render_template_string(SIGNUP, panel_name="RICH", has_logo=os.path.exists(LOGO_FILE), time=time.time())

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        return render_template_string(FORGOT, panel_name="RICH", error="Please contact @MrRichYT for password reset.", has_logo=os.path.exists(LOGO_FILE), time=time.time())
    return render_template_string(FORGOT, panel_name="RICH", has_logo=os.path.exists(LOGO_FILE), time=time.time())

# ✅ API Route for Dashboard AJAX
@app.route('/api/search', methods=['POST'])
def api_search():
    if 'user' not in session: 
        return {"status": "error", "message": "Unauthorized"}
    
    data = request.json
    cmd = data.get('cmd')
    query = data.get('query')
    
    with lock:
        r = asyncio.run_coroutine_threadsafe(send_wait(cmd, query), loop).result()
        if r:
            res = extract_result(r)
            return {"status": "success", "text": res["text"], "file": res["file"]}
        return {"status": "error", "message": "Timeout or Target Bot didn't respond."}

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
