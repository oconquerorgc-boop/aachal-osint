import threading, asyncio, re, sqlite3, secrets, string, os, time
from datetime import datetime
from flask import Flask, request, render_template_string, session, redirect, url_for, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

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
SESSION_STR = '1BVtsOMMBu2tX6Ow4MSJrDU2FdzE4mWMJ3YIzpbl4SNceVpzf6v2tbkhwhuRzCwol_JnofJTw9z2bgPjRuEM4DI3Sa8ds6iAMhWZRl_pZWYbjpq4qgif3Oku5INJM_0MN6Dgamx4K4HuR88tsVIH63KdsLUgb8NatAurhzJP0kKPuwaWD6cbQKaomQgJ2T2C7gUE6s4fBPx4Vv4xKH4JNwIqeaZUourfibPvLjQ5XWxyhfe7N7iI-IBuHRq5lsagdDYcPxfuHKn9sPqRmsX8TCV_lsdZpv8OUNhJ6FvpHGWbPd5npRW0Wu6N_7TA3iYrWVodUTtg3Ql2OwfxxJfdVjlOoW2qaRc0='
TARGET_BOT = '@Osint2_info_bot'
BOT_TOKEN = '8666312234:AAHBQ1dt2yPElbpASleamyaJydvuhwU7B2o'
WEB_USER = "RICH"
WEB_PASS = "Ravi124421"
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

    # FINAL MENU WITH ALL NEW COMMANDS
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
        ("📝 Name Info", "📝 Name Info", "Full Name..."),
        ("🆔 Aadhaar ➔ Ration", "🆔 Aadhaar ➔ Ration", "Aadhaar Number..."),
        ("💳 PAN Info", "💳 PAN Info", "PAN Number..."),
        ("⚪ LPG Info", "⚪ LPG Info", "LPG ID / Mobile..."),
        ("🚗 Vehicle V3", "🚗 Vehicle V3", "Vehicle Number..."),
        ("🎮 FF Info", "🎮 FF Info", "Free Fire UID..."),
        ("📄 UPI Info", "📄 UPI Info", "UPI ID / Mobile..."),
        ("📄 Voter Info", "📄 Voter Info", "Voter ID / Name..."),
        ("🚗 Vehicle to Owner", "🚗 Vehicle to Owner", "Vehicle Number..."),
        ("🐙 GitHub Info", "🐙 GitHub Info", "GitHub Username..."),
        ("👻 Snapchat Info", "👻 Snapchat Info", "Snapchat Username..."),
        ("🚨 Vehicle Challan", "🚨 Vehicle Challan", "Vehicle Number..."),
        ("📸 Challan Photo", "📸 Challan Photo", "Vehicle Number..."),
    ]

    def main_menu():
        m = types.InlineKeyboardMarkup(row_width=2)
        m.add(*[types.InlineKeyboardButton(text=d, callback_data="cmd|"+a) for d, a, p in MENU])
        return m

    def extract_text(msg):
        if not msg: return ""
        return msg.raw_text or msg.text or ""

    def setup_handlers():
        global ev, captured
        if ev is None: ev = asyncio.Event()
        
        @client.on(events.NewMessage(incoming=True))
        async def h(e):
            global captured, ev, last_result_id
            if e.sender_id == (await client.get_entity(TARGET_BOT)).id:
                t = extract_text(e.message).lower()
                if "fetching" in t or "wait" in t: return
                if len(t) > 30 and ("number" in t or "record" in t or "name" in t or "address" in t):
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
                if r and extract_text(r):
                    bot.send_message(call.message.chat.id, f"<pre>{extract_text(r)}</pre>", parse_mode='HTML')
                else:
                    bot.send_message(call.message.chat.id, "❌ Timeout or No Text Result", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: True)
    def txt(m):
        msg = bot.send_message(m.chat.id, "📡 Search: " + m.text)
        with lock:
            r = asyncio.run_coroutine_threadsafe(send_wait("🔍 Num Lookup", m.text), loop).result()
            try: bot.delete_message(m.chat.id, msg.message_id)
            except: pass
            if r and extract_text(r):
                bot.send_message(m.chat.id, f"<pre>{extract_text(r)}</pre>", parse_mode='HTML')
            else:
                bot.send_message(m.chat.id, "❌ Timeout or No Text Result", reply_markup=main_menu())

    def run_bot():
        print("🤖 Telegram Bot Started...")
        bot.infinity_polling()

except Exception as e:
    print("⚠️ Bot libraries error: " + str(e))
    def run_bot(): pass
    def send_wait(cmd, query): return None
    def extract_text(msg): return ""
    MENU = [("🔍 Num Lookup", "🔍 Num Lookup", "10 Digit Mobile...")]

# ================= FLASK WEB =================
app = Flask(__name__)
app.secret_key = "rich_secret_123_change_me"

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
.ok{color:#00e676;font-size:13px;margin-bottom:10px;text-align:center;background:rgba(0,255,102,0.1);padding:8px;border-radius:5px;}
.link{margin-top:15px;font-size:13px;color:#888;text-align:center;}.link a{color:#ff6600;text-decoration:none;font-weight:bold;}
</style></head><body>
""" + get_bg_html() + """
<div class="box"><h2>RESET <span>{{panel_name}}</span></h2>{% if error %}<div class="error">{{error}}</div>{% endif %}{% if ok %}<div class="ok">{{ok}}</div>{% endif %}
<form method="POST">
    <div class="input-group"><label>USERNAME</label><input type="text" name="username" placeholder="Your Username" required></div>
    <div class="input-
