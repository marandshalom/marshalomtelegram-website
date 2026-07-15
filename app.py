from flask import Flask, request, jsonify, render_template_string
import requests
import os
import random
import hmac
import hashlib
import json
from urllib.parse import parse_qsl
import psycopg2
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ===== ደህንነቱ የተጠበቀ - ከ Render Environment Variables ይነበባል =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@MarshalomTech")   # የቻናል username ወይም ID
BOT_USERNAME = os.environ.get("BOT_USERNAME", "marshalom_bot")  # ያለ @
DATABASE_URL = os.environ.get("DATABASE_URL")  # Render ራሱ ይሞላዋል ዳታቤዝ ሲያገናኙ
BASE_URL = os.environ.get("BASE_URL", "https://lwam-bot.onrender.com")  # የቦትዎ Render URL
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")        # ሙሉ አድሚን መዳረሻ ላለው password (አድሚን 1)
ADMIN_PASSWORD_2 = os.environ.get("ADMIN_PASSWORD_2")      # ሁለተኛ አድሚን password (አድሚን 2)
TECHNICAL_PASSWORD = os.environ.get("TECHNICAL_PASSWORD")  # የተወሰነ ቴክኒክ መዳረሻ ላለው password
# ====================================

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_with_webapp_button(chat_id, text, button_text, webapp_path):
    """Sends a message with a web_app inline button. Logs the real Telegram error
    if it fails, and falls back to a plain url button so the user still gets something."""
    webapp_url = f"{BASE_URL.rstrip('/')}{webapp_path}"
    result = requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        'chat_id': chat_id,
        'text': text,
        'reply_markup': {'inline_keyboard': [[{'text': button_text, 'web_app': {'url': webapp_url}}]]}
    })
    resp_json = result.json() if result.ok or result.content else {}
    if not resp_json.get('ok'):
        print(f"⚠️ web_app button send failed: {resp_json.get('description')} (BASE_URL={BASE_URL}, url={webapp_url})")
        # Fallback: plain URL button (opens in external browser instead of embedded Mini App)
        requests.post(f"{TELEGRAM_URL}/sendMessage", json={
            'chat_id': chat_id,
            'text': text,
            'reply_markup': {'inline_keyboard': [[{'text': button_text, 'url': webapp_url}]]}
        })
    return resp_json
ETHIOPIA_TZ = pytz.timezone("Africa/Addis_Ababa")

# ===== ዳታቤዝ (Postgres) =====
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL not set - storage disabled")
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS promos (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL,
                text_am TEXT,
                text_en TEXT,
                text_ti TEXT,
                text_or TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("ALTER TABLE promos ADD COLUMN IF NOT EXISTS text_am TEXT")
        cur.execute("ALTER TABLE promos ADD COLUMN IF NOT EXISTS text_en TEXT")
        cur.execute("ALTER TABLE promos ADD COLUMN IF NOT EXISTS text_ti TEXT")
        cur.execute("ALTER TABLE promos ADD COLUMN IF NOT EXISTS text_or TEXT")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                photo_url TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                user_id BIGINT PRIMARY KEY,
                name TEXT,
                username TEXT,
                message_count INTEGER DEFAULT 1,
                first_seen TIMESTAMP DEFAULT NOW(),
                last_seen TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS price_inquiries (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                name TEXT,
                username TEXT,
                product_name TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("ALTER TABLE price_inquiries ADD COLUMN IF NOT EXISTS product_name TEXT")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                location TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id SERIAL PRIMARY KEY,
                job_id INTEGER,
                job_title TEXT,
                user_id BIGINT,
                name TEXT,
                username TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT,
                position TEXT,
                salary TEXT,
                bonus TEXT DEFAULT '',
                warnings TEXT DEFAULT '',
                tasks TEXT DEFAULT '',
                role TEXT DEFAULT 'employee',
                must_change_password BOOLEAN DEFAULT TRUE,
                telegram_chat_id BIGINT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Safe upgrades for already-existing tables from earlier deploys
        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'employee'")
        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT TRUE")
        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                name TEXT,
                username TEXT,
                text TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                chat_id BIGINT PRIMARY KEY,
                role TEXT NOT NULL,
                employee_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database ready.")
    except Exception as e:
        print(f"DB init error: {e}")

# ===== የማስታወቂያ ማከማቻ (Promo storage) =====
def load_promos():
    if not DATABASE_URL:
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(text_am, text) FROM promos ORDER BY id")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [r[0] for r in rows]
    except Exception as e:
        print(f"DB load error: {e}")
        return []

def add_promo(raw_text):
    """Stores a promo, auto-enhanced and translated into 4 languages via DeepSeek."""
    if not DATABASE_URL:
        return 0
    try:
        translations = enhance_and_translate_promo(raw_text)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO promos (text, text_am, text_en, text_ti, text_or) VALUES (%s,%s,%s,%s,%s)",
            (raw_text, translations["am"], translations["en"], translations["ti"], translations["or"])
        )
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM promos")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except Exception as e:
        print(f"DB add error: {e}")
        return 0

def get_promos_multilang():
    if not DATABASE_URL:
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, COALESCE(text_am,text), COALESCE(text_en,text), COALESCE(text_ti,text), COALESCE(text_or,text) FROM promos ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"id": r[0], "am": r[1], "en": r[2], "ti": r[3], "or": r[4]} for r in rows]
    except Exception as e:
        print(f"DB get_promos_multilang error: {e}")
        return []

# ===== የምርት ካታሎግ (Products) =====
def get_products(category=None):
    if not DATABASE_URL:
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if category:
            cur.execute("SELECT id, name, category, description, photo_url FROM products WHERE category=%s ORDER BY id DESC", (category,))
        else:
            cur.execute("SELECT id, name, category, description, photo_url FROM products ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"id": r[0], "name": r[1], "category": r[2], "description": r[3], "photo_url": r[4]} for r in rows]
    except Exception as e:
        print(f"DB get_products error: {e}")
        return []

def add_product(name, category, description, photo_url):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (name, category, description, photo_url) VALUES (%s,%s,%s,%s) RETURNING id",
        (name, category, description, photo_url)
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id

def delete_product(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
    conn.commit()
    cur.close()
    conn.close()

# ===== የደንበኛ መዝገብ (Customers) =====
def upsert_customer(user_id, name, username):
    if not DATABASE_URL or not user_id:
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO customers (user_id, name, username, message_count, last_seen)
            VALUES (%s, %s, %s, 1, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                name = EXCLUDED.name,
                username = EXCLUDED.username,
                message_count = customers.message_count + 1,
                last_seen = NOW()
        """, (user_id, name, username))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB upsert_customer error: {e}")

def log_price_inquiry(user_id, name, username, product_name=None):
    if not DATABASE_URL:
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO price_inquiries (user_id, name, username, product_name) VALUES (%s,%s,%s,%s)",
            (user_id, name, username, product_name)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB log_price_inquiry error: {e}")

# ===== የስራ ማስታወቂያ (Jobs) =====
def get_jobs():
    if not DATABASE_URL:
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, description, location FROM jobs WHERE active=TRUE ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"id": r[0], "title": r[1], "description": r[2], "location": r[3]} for r in rows]
    except Exception as e:
        print(f"DB get_jobs error: {e}")
        return []

def add_job(title, description, location):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO jobs (title, description, location) VALUES (%s,%s,%s) RETURNING id", (title, description, location))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id

def delete_job(job_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET active=FALSE WHERE id=%s", (job_id,))
    conn.commit()
    cur.close()
    conn.close()

def add_job_application(job_id, job_title, user_id, name, username, phone):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO job_applications (job_id, job_title, user_id, name, username, phone) VALUES (%s,%s,%s,%s,%s,%s)",
        (job_id, job_title, user_id, name, username, phone)
    )
    conn.commit()
    cur.close()
    conn.close()

def get_stats():
    if not DATABASE_URL:
        return {"customers": 0, "messages": 0, "price_inquiries": 0, "products": 0, "promos": 0}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(message_count),0) FROM customers")
        cust_count, msg_count = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM price_inquiries")
        price_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM products")
        product_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM promos")
        promo_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {
            "customers": cust_count, "messages": msg_count,
            "price_inquiries": price_count, "products": product_count,
            "promos": promo_count
        }
    except Exception as e:
        print(f"DB get_stats error: {e}")
        return {"customers": 0, "messages": 0, "price_inquiries": 0, "products": 0, "promos": 0}

def get_customers_list():
    if not DATABASE_URL:
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name, username, message_count, last_seen FROM customers ORDER BY last_seen DESC LIMIT 200")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"user_id": r[0], "name": r[1], "username": r[2], "message_count": r[3], "last_seen": str(r[4])} for r in rows]
    except Exception as e:
        print(f"DB get_customers_list error: {e}")
        return []

# ===== Session (login) management - password-based access from any device =====
def set_session(chat_id, role, employee_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sessions (chat_id, role, employee_id) VALUES (%s, %s, %s)
        ON CONFLICT (chat_id) DO UPDATE SET role = EXCLUDED.role, employee_id = EXCLUDED.employee_id, created_at = NOW()
    """, (chat_id, role, employee_id))
    conn.commit()
    cur.close()
    conn.close()

def get_session(chat_id):
    if not DATABASE_URL:
        return None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT role, employee_id FROM sessions WHERE chat_id=%s", (chat_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"role": row[0], "employee_id": row[1]}
        return None
    except Exception as e:
        print(f"DB get_session error: {e}")
        return None

def clear_session(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE chat_id=%s", (chat_id,))
    conn.commit()
    cur.close()
    conn.close()

def is_admin_chat(chat_id):
    """True if this chat is the original owner OR has an active admin-password session."""
    if str(chat_id) == str(OWNER_CHAT_ID):
        return True
    session = get_session(chat_id)
    return session is not None and session["role"] == "admin"

def is_technical_chat(chat_id):
    session = get_session(chat_id)
    return session is not None and session["role"] in ("admin", "technical")

def is_team_leader_or_admin(chat_id):
    """True if this chat is a full admin OR a logged-in employee with role='team_leader'."""
    if is_admin_chat(chat_id):
        return True
    session = get_session(chat_id)
    if session and session["role"] == "employee" and session.get("employee_id"):
        emp = get_employee_by_id(session["employee_id"])
        return emp is not None and emp.get("role") == "team_leader"
    return False

def generate_temp_password():
    import random as _r
    import string as _s
    return ''.join(_r.choices(_s.ascii_uppercase + _s.digits, k=8))

# ===== የሰራተኛ አስተዳደር (Employees) =====
def add_employee(username, password, full_name, position, salary):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO employees (username, password, full_name, position, salary, must_change_password)
        VALUES (%s,%s,%s,%s,%s,TRUE) RETURNING id
    """, (username, password, full_name, position, salary))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id

def get_employee_by_credentials(username, password):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, position, salary, bonus, warnings, tasks, role, must_change_password FROM employees WHERE username=%s AND password=%s", (username, password))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {"id": row[0], "full_name": row[1], "position": row[2], "salary": row[3], "bonus": row[4],
                "warnings": row[5], "tasks": row[6], "role": row[7], "must_change_password": row[8]}
    return None

def get_employee_by_id(employee_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, position, salary, bonus, warnings, tasks, role, must_change_password, telegram_chat_id FROM employees WHERE id=%s", (employee_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "full_name": row[2], "position": row[3], "salary": row[4],
                "bonus": row[5], "warnings": row[6], "tasks": row[7], "role": row[8],
                "must_change_password": row[9], "telegram_chat_id": row[10]}
    return None

def get_employee_by_username(username):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, position, salary, bonus, warnings, tasks, role, must_change_password, telegram_chat_id FROM employees WHERE username=%s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "full_name": row[2], "position": row[3], "salary": row[4],
                "bonus": row[5], "warnings": row[6], "tasks": row[7], "role": row[8],
                "must_change_password": row[9], "telegram_chat_id": row[10]}
    return None

def list_employees():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, position, role FROM employees ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "username": r[1], "full_name": r[2], "position": r[3], "role": r[4]} for r in rows]

def update_employee_field(username, field, value, append=False):
    """field is one of: bonus, warnings, tasks, salary"""
    conn = get_db_connection()
    cur = conn.cursor()
    if append:
        cur.execute(f"UPDATE employees SET {field} = {field} || %s WHERE username=%s", (f"\n• {value}", username))
    else:
        cur.execute(f"UPDATE employees SET {field} = %s WHERE username=%s", (value, username))
    conn.commit()
    cur.close()
    conn.close()

def set_employee_password(username, new_password, must_change=False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE employees SET password=%s, must_change_password=%s WHERE username=%s", (new_password, must_change, username))
    conn.commit()
    cur.close()
    conn.close()

def set_employee_role(username, role):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE employees SET role=%s WHERE username=%s", (role, username))
    conn.commit()
    cur.close()
    conn.close()

def set_employee_chat_id(employee_id, chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE employees SET telegram_chat_id=%s WHERE id=%s", (chat_id, employee_id))
    conn.commit()
    cur.close()
    conn.close()

# ===== የደንበኛ አስተያየት (Customer Feedback) =====
def add_feedback(user_id, name, username, text):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO feedback (user_id, name, username, text) VALUES (%s,%s,%s,%s)", (user_id, name, username, text))
    conn.commit()
    cur.close()
    conn.close()

def get_recent_feedback(limit=20):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, username, text, created_at FROM feedback ORDER BY id DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"name": r[0], "username": r[1], "text": r[2], "created_at": str(r[3])} for r in rows]

# ===== Telegram WebApp initData ማረጋገጫ (Security) =====
def verify_telegram_webapp_data(init_data):
    """የቴሌግራም Mini App የላከውን initData ትክክለኛነት ያረጋግጣል"""
    try:
        parsed = dict(parse_qsl(init_data))
        received_hash = parsed.pop('hash', None)
        if not received_hash:
            return None
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if computed_hash == received_hash:
            user_data = json.loads(parsed.get('user', '{}'))
            return user_data
        return None
    except Exception as e:
        print(f"WebApp verify error: {e}")
        return None

# ===== ሙከራ =====
@app.route('/test', methods=['GET'])
def test():
    result = "🔑 Environment Variables:\n\n"
    result += f"TELEGRAM_TOKEN: {'✅ SET' if TELEGRAM_TOKEN else '❌ NOT SET'}\n"
    result += f"OWNER_CHAT_ID: {'✅ SET' if OWNER_CHAT_ID else '❌ NOT SET'}\n"
    result += f"DEEPSEEK_API_KEY: {'✅ SET' if DEEPSEEK_API_KEY else '❌ NOT SET'}\n"
    result += f"CHANNEL_ID: {CHANNEL_ID}\n"
    result += f"BOT_USERNAME: {BOT_USERNAME}\n"
    result += f"BASE_URL: {BASE_URL}\n"
    result += f"DATABASE_URL: {'✅ SET' if DATABASE_URL else '❌ NOT SET'}\n"
    result += f"📦 የተከማቹ ማስታወቂያዎች: {len(load_promos())}\n"

    if DEEPSEEK_API_KEY:
        try:
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "Hello"}]
            }
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                result += "\n✅ DeepSeek API is working!"
            else:
                result += f"\n❌ DeepSeek API error: {response.status_code} - {response.text[:300]}"
        except Exception as e:
            result += f"\n❌ Error: {str(e)}"
    else:
        result += "\n❌ DEEPSEEK_API_KEY is not set!"

    return result

# ===== ሲስተም መመሪያ =====
SYSTEM_PROMPT = """አንተ "Marshalom AI" ነህ — የ Shalom Technology ረዳት።
የቢዝነሱ ባለቤት ስም ማርሻሎም ነው።
ቋንቋ: ደንበኛው በምንም ቋንቋ ቢጽፍ በዚያው ምላሽ ስጥ።
ስብዕና: ተፈጥሯዊ፣ ሙቀት ያለው፣ ወዳጃዊ ሁን።
አገልግሎቶቻችን: CCTV ካሜራ, ኔትወርክ, ኤሌክትሮኒክስ
ስለ ዋጋ: ቁጥር አትጥቀስ።
ማህበራዊ ሚዲያ: 0931556590, www.marshalom.com, YouTube, TikTok"""

WELCOME_MESSAGE = """✨ እንኳን ደህና መጡ ወደ SHALOM TECHNOLOGY! ✨

🎥📷🔒 እኛ በኤሌክትሮኒክስ እና በደህንነት ካሜራዎች ላይ ጥራት ያለው አገልግሎት የምንሰጥ ታማኝ የቴክኖሎጂ አጋርዎ ነን። ✅

🚀 ለምን እኛን ይመርጣሉ?
🔹 ዘመናዊ የደህንነት ካሜራዎች (CCTV) 📷🎥
🔹 ጥራት ያላቸው ኤሌክትሮኒክስ እቃዎች 📺🔌
🔹 ፈጣን እና አስተማማኝ አገልግሎት ⚡️✅

📢 ቻናላችንን ይቀላቀሉ: https://t.me/cctvcamera2018
🌐 ድር ጣቢያ: www.marshalom.com
📞 ስልክ: 0931556590"""

BUSY_MESSAGE = """🌟 ማርሻሎም (Marshalom) የቴክኖሎጂ ረዳት 🌟
ሰላም! መልእክትዎን ስላደረሱን እናመሰግናለን። 🙏
አሁን ላይ እጅግ በጣም ብዙ ጥያቄዎችን በማስተናገድ ላይ ስለሆንን፣ ትክክለኛ ምላሽ ለእርስዎ ለመስጠት ጥቂት ደቂቃዎች ይጠብቁ። ⏳

📞 አስቸኳይ ከሆነ: 0931556590"""

# ===== DeepSeek AI =====
def ask_deepseek(text):
    if not DEEPSEEK_API_KEY:
        return None
    try:
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            "max_tokens": 300
        }
        response = requests.post(url, json=payload, headers=headers, timeout=25)
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            print(f"DeepSeek error {response.status_code}: {response.text[:300]}")
            return None
    except Exception as e:
        print(f"DeepSeek exception: {e}")
        return None

def enhance_and_translate_promo(raw_text):
    """Takes admin's raw promo text (Amharic or English, any spelling), asks DeepSeek to
    correct spelling/grammar, make it attractive marketing copy, and translate into
    Amharic, English, Tigrinya, and Afan Oromo. Returns dict with all 4, falling back
    to the raw text in all fields if DeepSeek is unavailable."""
    fallback = {"am": raw_text, "en": raw_text, "ti": raw_text, "or": raw_text}
    if not DEEPSEEK_API_KEY:
        return fallback
    try:
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
        prompt = f"""You are a marketing copywriter for a CCTV/electronics business in Ethiopia.
Take this promotional message (it may have spelling/grammar mistakes, in Amharic or English):

\"\"\"{raw_text}\"\"\"

1. Correct any spelling/grammar mistakes.
2. Make it attractive, energetic marketing copy (keep emojis, keep it concise).
3. Translate it into all of: Amharic, English, Tigrinya, Afan Oromo.

Respond with ONLY valid JSON, no markdown fences, no preamble, in this exact shape:
{{"am": "...", "en": "...", "ti": "...", "or": "..."}}"""
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            content = content.strip().strip('`')
            if content.startswith('json'):
                content = content[4:].strip()
            parsed = json.loads(content)
            return {
                "am": parsed.get("am", raw_text),
                "en": parsed.get("en", raw_text),
                "ti": parsed.get("ti", raw_text),
                "or": parsed.get("or", raw_text),
            }
        else:
            print(f"DeepSeek translate error {response.status_code}: {response.text[:300]}")
            return fallback
    except Exception as e:
        print(f"DeepSeek translate exception: {e}")
        return fallback

# ===== ራስ-ሰር ማስታወቂያ ወደ ቻናል መላክ =====
def post_random_promo():
    promos = load_promos()
    if not promos:
        print("No promos to post.")
        return
    promo_text = random.choice(promos)

    reply_markup = {
        'inline_keyboard': [[
            {'text': '💬 ዋጋ ጠይቁ', 'url': f'https://t.me/{BOT_USERNAME}?start=price'}
        ]]
    }
    try:
        requests.post(f"{TELEGRAM_URL}/sendMessage", json={
            'chat_id': CHANNEL_ID,
            'text': promo_text,
            'reply_markup': reply_markup
        })
        print(f"Posted promo to {CHANNEL_ID}")
    except Exception as e:
        print(f"Failed to post promo: {e}")

def schedule_daily_promos():
    """በየቀኑ 5 የተለያዩ የኢትዮጵያ ቀን ሰዓቶች ላይ ራስ-ሰር ማስታወቂያ ይለጥፋል"""
    scheduler = BackgroundScheduler(timezone=ETHIOPIA_TZ)
    # 5 fixed times per day, spread across Ethiopian daytime hours (not late night)
    post_hours = [9, 12, 15, 17, 19]
    for hour in post_hours:
        scheduler.add_job(post_random_promo, 'cron', hour=hour, minute=random.randint(0, 30))
    scheduler.start()
    print("✅ Promo scheduler started.")

# ===== 🛍️ የምርት ካታሎግ Mini App (ለደንበኞች) =====
CATALOG_HTML = """
<!DOCTYPE html>
<html lang="am">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Shalom Technology</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', system-ui, sans-serif; }
    body { background: #0b1219; min-height: 100vh; color: #fff; }
    .app-container { max-width: 420px; width: 100%; margin: 0 auto; min-height: 100vh; background: #17212b; overflow: hidden; padding: 14px; position: relative; }

    .header { text-align: center; padding-bottom: 12px; border-bottom: 1px solid #2b3a4a; margin-bottom: 12px; }
    .header .top-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .header .lang-selector { display: flex; gap: 4px; }
    .header .lang-selector button { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); color: #8aa3b5; padding: 3px 8px; border-radius: 12px; font-size: 10px; cursor: pointer; }
    .header .lang-selector button.active { background: rgba(74,158,255,0.2); border-color: #4a9eff; color: #4a9eff; }
    .header .logo-img { width: 40px; height: 40px; border-radius: 10px; object-fit: cover; box-shadow: 0 2px 10px rgba(0,0,0,0.4); }
    .header h1 { font-size: 18px; font-weight: 700; background: linear-gradient(90deg,#4a9eff,#7ac7ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-top: 4px; }
    .header .sub { font-size: 11px; color: #8aa3b5; }

    .pages { padding: 6px 0 80px; }
    .page { display: none; animation: fadeSlide 0.25s ease; }
    .page.active { display: block; }
    @keyframes fadeSlide { 0% { opacity: 0; transform: translateY(10px); } 100% { opacity: 1; transform: translateY(0); } }
    .page-title { font-size: 15px; font-weight: 600; color: #fff; display: flex; align-items: center; gap: 6px; margin-bottom: 10px; }
    .back-btn { background: rgba(255,255,255,0.08); border: none; color: #fff; font-size: 18px; padding: 2px 12px; border-radius: 30px; cursor: pointer; }

    .menu-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 12px; }
    .menu-btn { border-radius: 14px; padding: 10px 4px; text-align: center; font-size: 9px; font-weight: 500; cursor: pointer; color: #e0edf5; border: none; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
    .menu-btn .icon { font-size: 22px; display: block; margin-bottom: 2px; }
    .menu-btn:nth-child(1){background:linear-gradient(135deg,#2a3a4a,#1a2a3a);}
    .menu-btn:nth-child(2){background:linear-gradient(135deg,#4a2a22,#3a1a12);}
    .menu-btn:nth-child(3){background:linear-gradient(135deg,#4a3a1a,#3a2a0a);}
    .menu-btn:nth-child(4){background:linear-gradient(135deg,#1a4a3a,#0a3a2a);}
    .menu-btn:nth-child(5){background:linear-gradient(135deg,#3a2a5a,#2a1a4a);}
    .menu-btn:nth-child(6){background:linear-gradient(135deg,#4a2a3a,#3a1a2a);}
    .menu-btn:nth-child(7){background:linear-gradient(135deg,#4a3a1a,#3a2a0a);}
    .menu-btn:nth-child(8){background:linear-gradient(135deg,#1a4a3a,#0a3a2a);}
    .menu-btn:nth-child(9){background:linear-gradient(135deg,#2a3a5a,#1a2a4a);}
    .menu-btn:nth-child(10){background:linear-gradient(135deg,#1a4a3a,#0a3a2a);}
    .menu-btn:nth-child(11){background:linear-gradient(135deg,#4a2a1a,#3a1a0a);}
    .menu-btn:nth-child(12){background:linear-gradient(135deg,#2a4a4a,#1a3a3a);}
    .menu-btn:nth-child(13){background:linear-gradient(135deg,#4a4a1a,#3a3a0a);}
    .menu-btn:nth-child(14){background:linear-gradient(135deg,#4a2a2a,#3a1a1a);}
    .menu-btn:nth-child(15){background:linear-gradient(135deg,#1a2a4a,#0a1a3a);}
    .menu-btn:nth-child(16){background:linear-gradient(135deg,#3a2a5a,#2a1a4a);}
    .menu-btn:nth-child(17){background:linear-gradient(135deg,#4a2a3a,#3a1a2a);}

    .section-title { color: #b8a84a; font-size: 13px; font-weight: 600; margin-bottom: 8px; }
    .product-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
    .product-card { background: rgba(255,255,255,0.04); border-radius: 14px; overflow: hidden; border: 1px solid rgba(255,255,255,0.06); }
    .product-card .promo-img { width: 100%; height: 100px; object-fit: cover; background: linear-gradient(135deg,#1a2a3a,#2a3a4a); }
    .product-card .info { padding: 6px 8px; text-align: center; }
    .product-card .name { font-weight: 600; font-size: 11px; color: #b8a84a; }
    .product-card .desc { font-size: 9px; color: #8aa3b5; margin: 2px 0 4px; white-space: pre-line; max-height: 60px; overflow-y: auto; }
    .product-card .ask-btn { width: 100%; padding: 5px; border: none; border-radius: 8px; color: #fff; font-weight: 600; font-size: 10px; cursor: pointer; background: linear-gradient(135deg,#4a3a1a,#3a2a0a); }
    .channel-link { padding: 8px; background: rgba(74,158,255,0.08); border-radius: 12px; text-align: center; border: 1px dashed #4a9eff; margin-bottom: 10px; }
    .channel-link a { color: #4a9eff; font-weight: 600; text-decoration: none; font-size: 12px; }

    .promo-banner { background: linear-gradient(135deg,#4a2a2a,#3a1a1a); border-radius: 12px; padding: 10px 14px; margin-top: 10px; display: flex; align-items: center; gap: 10px; border: 1px solid #4a3a1a; }
    .promo-banner .text { font-size: 12px; color: #c0d8e8; flex: 1; font-weight: 600; }

    .bottom-nav { position: fixed; bottom: 0; left: 50%; transform: translateX(-50%); max-width: 420px; width: 100%; background: rgba(15,26,36,0.96); backdrop-filter: blur(14px); border-top: 1px solid #2b3a4a; display: flex; justify-content: space-around; padding: 8px 0 14px; }
    .nav-item { color: #6a8a9e; font-size: 8px; text-align: center; cursor: pointer; padding: 2px 6px; }
    .nav-item.active { color: #4a9eff; }
    .nav-item .icon { font-size: 16px; display: block; }

    .btn-primary { background: #4a9eff; border: none; border-radius: 30px; padding: 10px; color: #fff; font-weight: 600; font-size: 13px; width: 100%; cursor: pointer; margin-top: 4px; }
    .btn-primary.gold { background: #b8a84a; color: #1a1a2e; }
    .card-box { background: rgba(255,255,255,0.04); border-radius: 12px; padding: 10px; border: 1px solid rgba(255,255,255,0.06); text-align: center; cursor: pointer; }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }
    .input-field { width:100%; padding:10px; margin-bottom:8px; background:rgba(255,255,255,0.05); border:1px solid #2b3a4a; border-radius:10px; color:#fff; font-size:13px; }
    .stat-box { background: rgba(255,255,255,0.04); border-radius: 8px; padding: 6px; text-align: center; }
    .stat-num { font-size: 16px; font-weight: 700; }
    .stat-label { font-size: 7px; color: #8aa3b5; }
    .empty-msg { text-align:center; opacity:0.6; margin-top: 30px; font-size: 12px; }
</style>
</head>
<body>

<div class="app-container">
    <div class="header">
        <div class="top-row">
            <img class="logo-img" src="/static/logo.jpg" />
            <div class="lang-selector" id="langSelector">
                <button class="active" data-lang="am" onclick="switchLanguage('am')">አማ</button>
                <button data-lang="en" onclick="switchLanguage('en')">EN</button>
                <button data-lang="ti" onclick="switchLanguage('ti')">ትግ</button>
                <button data-lang="or" onclick="switchLanguage('or')">ኦሮ</button>
            </div>
        </div>
        <h1 id="mainTitle">Shalom Technology</h1>
        <div class="sub" id="mainSub">✨ የእርስዎ የደህንነት አጋር ✨</div>
    </div>

    <div class="pages" id="pagesContainer">

        <!-- HOME -->
        <div class="page active" id="page-home">
            <div class="menu-grid">
                <div class="menu-btn" onclick="showPage('page-products')"><span class="icon">🛍️</span><span data-key="m1">ምርቶች</span></div>
                <div class="menu-btn" onclick="showPage('page-call')"><span class="icon">📞</span><span data-key="m2">ይደውሉ</span></div>
                <div class="menu-btn" onclick="showPage('page-social')"><span class="icon">🌐</span><span data-key="m3">ማህበራዊ</span></div>
                <div class="menu-btn" onclick="showPage('page-share')"><span class="icon">👥</span><span data-key="m4">ማጋሪያ</span></div>
                <div class="menu-btn" onclick="showPage('page-news')"><span class="icon">📰</span><span data-key="m5">ዜና</span></div>
                <div class="menu-btn" onclick="showPage('page-compare')"><span class="icon">⚖️</span><span data-key="m6">ንጽጽር</span></div>
                <div class="menu-btn" onclick="showPage('page-jobs')"><span class="icon">💼</span><span data-key="m7">ክፍት ስራ</span></div>
                <div class="menu-btn" onclick="showPage('page-discount')"><span class="icon">🎁</span><span data-key="m8">ቅናሽ</span></div>
                <div class="menu-btn" onclick="showPage('page-ai')"><span class="icon">🤖</span><span data-key="m9">ረዳት</span></div>
                <div class="menu-btn" onclick="showPage('page-support')"><span class="icon">🛡️</span><span data-key="m10">ድጋፍ</span></div>
                <div class="menu-btn" onclick="showPage('page-promo')"><span class="icon">📢</span><span data-key="m11">ማስታወቂያ</span></div>
                <div class="menu-btn" onclick="showPage('page-tips')"><span class="icon">💡</span><span data-key="m12">ምክሮች</span></div>
                <div class="menu-btn" onclick="showPage('page-banks')"><span class="icon">🏦</span><span data-key="m13">ባንክ</span></div>
                <div class="menu-btn" onclick="showPage('page-login')"><span class="icon">🔑</span><span data-key="m14">መግቢያ</span></div>
                <div class="menu-btn" onclick="showPage('page-admin')"><span class="icon">⚙️</span><span data-key="m15">አድሚን</span></div>
                <div class="menu-btn" onclick="showPage('page-teamleader')"><span class="icon">👔</span><span data-key="m16">ቲም ሊደር</span></div>
                <div class="menu-btn" onclick="showPage('page-employee')"><span class="icon">👤</span><span data-key="m17">ሰራተኛ</span></div>
            </div>
            <div class="promo-banner">
                <span style="font-size:18px;">🔥</span>
                <span class="text" id="homePromoText">✨ ማስታወቂያ ለማየት 📢 ላይ ይጫኑ</span>
            </div>
            <div style="margin-top:6px; text-align:center; color:#6a8a9e; font-size:9px;">
                📢 ቻናላችን: <span style="color:#4a9eff;">@MarshalomTech</span>
            </div>
        </div>

        <!-- PRODUCTS -->
        <div class="page" id="page-products">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button><span id="pTitle">🛍️ ምርቶች</span></div>
            <div class="product-grid" id="productGrid"><p class="empty-msg">⏳...</p></div>
            <div class="channel-link">📢 <a href="https://t.me/cctvcamera2018" target="_blank" id="channelText">ተጨማሪ ምርቶች ለማየት ቻናላችንን ይቀላቀሉ</a> 📢</div>
        </div>

        <!-- CALL -->
        <div class="page" id="page-call">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>📞 <span id="callTitle">ይደውሉ</span></div>
            <div class="grid2" style="margin-top:6px;">
                <a href="tel:0931556590" class="card-box" style="text-decoration:none; color:inherit;">
                    <div style="font-size:14px; font-weight:700; color:#fff;">0931556590</div>
                    <div style="font-size:9px; color:#8aa3b5;" id="callLabel1">ኢትዮ ቴሌኮም</div>
                </a>
                <a href="tel:+251799556590" class="card-box" style="text-decoration:none; color:inherit;">
                    <div style="font-size:14px; font-weight:700; color:#fff;">+251799556590</div>
                    <div style="font-size:9px; color:#8aa3b5;" id="callLabel2">ሳፋሪኮም</div>
                </a>
                <a href="tel:0914412816" class="card-box" style="text-decoration:none; color:inherit;">
                    <div style="font-size:14px; font-weight:700; color:#fff;">0914412816</div>
                    <div style="font-size:9px; color:#8aa3b5;">ኢትዮ ቴሌኮም</div>
                </a>
                <a href="tel:+251967386958" class="card-box" style="text-decoration:none; color:inherit;">
                    <div style="font-size:14px; font-weight:700; color:#fff;">+251967386958</div>
                    <div style="font-size:9px; color:#8aa3b5;">ሳፋሪኮም</div>
                </a>
            </div>
        </div>

        <!-- SOCIAL -->
        <div class="page" id="page-social">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🌐 <span id="socialTitle">ማህበራዊ</span></div>
            <div class="grid3" style="margin-top:6px;">
                <a href="https://tiktok.com/@shalomtech" target="_blank" class="card-box" style="text-decoration:none; color:inherit;"><span style="font-size:24px; display:block;">🎵</span><span style="font-size:8px; color:#c0d8e8;">TikTok</span></a>
                <a href="https://youtube.com/@ShalomTechnology" target="_blank" class="card-box" style="text-decoration:none; color:inherit;"><span style="font-size:24px; display:block;">▶️</span><span style="font-size:8px; color:#c0d8e8;">YouTube</span></a>
                <a href="https://facebook.com/share/1YEeCpFBgp" target="_blank" class="card-box" style="text-decoration:none; color:inherit;"><span style="font-size:24px; display:block;">📘</span><span style="font-size:8px; color:#c0d8e8;">Facebook</span></a>
                <a href="https://instagram.com/marshalom" target="_blank" class="card-box" style="text-decoration:none; color:inherit;"><span style="font-size:24px; display:block;">📸</span><span style="font-size:8px; color:#c0d8e8;">Instagram</span></a>
                <a href="https://instagram.com/codexafrica" target="_blank" class="card-box" style="text-decoration:none; color:inherit;"><span style="font-size:24px; display:block;">📸</span><span style="font-size:8px; color:#c0d8e8;">CodexAfrica</span></a>
                <a href="https://marshalom.com" target="_blank" class="card-box" style="text-decoration:none; color:inherit;"><span style="font-size:24px; display:block;">🌐</span><span style="font-size:8px; color:#c0d8e8;">marshalom.com</span></a>
            </div>
        </div>

        <!-- SHARE -->
        <div class="page" id="page-share">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>👥 <span id="shareTitle">ማጋሪያ</span></div>
            <div style="background:rgba(74,158,255,0.04); border-radius:12px; padding:10px; margin-top:8px; border:1px solid rgba(74,158,255,0.06); font-size:11px; color:#c0d8e8; line-height:1.6;">
                <div style="color:#b8a84a; font-weight:700; font-size:13px; text-align:center;" id="shareWelcomeTitle">✨ እንኳን ደህና መጡ ወደ Shalom Technology! ✨</div>
                <span id="shareWelcomeText">ይህንን ቦት ለጓደኞችዎ ያጋሩ!</span>
            </div>
            <button class="btn-primary" style="margin-top:10px;" onclick="shareChannel()" id="shareBtn">📤 ቻናላችንን ያጋሩ (Telegram ይምረጡ)</button>
            <div class="grid3" style="margin-top:8px;">
                <a id="shareWhatsapp" target="_blank" class="card-box" style="text-decoration:none; color:inherit;"><span style="font-size:18px; display:block;">💬</span><span style="font-size:7px; color:#c0d8e8;">WhatsApp</span></a>
                <a id="shareFacebook" target="_blank" class="card-box" style="text-decoration:none; color:inherit;"><span style="font-size:18px; display:block;">📘</span><span style="font-size:7px; color:#c0d8e8;">Facebook</span></a>
                <a id="shareTelegram" target="_blank" class="card-box" style="text-decoration:none; color:inherit;"><span style="font-size:18px; display:block;">✈️</span><span style="font-size:7px; color:#c0d8e8;">Telegram</span></a>
            </div>
        </div>

        <!-- NEWS -->
        <div class="page" id="page-news">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>📰 <span id="newsTitle">ዜና</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px 10px; margin-bottom:5px; border-left:3px solid #4a9eff;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;" id="news1_title">📸 አዲስ ካሜራ ፊት ብቻ ሳይሆን የእግር ንዝረትን ይለያል!</div>
                <div style="color:#c0d8e8; font-size:10px; margin-top:2px;" id="news1_desc">የቻይና ኩባንያ አዲስ AI ካሜራ አስገባ — ሰዎችን በእግራቸው እንቅስቃሴ ይለያል! 🦶</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px 10px; margin-bottom:5px; border-left:3px solid #4a9eff;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;" id="news2_title">🚀 በአሜሪካ የሰማይ ላይ ካሜራ ተፈተሸ</div>
                <div style="color:#c0d8e8; font-size:10px; margin-top:2px;" id="news2_desc">ሰዎችን ከ5 ኪሎ ሜትር ርቀት የሚያውቅ ካሜራ ተፈተሸ! 🌍</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px 10px; border-left:3px solid #ff6b6b;">
                <div style="color:#ff6b6b; font-weight:600; font-size:11px;" id="news3_title">😂 አስቂኝ ዜና!</div>
                <div style="color:#c0d8e8; font-size:10px; margin-top:2px;" id="news3_desc">ማርሻሎም ለቦቱ ምስጢር ቁጥር "777" ደብቆታል! 🤫😂</div>
            </div>
        </div>

        <!-- COMPARE -->
        <div class="page" id="page-compare">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>⚖️ <span id="compareTitle">ንጽጽር</span></div>
            <div class="grid2" style="margin-top:6px;">
                <div class="card-box" style="text-align:left; cursor:default;">
                    <div style="color:#b8a84a; font-weight:600; font-size:12px; text-align:center;">CALUS VC9</div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ጥራት</span><span style="color:#fff; float:right;">4MP</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ኔትወርክ</span><span style="color:#fff; float:right;">4G+Solar</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0;"><span style="color:#8aa3b5;">PTZ</span><span style="color:#fff; float:right;">✅ 360°</span></div>
                </div>
                <div class="card-box" style="text-align:left; cursor:default;">
                    <div style="color:#b8a84a; font-weight:600; font-size:12px; text-align:center;">HIKVISION Speed Dome</div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ጥራት</span><span style="color:#fff; float:right;">4MP</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ርቀት</span><span style="color:#fff; float:right;">200m</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0;"><span style="color:#8aa3b5;">PTZ</span><span style="color:#fff; float:right;">✅ 32x</span></div>
                </div>
            </div>
        </div>

        <!-- JOBS -->
        <div class="page" id="page-jobs">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>💼 <span id="jobsTitle">ክፍት ስራ</span></div>
            <div id="jobsList"><p class="empty-msg">⏳...</p></div>
        </div>

        <!-- DISCOUNT -->
        <div class="page" id="page-discount">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🎁 <span id="discountTitle">ቅናሽ</span></div>
            <div id="discountBox" style="background:linear-gradient(135deg,#4a3a1a,#3a2a0a); border-radius:16px; padding:20px 12px; text-align:center; color:#b8a84a; border:1px solid #4a3a1a;">
                <div style="font-size:30px;">🎁</div>
                <div id="discountContent" style="font-size:13px; color:#c0d8e8; margin-top:6px;">⏳...</div>
            </div>
        </div>

        <!-- AI -->
        <div class="page" id="page-ai">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🤖 <span id="aiTitle">ረዳት</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:14px; padding:12px 10px; border:1px solid rgba(255,215,0,0.06);">
                <div style="color:#b8a84a; font-size:14px; font-weight:700; text-align:center;" id="aiBusyTitle">🌟 Shalom Technology AI ረዳት 🌟</div>
                <div style="color:#c0d8e8; font-size:11px; line-height:1.6; margin-top:4px;" id="aiBusyBody">ማንኛውም ጥያቄ ካለዎት ከታች ያለውን ቁልፍ ተጭነው ከ AI ረዳታችን ጋር በቀጥታ ይወያዩ! 🤝✨</div>
                <button class="btn-primary" style="margin-top:6px;" onclick="openAI()" id="aiBtn">🤖 ከ AI ጋር ይወያዩ</button>
            </div>
        </div>

        <!-- SUPPORT -->
        <div class="page" id="page-support">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🛡️ <span id="supportTitle">ድጋፍ</span></div>
            <div style="text-align:center;">
                <div style="font-size:32px;">🛡️</div>
                <p style="color:#c0d8e8; font-size:13px; font-weight:600;" id="supportSub">24/7 ደንበኛ ድጋፍ</p>
                <div class="grid3" style="margin-top:6px;">
                    <a href="tel:0931556590" class="card-box" style="text-decoration:none; color:inherit;">
                        <span style="font-size:28px; display:block;">📞</span>
                        <span style="font-size:9px; color:#c0d8e8;">ስልክ</span>
                        <span style="font-size:8px; color:#8aa3b5;">0931556590</span>
                    </a>
                    <a href="https://wa.me/251799556590" target="_blank" class="card-box" style="text-decoration:none; color:inherit;">
                        <span style="font-size:28px; display:block;">💬</span>
                        <span style="font-size:9px; color:#c0d8e8;">ዋትሳፕ</span>
                        <span style="font-size:8px; color:#8aa3b5;">+251799556590</span>
                    </a>
                    <a href="https://t.me/MarshalomTech" target="_blank" class="card-box" style="text-decoration:none; color:inherit;">
                        <span style="font-size:28px; display:block;">✈️</span>
                        <span style="font-size:9px; color:#c0d8e8;">ቴሌግራም</span>
                        <span style="font-size:8px; color:#8aa3b5;">@MarshalomTech</span>
                    </a>
                </div>
                <a href="tel:0931556590" style="text-decoration:none;"><button class="btn-primary" style="margin-top:6px;" id="supportBtn">📞 ወዲያው ይደውሉ</button></a>
            </div>
        </div>

        <!-- PROMO -->
        <div class="page" id="page-promo">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>📢 <span id="promoTitle">ማስታወቂያ</span></div>
            <div id="promoList"><p class="empty-msg">⏳...</p></div>
        </div>

        <!-- TIPS -->
        <div class="page" id="page-tips">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>💡 <span id="tipsTitle">ምክሮች</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; margin-bottom:4px;">
                <div style="color:#b8a84a; font-size:11px;" id="tip1">💡 ምክር 1</div>
                <div style="color:#c0d8e8; font-size:11px;" id="tip1d">ካሜራ ሲጭኑ የፀሐይ ብርሃን ወደሚያገኝ ቦታ ይጫኑ!</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px;">
                <div style="color:#b8a84a; font-size:11px;" id="tip2">💡 ምክር 2</div>
                <div style="color:#c0d8e8; font-size:11px;" id="tip2d">የካሜራ ስርዓትን በየጊዜው ያሻሽሉ!</div>
            </div>
        </div>

        <!-- BANKS -->
        <div class="page" id="page-banks">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🏦 <span id="banksTitle">ባንክ</span></div>
            <div class="card-box" style="cursor:default;">
                <span style="font-size:28px; display:block;">🏦</span>
                <div style="font-size:12px; color:#c0d8e8; margin-top:6px;" id="banksMsg">የባንክ ዝርዝር ለማግኘት እባክዎ ደውለው ወይም መልእክት ይላኩልን</div>
                <a href="tel:0931556590" style="text-decoration:none;"><button class="btn-primary" style="margin-top:8px;">📞 0931556590</button></a>
            </div>
        </div>

        <!-- LOGIN -->
        <div class="page" id="page-login">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🔑 <span id="loginTitle">መግቢያ</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:16px; padding:16px 12px; border:1px solid rgba(74,158,255,0.1);">
                <div style="text-align:center; font-size:28px; margin-bottom:4px;">🔐</div>
                <div style="color:#c0d8e8; font-size:12px; text-align:center; margin-bottom:6px;" id="loginSub">ለቲም ሊደር እና ሰራተኞች (ባለቤት ራሱ በራስ-ሰር ይታወቃል)</div>
                <input type="text" id="loginUsername" placeholder="Username" class="input-field">
                <input type="password" id="loginPassword" placeholder="Password" class="input-field">
                <button class="btn-primary" onclick="doLogin()" id="loginBtn">🔓 ግባ</button>
                <div id="loginMsg" style="font-size:11px; text-align:center; margin-top:6px; color:#ff6b6b;"></div>
            </div>
        </div>

        <!-- ADMIN -->
        <div class="page" id="page-admin">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>⚙️ <span id="adminTitle">አድሚን</span></div>
            <div id="adminContent"><p class="empty-msg">⏳ በማረጋገጥ ላይ...</p></div>
        </div>

        <!-- TEAM LEADER -->
        <div class="page" id="page-teamleader">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>👔 <span id="tlTitle">ቲም ሊደር</span></div>
            <div id="tlLoginBox">
                <input type="text" id="tlUsername" placeholder="Username" class="input-field">
                <input type="password" id="tlPassword" placeholder="Password" class="input-field">
                <button class="btn-primary" onclick="teamLeaderLogin()">🔓 ግባ</button>
                <div id="tlMsg" style="font-size:11px; text-align:center; margin-top:6px; color:#ff6b6b;"></div>
            </div>
            <div id="tlContent" style="display:none;"></div>
        </div>

        <!-- EMPLOYEE -->
        <div class="page" id="page-employee">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>👤 <span id="empTitle">ሰራተኛ</span></div>
            <div id="empLoginBox">
                <input type="text" id="empUsername" placeholder="Username" class="input-field">
                <input type="password" id="empPassword" placeholder="Password" class="input-field">
                <button class="btn-primary" onclick="employeeLogin()">🔓 ግባ</button>
                <div id="empMsg" style="font-size:11px; text-align:center; margin-top:6px; color:#ff6b6b;"></div>
            </div>
            <div id="empContent" style="display:none;"></div>
        </div>

    </div>

    <div class="bottom-nav">
        <div class="nav-item active" onclick="showPage('page-home')"><span class="icon">🏠</span><span data-key="n1">መነሻ</span></div>
        <div class="nav-item" onclick="showPage('page-products')"><span class="icon">🛍️</span><span data-key="n2">ምርቶች</span></div>
        <div class="nav-item" onclick="showPage('page-ai')"><span class="icon">🤖</span><span data-key="n3">ረዳት</span></div>
        <div class="nav-item" onclick="showPage('page-share')"><span class="icon">👥</span><span data-key="n4">አጋራ</span></div>
        <div class="nav-item" onclick="showPage('page-jobs')"><span class="icon">💼</span><span data-key="n5">ስራ</span></div>
    </div>
</div>

<script>
const tg = window.Telegram.WebApp;
tg.ready(); tg.expand();
const initData = tg.initData;
const tgUser = (tg.initDataUnsafe && tg.initDataUnsafe.user) ? tg.initDataUnsafe.user : {};

let currentLang = 'am';
let allProducts = [];
let teamLeaderCreds = null;

const translations = {
    am: {
        title:'Shalom Technology', sub:'✨ የእርስዎ የደህንነት አጋር ✨',
        m1:'ምርቶች',m2:'ይደውሉ',m3:'ማህበራዊ',m4:'ማጋሪያ',m5:'ዜና',m6:'ንጽጽር',m7:'ክፍት ስራ',m8:'ቅናሽ',
        m9:'ረዳት',m10:'ድጋፍ',m11:'ማስታወቂያ',m12:'ምክሮች',m13:'ባንክ',m14:'መግቢያ',m15:'አድሚን',m16:'ቲም ሊደር',m17:'ሰራተኛ',
        n1:'መነሻ',n2:'ምርቶች',n3:'ረዳት',n4:'አጋራ',n5:'ስራ',
        pTitle:'🛍️ ምርቶች', channelText:'ተጨማሪ ምርቶች ለማየት ቻናላችንን ይቀላቀሉ',
        callTitle:'ይደውሉ', callLabel1:'ኢትዮ ቴሌኮም', callLabel2:'ሳፋሪኮም',
        socialTitle:'ማህበራዊ', shareTitle:'ማጋሪያ',
        shareWelcomeTitle:'✨ እንኳን ደህና መጡ ወደ Shalom Technology! ✨', shareWelcomeText:'ይህንን ቦት ለጓደኞችዎ ያጋሩ!',
        shareBtn:'📤 ቻናላችንን ያጋሩ (Telegram ይምረጡ)',
        newsTitle:'ዜና', compareTitle:'ንጽጽር',
        jobsTitle:'ክፍት ስራ', jobsApply:'📝 አሁን አመልክት', jobsEmpty:'ለጊዜው ክፍት የስራ ቦታ የለም',
        discountTitle:'ቅናሽ', aiTitle:'ረዳት', supportTitle:'ድጋፍ', supportSub:'24/7 ደንበኛ ድጋፍ',
        promoTitle:'ማስታወቂያ', promoEmpty:'ለጊዜው ማስታወቂያ የለም',
        tipsTitle:'ምክሮች', banksTitle:'ባንክ',
        loginTitle:'መግቢያ', loginSub:'ለቲም ሊደር እና ሰራተኞች (ባለቤት ራሱ በራስ-ሰር ይታወቃል)', loginBtn:'🔓 ግባ',
        adminTitle:'አድሚን', tlTitle:'ቲም ሊደር', empTitle:'ሰራተኛ',
        askPrice:'💬 ዋጋ ጠይቁ', askSent:'✅ ጥያቄዎ ተልኳል!',
        phonePlaceholder:'ስልክ ቁጥርዎን ያስገቡ', applyBtn:'📝 አመልክት', applySent:'✅ ማመልከቻዎ ተልኳል!',
        wrongLogin:'❌ የተሳሳተ username ወይም password', mustChangePw:'🔐 መጀመሪያ password ይቀይሩ:',
        setPwBtn:'✅ Password ቀይር', pwChanged:'✅ Password ተቀይሯል!'
    },
    en: {
        title:'Shalom Technology', sub:'✨ Your Security Partner ✨',
        m1:'Products',m2:'Call',m3:'Social',m4:'Share',m5:'News',m6:'Compare',m7:'Jobs',m8:'Discount',
        m9:'Assistant',m10:'Support',m11:'Promo',m12:'Tips',m13:'Banks',m14:'Login',m15:'Admin',m16:'Team Leader',m17:'Employee',
        n1:'Home',n2:'Products',n3:'Assistant',n4:'Share',n5:'Jobs',
        pTitle:'🛍️ Products', channelText:'Join our channel for more products',
        callTitle:'Call', callLabel1:'Ethio Telecom', callLabel2:'Safaricom',
        socialTitle:'Social', shareTitle:'Share',
        shareWelcomeTitle:'✨ Welcome to Shalom Technology! ✨', shareWelcomeText:'Share this bot with your friends!',
        shareBtn:'📤 Share our channel (choose Telegram)',
        newsTitle:'News', compareTitle:'Compare',
        jobsTitle:'Jobs', jobsApply:'📝 Apply Now', jobsEmpty:'No open positions right now',
        discountTitle:'Discount', aiTitle:'Assistant', supportTitle:'Support', supportSub:'24/7 Customer Support',
        promoTitle:'Promo', promoEmpty:'No promotions right now',
        tipsTitle:'Tips', banksTitle:'Banks',
        loginTitle:'Login', loginSub:'For Team Leader & Employees (Owner is auto-detected)', loginBtn:'🔓 Login',
        adminTitle:'Admin', tlTitle:'Team Leader', empTitle:'Employee',
        askPrice:'💬 Ask Price', askSent:'✅ Request sent!',
        phonePlaceholder:'Enter your phone number', applyBtn:'📝 Apply', applySent:'✅ Application sent!',
        wrongLogin:'❌ Wrong username or password', mustChangePw:'🔐 Please set a new password first:',
        setPwBtn:'✅ Change Password', pwChanged:'✅ Password changed!'
    },
    ti: {
        title:'Shalom Technology', sub:'✨ ናይ ሓልዎት ኣጋርኩም ✨',
        m1:'ምርቶች',m2:'ደውሉ',m3:'ማህበራዊ',m4:'ኣጋሩ',m5:'ዜና',m6:'ንጽጽር',m7:'ስራ',m8:'ቅናሽ',
        m9:'ረዳት',m10:'ድጋፍ',m11:'ማስታወቂያ',m12:'ምኽርታት',m13:'ባንክ',m14:'ምእታው',m15:'ኣድሚን',m16:'መራሒ ጉጅለ',m17:'ሰራተኛ',
        n1:'መነሻ',n2:'ምርቶች',n3:'ረዳት',n4:'ኣጋሩ',n5:'ስራ',
        pTitle:'🛍️ ምርቶች', channelText:'ካልኦት ምርትታት ንምርኣይ ቻናልና ተጸንበሩ',
        callTitle:'ደውሉ', callLabel1:'ኢትዮ ተለኮም', callLabel2:'ሳፋሪኮም',
        socialTitle:'ማህበራዊ', shareTitle:'ኣጋሩ',
        shareWelcomeTitle:'✨ ናብ Shalom Technology ብደሓን መጻእኩም! ✨', shareWelcomeText:'ነዚ ቦት ንመሓዙትኩም ኣጋሩ!',
        shareBtn:'📤 ቻናልና ኣጋሩ',
        newsTitle:'ዜና', compareTitle:'ንጽጽር',
        jobsTitle:'ክፍቲ ስራሕ', jobsApply:'📝 ሕጂ ኣመልክቱ', jobsEmpty:'ሕጂ ክፍቲ ቦታ የለን',
        discountTitle:'ቅናሽ', aiTitle:'ረዳት', supportTitle:'ደገፍ', supportSub:'24/7 ደገፍ ዓሚል',
        promoTitle:'ማስታወቂያ', promoEmpty:'ሕጂ ማስታወቂያ የለን',
        tipsTitle:'ምኽርታት', banksTitle:'ባንክ',
        loginTitle:'ምእታው', loginSub:'ንመራሒ ጉጅለን ሰራተኛታትን', loginBtn:'🔓 እቶ',
        adminTitle:'ኣድሚን', tlTitle:'መራሒ ጉጅለ', empTitle:'ሰራተኛ',
        askPrice:'💬 ዋጋ ሕተት', askSent:'✅ ተላኢኹ!',
        phonePlaceholder:'ቁጽሪ ስልኪ ኣእትዉ', applyBtn:'📝 ኣመልክት', applySent:'✅ ማመልከቻ ተላኢኹ!',
        wrongLogin:'❌ ግጉይ username ወይ password', mustChangePw:'🔐 መጀመርታ password ቀይሩ:',
        setPwBtn:'✅ Password ቀይር', pwChanged:'✅ ተቐይሩ!'
    },
    or: {
        title:'Shalom Technology', sub:'✨ Michuu Nageenya Keessanii ✨',
        m1:'Oomishaalee',m2:'Bilbilaa',m3:'Hawaasa',m4:'Qooda',m5:'Oduu',m6:'Madaalii',m7:'Hojii',m8:'Hir\u2019aa',
        m9:'Gargaaraa',m10:'Deggersa',m11:'Beeksisa',m12:'Gorsa',m13:'Baankii',m14:'Seensa',m15:'Admin',m16:'Hoogganaa',m17:'Hojjetaa',
        n1:'Mana',n2:'Oomishaalee',n3:'Gargaaraa',n4:'Qooda',n5:'Hojii',
        pTitle:'🛍️ Oomishaalee', channelText:'Oomisha dabalataaf channel keenya hordofaa',
        callTitle:'Bilbilaa', callLabel1:'Ethio Telecom', callLabel2:'Safaricom',
        socialTitle:'Hawaasa', shareTitle:'Qooda',
        shareWelcomeTitle:'✨ Baga Nagaan Dhuftan Shalom Technology! ✨', shareWelcomeText:'Bot kana hiriyoota keessaniif qoodaa!',
        shareBtn:'📤 Channel keenya qoodaa',
        newsTitle:'Oduu', compareTitle:'Madaalii',
        jobsTitle:'Hojii Banaa', jobsApply:'📝 Amma Iyyadhu', jobsEmpty:'Yeroo ammaa hojiin banaan hin jiru',
        discountTitle:'Hir\u2019aa', aiTitle:'Gargaaraa', supportTitle:'Deggersa', supportSub:'Deggersa Maamilaa 24/7',
        promoTitle:'Beeksisa', promoEmpty:'Yeroo ammaa beeksisni hin jiru',
        tipsTitle:'Gorsa', banksTitle:'Baankii',
        loginTitle:'Seensa', loginSub:'Hoogganaa fi Hojjettootaaf', loginBtn:'🔓 Seeni',
        adminTitle:'Admin', tlTitle:'Hoogganaa', empTitle:'Hojjetaa',
        askPrice:'💬 Gaafii Gatii', askSent:'✅ Ergameera!',
        phonePlaceholder:'Lakkoofsa bilbila keessan galchaa', applyBtn:'📝 Iyyadhu', applySent:'✅ Iyyannoon ergameera!',
        wrongLogin:'❌ username ykn password dogongora', mustChangePw:'🔐 Duraan dursanii password haaraa qopheessaa:',
        setPwBtn:'✅ Password Jijjiiri', pwChanged:'✅ Jijjiirameera!'
    }
};

function switchLanguage(lang) {
    currentLang = lang;
    const t = translations[lang];
    document.querySelectorAll('.lang-selector button').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
    document.getElementById('mainTitle').textContent = t.title;
    document.getElementById('mainSub').textContent = t.sub;
    document.querySelectorAll('[data-key]').forEach(el => {
        const key = el.dataset.key;
        if (t[key]) el.textContent = t[key];
    });
    document.getElementById('pTitle').textContent = t.pTitle;
    document.getElementById('channelText').textContent = t.channelText;
    document.getElementById('callTitle').textContent = t.callTitle;
    document.getElementById('callLabel1').textContent = t.callLabel1;
    document.getElementById('callLabel2').textContent = t.callLabel2;
    document.getElementById('socialTitle').textContent = t.socialTitle;
    document.getElementById('shareTitle').textContent = t.shareTitle;
    document.getElementById('shareWelcomeTitle').textContent = t.shareWelcomeTitle;
    document.getElementById('shareWelcomeText').textContent = t.shareWelcomeText;
    document.getElementById('shareBtn').textContent = t.shareBtn;
    document.getElementById('newsTitle').textContent = t.newsTitle;
    document.getElementById('compareTitle').textContent = t.compareTitle;
    document.getElementById('jobsTitle').textContent = t.jobsTitle;
    document.getElementById('discountTitle').textContent = t.discountTitle;
    document.getElementById('aiTitle').textContent = t.aiTitle;
    document.getElementById('supportTitle').textContent = t.supportTitle;
    document.getElementById('supportSub').textContent = t.supportSub;
    document.getElementById('promoTitle').textContent = t.promoTitle;
    document.getElementById('tipsTitle').textContent = t.tipsTitle;
    document.getElementById('banksTitle').textContent = t.banksTitle;
    document.getElementById('loginTitle').textContent = t.loginTitle;
    document.getElementById('loginSub').textContent = t.loginSub;
    document.getElementById('loginBtn').textContent = t.loginBtn;
    document.getElementById('adminTitle').textContent = t.adminTitle;
    document.getElementById('tlTitle').textContent = t.tlTitle;
    document.getElementById('empTitle').textContent = t.empTitle;
    renderProducts();
    renderPromos();
    renderJobs();
}

function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(pageId);
    if (target) target.classList.add('active');
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    if (pageId === 'page-home') document.querySelector('.nav-item:nth-child(1)').classList.add('active');
    else if (pageId === 'page-products') document.querySelector('.nav-item:nth-child(2)').classList.add('active');
    else if (pageId === 'page-ai') document.querySelector('.nav-item:nth-child(3)').classList.add('active');
    else if (pageId === 'page-share') document.querySelector('.nav-item:nth-child(4)').classList.add('active');
    else if (pageId === 'page-jobs') document.querySelector('.nav-item:nth-child(5)').classList.add('active');
    if (pageId === 'page-admin') loadAdminPage();
}

// ===== PRODUCTS =====
async function loadProducts() {
    const res = await fetch('/api/products');
    allProducts = await res.json();
    renderProducts();
}
function renderProducts() {
    const t = translations[currentLang];
    const el = document.getElementById('productGrid');
    if (!allProducts.length) { el.innerHTML = '<p class="empty-msg">...</p>'; return; }
    el.innerHTML = allProducts.map(p => `
        <div class="product-card">
            <img class="promo-img" src="${p.photo_url || '/static/logo.jpg'}" />
            <div class="info">
                <div class="name">${p.name}</div>
                <div class="desc">${p.description || ''}</div>
                <button class="ask-btn" onclick='askPrice(${p.id}, ${JSON.stringify(p.name)})'>${t.askPrice}</button>
            </div>
        </div>
    `).join('');
}
async function askPrice(productId, productName) {
    const t = translations[currentLang];
    await fetch('/api/ask_price', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({initData, product_id: productId, product_name: productName})
    });
    alert(t.askSent);
}

// ===== JOBS =====
async function loadJobs() {
    const res = await fetch('/api/jobs');
    window._jobs = await res.json();
    renderJobs();
}
function renderJobs() {
    const t = translations[currentLang];
    const el = document.getElementById('jobsList');
    const jobs = window._jobs || [];
    if (!jobs.length) { el.innerHTML = `<p class="empty-msg">${t.jobsEmpty}</p>`; return; }
    el.innerHTML = jobs.map(j => `
        <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; margin-bottom:6px; border-left:4px solid #4a9eff;">
            <h3 style="color:#fff; font-size:12px;">${j.title}</h3>
            <p style="color:#9bb0c0; font-size:10px;">${j.location || ''}</p>
            <p style="color:#c0d8e8; font-size:10px; margin-top:4px;">${j.description || ''}</p>
            <input type="text" id="phone-${j.id}" placeholder="${t.phonePlaceholder}" class="input-field" style="margin-top:6px;">
            <button class="btn-primary" onclick="applyJob(${j.id}, ${JSON.stringify(j.title)})">${t.applyBtn}</button>
        </div>
    `).join('');
}
async function applyJob(jobId, jobTitle) {
    const t = translations[currentLang];
    const phone = document.getElementById('phone-' + jobId).value;
    await fetch('/api/jobs/apply', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({initData, job_id: jobId, job_title: jobTitle, phone})
    });
    alert(t.applySent);
}

// ===== PROMOS =====
async function loadPromos() {
    const res = await fetch('/api/promos');
    window._promos = await res.json();
    renderPromos();
    renderDiscount();
}
function renderPromos() {
    const t = translations[currentLang];
    const el = document.getElementById('promoList');
    const promos = window._promos || [];
    if (!promos.length) { el.innerHTML = `<p class="empty-msg">${t.promoEmpty}</p>`; return; }
    el.innerHTML = promos.map(p => `
        <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; border-left:4px solid #4a9eff; margin-bottom:4px;">
            <div style="color:#c0d8e8; font-size:11px;">${p[currentLang] || p.am}</div>
        </div>
    `).join('');
    const homeText = document.getElementById('homePromoText');
    if (promos.length && homeText) homeText.textContent = (promos[0][currentLang] || promos[0].am);
}
function renderDiscount() {
    const promos = window._promos || [];
    const el = document.getElementById('discountContent');
    if (promos.length) {
        el.textContent = promos[0][currentLang] || promos[0].am;
    } else {
        el.textContent = currentLang === 'en' ? 'No active discount right now' : 'ለጊዜው ንቁ ቅናሽ የለም';
    }
}

// ===== SHARE =====
function shareChannel() {
    const channelUrl = 'https://t.me/MarshalomTech';
    tg.openTelegramLink('https://t.me/share/url?url=' + encodeURIComponent(channelUrl) + '&text=' + encodeURIComponent('Shalom Technology - CCTV and Electronics'));
}
document.getElementById('shareWhatsapp') && (document.getElementById('shareWhatsapp').href = 'https://wa.me/?text=' + encodeURIComponent('Check out Shalom Technology: https://t.me/MarshalomTech'));
document.getElementById('shareFacebook') && (document.getElementById('shareFacebook').href = 'https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent('https://t.me/MarshalomTech'));
document.getElementById('shareTelegram') && (document.getElementById('shareTelegram').href = 'https://t.me/share/url?url=' + encodeURIComponent('https://t.me/MarshalomTech'));

// ===== AI =====
function openAI() {
    tg.openTelegramLink('https://t.me/MarshalomSupportBot');
}

// ===== LOGIN (routes to team leader or employee page based on role) =====
async function doLogin() {
    const t = translations[currentLang];
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const res = await fetch('/api/employee/login', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password})
    });
    const data = await res.json();
    if (!data.ok) {
        document.getElementById('loginMsg').textContent = t.wrongLogin;
        return;
    }
    if (data.profile.role === 'team_leader') {
        teamLeaderCreds = {tl_username: username, tl_password: password};
        showPage('page-teamleader');
        renderTeamLeaderPanel(data.profile, username, password);
    } else {
        showPage('page-employee');
        renderEmployeePanel(data.profile, username, password);
    }
}

// ===== EMPLOYEE direct login (from Employee menu page) =====
async function employeeLogin() {
    const t = translations[currentLang];
    const username = document.getElementById('empUsername').value;
    const password = document.getElementById('empPassword').value;
    const res = await fetch('/api/employee/login', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password})
    });
    const data = await res.json();
    if (!data.ok) { document.getElementById('empMsg').textContent = t.wrongLogin; return; }
    if (data.profile.role === 'team_leader') {
        alert(currentLang === 'en' ? 'This is a Team Leader account - please use the Team Leader menu.' : 'ይህ የቲም ሊደር አካውንት ነው - እባክዎ የቲም ሊደር ምናሌ ይጠቀሙ።');
        return;
    }
    renderEmployeePanel(data.profile, username, password);
}

function renderEmployeePanel(profile, username, password) {
    const t = translations[currentLang];
    document.getElementById('empLoginBox').style.display = 'none';
    const el = document.getElementById('empContent');
    el.style.display = 'block';

    if (profile.must_change_password) {
        el.innerHTML = `
            <div style="background:rgba(255,255,255,0.03); border-radius:14px; padding:14px; text-align:center;">
                <div style="font-size:28px;">🔐</div>
                <p style="color:#ffb84a; font-size:12px; margin:6px 0;">${t.mustChangePw}</p>
                <input type="password" id="newPwInput" placeholder="New password" class="input-field">
                <button class="btn-primary" onclick="changeEmpPassword('${username}','${password}')">${t.setPwBtn}</button>
                <div id="pwMsg" style="font-size:11px; margin-top:6px; color:#4aff8a;"></div>
            </div>
        `;
        return;
    }

    el.innerHTML = `
        <div style="background:rgba(255,255,255,0.04); border-radius:14px; padding:14px;">
            <div style="text-align:center; font-size:32px;">👤</div>
            <div style="text-align:center; color:#fff; font-weight:700; font-size:14px;">${profile.full_name}</div>
            <div style="text-align:center; color:#8aa3b5; font-size:11px; margin-bottom:8px;">${profile.position}</div>
            <div style="font-size:11px; color:#c0d8e8; line-height:1.8;">
                <b>💰 ደመወዝ:</b> ${profile.salary || '-'}<br>
                <b>🎁 ቦነስ:</b><br>${(profile.bonus || 'የለም').replace(/\\n/g,'<br>')}<br>
                <b>⚠️ ማስጠንቀቂያ:</b><br>${(profile.warnings || 'የለም').replace(/\\n/g,'<br>')}<br>
                <b>📋 ስራዎች:</b><br>${(profile.tasks || 'የለም').replace(/\\n/g,'<br>')}
            </div>
        </div>
    `;
}

async function changeEmpPassword(username, oldPassword) {
    const newPassword = document.getElementById('newPwInput').value;
    if (!newPassword) return;
    const res = await fetch('/api/employee/set_password', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({username, old_password: oldPassword, new_password: newPassword})
    });
    const data = await res.json();
    if (data.ok) {
        document.getElementById('pwMsg').textContent = translations[currentLang].pwChanged;
        setTimeout(() => employeeLoginRetry(username, newPassword), 1000);
    }
}
async function employeeLoginRetry(username, password) {
    const res = await fetch('/api/employee/login', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password})
    });
    const data = await res.json();
    if (data.ok) renderEmployeePanel(data.profile, username, password);
}

// ===== TEAM LEADER =====
async function teamLeaderLogin() {
    const t = translations[currentLang];
    const username = document.getElementById('tlUsername').value;
    const password = document.getElementById('tlPassword').value;
    const res = await fetch('/api/employee/login', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password})
    });
    const data = await res.json();
    if (!data.ok || data.profile.role !== 'team_leader') {
        document.getElementById('tlMsg').textContent = t.wrongLogin;
        return;
    }
    teamLeaderCreds = {tl_username: username, tl_password: password};
    renderTeamLeaderPanel(data.profile, username, password);
}

async function renderTeamLeaderPanel(profile) {
    document.getElementById('tlLoginBox').style.display = 'none';
    const el = document.getElementById('tlContent');
    el.style.display = 'block';
    el.innerHTML = `<p class="empty-msg">⏳...</p>`;

    const res = await fetch('/api/team/employees', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(teamLeaderCreds)
    });
    const employees = await res.json();

    el.innerHTML = `
        <div style="text-align:center; margin-bottom:10px;">
            <div style="font-size:28px;">👔</div>
            <div style="color:#fff; font-weight:700;">${profile.full_name}</div>
            <div style="color:#8aa3b5; font-size:11px;">🌟 ቲም ሊደር</div>
        </div>
        <div id="tlEmployeeList"></div>
    `;
    const listEl = document.getElementById('tlEmployeeList');
    listEl.innerHTML = (employees || []).map(e => `
        <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; margin-bottom:6px;">
            <b style="color:#fff; font-size:12px;">${e.full_name}</b> <span style="color:#8aa3b5; font-size:10px;">(${e.position})</span>
            <div style="display:flex; gap:4px; margin-top:6px;">
                <button style="flex:1; font-size:9px; padding:5px; border:none; border-radius:6px; background:#2b3a4a; color:#fff;" onclick="tlResetPassword('${e.username}')">🔐 Reset</button>
                <button style="flex:1; font-size:9px; padding:5px; border:none; border-radius:6px; background:#2b3a4a; color:#fff;" onclick="tlAssignTask('${e.username}')">📋 Task</button>
                <button style="flex:1; font-size:9px; padding:5px; border:none; border-radius:6px; background:#2b3a4a; color:#fff;" onclick="tlGiveBonus('${e.username}')">🎁 Bonus</button>
            </div>
        </div>
    `).join('') || '<p class="empty-msg">ምንም ሰራተኛ የለም</p>';
}

async function tlResetPassword(username) {
    const res = await fetch('/api/team/reset_password', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({...teamLeaderCreds, username})
    });
    const data = await res.json();
    if (data.ok) alert('✅ Temp password: ' + data.temp_password);
}
async function tlAssignTask(username) {
    const task = prompt('📋 New task:');
    if (!task) return;
    await fetch('/api/team/update', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({...teamLeaderCreds, username, field: 'tasks', value: task})
    });
    alert('✅ Task assigned!');
}
async function tlGiveBonus(username) {
    const bonus = prompt('🎁 Bonus amount:');
    if (!bonus) return;
    await fetch('/api/team/update', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({...teamLeaderCreds, username, field: 'bonus', value: bonus})
    });
    alert('✅ Bonus added!');
}

// ===== ADMIN (auto-detected via Telegram identity, no manual login) =====
async function loadAdminPage() {
    const el = document.getElementById('adminContent');
    const verifyRes = await fetch('/api/admin/verify', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({initData})
    });
    const verify = await verifyRes.json();
    if (!verify.ok) {
        el.innerHTML = '<p class="empty-msg">🚫 ተደራሽነት የለዎትም (የባለቤት አካውንት ብቻ)</p>';
        return;
    }
    const [statsRes, productsRes, customersRes, jobsRes] = await Promise.all([
        fetch('/api/admin/stats', {headers:{'X-Init-Data': initData}}),
        fetch('/api/products'),
        fetch('/api/admin/customers', {headers:{'X-Init-Data': initData}}),
        fetch('/api/jobs')
    ]);
    const stats = await statsRes.json();
    const products = await productsRes.json();
    const customers = await customersRes.json();
    const jobs = await jobsRes.json();

    el.innerHTML = `
        <div class="grid2" style="margin-bottom:10px;">
            <div class="stat-box"><div class="stat-num">${stats.customers}</div><div class="stat-label">👥 ደንበኞች</div></div>
            <div class="stat-box"><div class="stat-num">${stats.messages}</div><div class="stat-label">💬 መልእክቶች</div></div>
            <div class="stat-box"><div class="stat-num">${stats.price_inquiries}</div><div class="stat-label">💰 የዋጋ ጥያቄ</div></div>
            <div class="stat-box"><div class="stat-num">${stats.products}</div><div class="stat-label">🛍️ ምርቶች</div></div>
        </div>
        <div class="section-title">🛍️ ምርት ጨምር</div>
        <input type="text" id="newProdName" placeholder="የምርት ስም" class="input-field">
        <input type="text" id="newProdCat" placeholder="ምድብ (CCTV/ኤሌክትሮኒክስ)" class="input-field">
        <textarea id="newProdDesc" placeholder="መግለጫ" class="input-field" rows="2"></textarea>
        <input type="text" id="newProdLink" placeholder="🔗 የፎቶ ሊንክ (አማራጭ)" class="input-field">
        <div style="text-align:center; color:#8aa3b5; font-size:10px; margin:4px 0;">-- ወይም --</div>
        <input type="file" id="newProdFile" accept="image/*" class="input-field" style="padding:6px;">
        <button class="btn-primary gold" onclick="adminAddProduct()">➕ ምርት ጨምር</button>
        <div id="adminProdList" style="margin-top:8px;">
            ${products.map(p => `
                <div style="background:rgba(255,255,255,0.03); border-radius:8px; padding:6px 8px; margin-bottom:4px; font-size:11px; display:flex; justify-content:space-between; align-items:center;">
                    <span>${p.name} (${p.category})</span>
                    <span style="color:#ff6b6b; cursor:pointer;" onclick="adminDeleteProduct(${p.id})">🗑️</span>
                </div>
            `).join('')}
        </div>
        <div class="section-title" style="margin-top:14px;">💼 ስራ ጨምር</div>
        <input type="text" id="newJobTitle" placeholder="የስራ ርዕስ" class="input-field">
        <input type="text" id="newJobLoc" placeholder="ቦታ" class="input-field">
        <textarea id="newJobDesc" placeholder="መግለጫ" class="input-field" rows="2"></textarea>
        <button class="btn-primary gold" onclick="adminAddJob()">➕ ስራ ጨምር</button>
        <div id="adminJobList" style="margin-top:8px;">
            ${jobs.map(j => `
                <div style="background:rgba(255,255,255,0.03); border-radius:8px; padding:6px 8px; margin-bottom:4px; font-size:11px; display:flex; justify-content:space-between; align-items:center;">
                    <span>${j.title}</span>
                    <span style="color:#ff6b6b; cursor:pointer;" onclick="adminDeleteJob(${j.id})">🗑️</span>
                </div>
            `).join('')}
        </div>
        <div class="section-title" style="margin-top:14px;">👥 ደንበኞች (የቅርብ ጊዜ)</div>
        <div>
            ${customers.slice(0,10).map(c => `
                <div style="background:rgba(255,255,255,0.03); border-radius:8px; padding:6px 8px; margin-bottom:4px; font-size:10px;">
                    👤 ${c.name || 'ስም የለም'} (@${c.username || 'የለም'}) - 💬 ${c.message_count}
                </div>
            `).join('')}
        </div>
    `;
}

async function adminAddProduct() {
    const name = document.getElementById('newProdName').value;
    const category = document.getElementById('newProdCat').value;
    const description = document.getElementById('newProdDesc').value;
    const linkUrl = document.getElementById('newProdLink').value;
    const fileInput = document.getElementById('newProdFile');
    if (!name || !category) { alert('ስም እና ምድብ ያስፈልጋል'); return; }

    let photo_url = linkUrl;
    if (fileInput.files && fileInput.files[0]) {
        photo_url = await fileToBase64(fileInput.files[0]);
    }
    await fetch('/api/admin/products', {
        method:'POST', headers:{'Content-Type':'application/json','X-Init-Data': initData},
        body: JSON.stringify({name, category, description, photo_url})
    });
    loadAdminPage();
    loadProducts();
}
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}
async function adminDeleteProduct(id) {
    await fetch('/api/admin/products/'+id, {method:'DELETE', headers:{'X-Init-Data': initData}});
    loadAdminPage();
    loadProducts();
}
async function adminAddJob() {
    const title = document.getElementById('newJobTitle').value;
    const location = document.getElementById('newJobLoc').value;
    const description = document.getElementById('newJobDesc').value;
    if (!title) { alert('የስራ ርዕስ ያስፈልጋል'); return; }
    await fetch('/api/admin/jobs', {
        method:'POST', headers:{'Content-Type':'application/json','X-Init-Data': initData},
        body: JSON.stringify({title, location, description})
    });
    loadAdminPage();
    loadJobs();
}
async function adminDeleteJob(id) {
    await fetch('/api/admin/jobs/'+id, {method:'DELETE', headers:{'X-Init-Data': initData}});
    loadAdminPage();
    loadJobs();
}

// ===== INIT =====
loadProducts();
loadJobs();
loadPromos();
if (window.location.hash) {
    const targetPage = window.location.hash.replace('#', '');
    if (document.getElementById(targetPage)) showPage(targetPage);
}
</script>
</body>
</html>

"""

@app.route('/webapp')
def webapp_catalog():
    return render_template_string(CATALOG_HTML)

@app.route('/api/products')
def api_products():
    category = request.args.get('category')
    return jsonify(get_products(category))

@app.route('/api/promos')
def api_promos():
    return jsonify(get_promos_multilang())

@app.route('/api/jobs')
def api_jobs():
    return jsonify(get_jobs())

@app.route('/api/jobs/apply', methods=['POST'])
def api_jobs_apply():
    body = request.get_json(silent=True) or {}
    user = verify_telegram_webapp_data(body.get('initData', ''))
    job_id = body.get('job_id')
    job_title = body.get('job_title', 'ያልታወቀ ስራ')
    phone = body.get('phone', '')
    name = user.get('first_name', '') if user else body.get('name', 'ስም የለም')
    username = user.get('username', '') if user else ''
    user_id = user.get('id') if user else None
    add_job_application(job_id, job_title, user_id, name, username, phone)
    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        'chat_id': OWNER_CHAT_ID,
        'text': f"💼 አዲስ የስራ ማመልከቻ!\nስራ: {job_title}\nስም: {name} (@{username or 'የለም'})\nስልክ: {phone}\nመታወቂያ: {user_id}"
    })
    return jsonify({"ok": True})

@app.route('/api/ask_price', methods=['POST'])
def api_ask_price():
    body = request.get_json(silent=True) or {}
    user = verify_telegram_webapp_data(body.get('initData', ''))
    product_name = body.get('product_name', 'ያልታወቀ ምርት')
    if not user:
        return jsonify({"ok": False, "error": "verification failed"}), 403
    user_id = user.get('id')
    name = (user.get('first_name', '') + ' ' + user.get('last_name', '')).strip()
    username = user.get('username', '')
    upsert_customer(user_id, name, username)
    log_price_inquiry(user_id, name, username, product_name)
    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        'chat_id': OWNER_CHAT_ID,
        'text': f"💰 የዋጋ ጥያቄ (ከካታሎግ)!\nምርት: {product_name}\nስም: {name} (@{username or 'የለም'})\nመታወቂያ: {user_id}\n🔗 tg://user?id={user_id}"
    })
    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        'chat_id': user_id,
        'text': f'✅ ስለ "{product_name}" ዋጋ ጥያቄዎ ደርሶናል! በቅርቡ ምላሽ ያገኛሉ። 🙏'
    })
    return jsonify({"ok": True})

@app.route('/api/employee/login', methods=['POST'])
def api_employee_login():
    body = request.get_json(silent=True) or {}
    emp = get_employee_by_credentials(body.get('username', '').strip(), body.get('password', '').strip())
    if not emp:
        return jsonify({"ok": False, "error": "invalid credentials"}), 401
    return jsonify({"ok": True, "profile": emp})

@app.route('/api/employee/set_password', methods=['POST'])
def api_employee_set_password():
    body = request.get_json(silent=True) or {}
    emp = get_employee_by_credentials(body.get('username', '').strip(), body.get('old_password', '').strip())
    if not emp:
        return jsonify({"ok": False, "error": "invalid credentials"}), 401
    new_password = body.get('new_password', '').strip()
    if not new_password:
        return jsonify({"ok": False, "error": "empty password"}), 400
    set_employee_password(body.get('username').strip(), new_password, must_change=False)
    return jsonify({"ok": True})

@app.route('/api/team/employees', methods=['POST'])
def api_team_employees():
    body = request.get_json(silent=True) or {}
    if not is_authorized_manager(body):
        return jsonify({"error": "forbidden"}), 403
    return jsonify(list_employees())

@app.route('/api/team/update', methods=['POST'])
def api_team_update():
    body = request.get_json(silent=True) or {}
    if not is_authorized_manager(body):
        return jsonify({"error": "forbidden"}), 403
    username = body.get('username')
    field = body.get('field')
    value = body.get('value')
    if field not in ('bonus', 'warnings', 'tasks'):
        return jsonify({"error": "invalid field"}), 400
    update_employee_field(username, field, value, append=True)
    return jsonify({"ok": True})

@app.route('/api/team/reset_password', methods=['POST'])
def api_team_reset_password():
    body = request.get_json(silent=True) or {}
    if not is_authorized_manager(body):
        return jsonify({"error": "forbidden"}), 403
    username = body.get('username')
    emp = get_employee_by_username(username)
    if not emp:
        return jsonify({"error": "not found"}), 404
    temp_pw = generate_temp_password()
    set_employee_password(username, temp_pw, must_change=True)
    if emp.get('telegram_chat_id'):
        requests.post(f"{TELEGRAM_URL}/sendMessage", json={
            'chat_id': emp['telegram_chat_id'],
            'text': f"🔐 password ዎ ዳግም ተጀምሯል። ጊዜያዊ password: {temp_pw}"
        })
    return jsonify({"ok": True, "temp_password": temp_pw})

# ===== ⚙️ Admin Dashboard Mini App (ለባለቤት ብቻ) =====
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="am">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin Dashboard</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, sans-serif; background: #17212b; color: #fff; padding: 12px; }
  h1 { font-size: 18px; margin-bottom: 12px; }
  .tabs { display: flex; gap: 6px; margin-bottom: 14px; }
  .tab { flex:1; padding: 8px; text-align:center; background:#2b3a4a; border-radius:8px; font-size:12px; }
  .tab.active { background:#4a9eff; }
  .stats-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:16px; }
  .stat-card { background:#232e3c; border-radius:10px; padding:12px; text-align:center; }
  .stat-num { font-size:22px; font-weight:700; }
  .stat-label { font-size:11px; opacity:0.7; }
  .section { display:none; }
  .section.active { display:block; }
  input, textarea { width:100%; padding:8px; margin-bottom:8px; border-radius:6px; border:none; background:#2b3a4a; color:#fff; font-size:13px; }
  button.primary { width:100%; padding:10px; background:#4a9eff; color:#fff; border:none; border-radius:8px; font-size:14px; margin-bottom:16px; }
  .list-item { background:#232e3c; padding:10px; border-radius:8px; margin-bottom:8px; font-size:12px; }
  .del-btn { color:#ff5555; float:right; }
  .denied { text-align:center; margin-top:60px; opacity:0.7; }
</style>
</head>
<body>
<div id="app"><p class="denied">🔒 በማረጋገጥ ላይ...</p></div>

<script>
const tg = window.Telegram.WebApp;
tg.ready(); tg.expand();
const initData = tg.initData;

async function init() {
  const verifyRes = await fetch('/api/admin/verify', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({initData})
  });
  const verify = await verifyRes.json();
  if (!verify.ok) {
    document.getElementById('app').innerHTML = '<p class="denied">🚫 ተደራሽነት የለዎትም</p>';
    return;
  }
  render();
}

function render() {
  document.getElementById('app').innerHTML = `
    <h1><img src="/static/logo.jpg" style="width:24px;height:24px;border-radius:6px;vertical-align:middle;margin-right:6px;">⚙️ Admin Dashboard</h1>
    <div class="tabs">
      <div class="tab active" onclick="showTab('stats')">📈 ስታት</div>
      <div class="tab" onclick="showTab('products')">🛍️ ምርቶች</div>
      <div class="tab" onclick="showTab('customers')">👥 ደንበኞች</div>
    </div>
    <div id="stats" class="section active"></div>
    <div id="products" class="section"></div>
    <div id="customers" class="section"></div>
  `;
  loadStats(); loadProducts(); loadCustomers();
}

function showTab(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  event.target.classList.add('active');
}

async function loadStats() {
  const res = await fetch('/api/admin/stats', {headers:{'X-Init-Data': initData}});
  const s = await res.json();
  document.getElementById('stats').innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-num">${s.customers}</div><div class="stat-label">👥 ደንበኞች</div></div>
      <div class="stat-card"><div class="stat-num">${s.messages}</div><div class="stat-label">💬 መልእክቶች</div></div>
      <div class="stat-card"><div class="stat-num">${s.price_inquiries}</div><div class="stat-label">💰 የዋጋ ጥያቄ</div></div>
      <div class="stat-card"><div class="stat-num">${s.products}</div><div class="stat-label">🛍️ ምርቶች</div></div>
      <div class="stat-card"><div class="stat-num">${s.promos}</div><div class="stat-label">📢 ማስታወቂያ</div></div>
    </div>
  `;
}

async function loadProducts() {
  const res = await fetch('/api/products');
  const products = await res.json();
  const el = document.getElementById('products');
  el.innerHTML = `
    <input id="p-name" placeholder="የምርት ስም" />
    <input id="p-cat" placeholder="ምድብ (ለምሳሌ CCTV)" />
    <textarea id="p-desc" placeholder="መግለጫ"></textarea>
    <input id="p-photo" placeholder="የፎቶ ሊንክ (URL)" />
    <button class="primary" onclick="addProduct()">➕ ምርት ጨምር</button>
    ${products.map(p => `
      <div class="list-item">
        <b>${p.name}</b> (${p.category})<br>${p.description||''}
        <span class="del-btn" onclick="delProduct(${p.id})">🗑️ ሰርዝ</span>
      </div>
    `).join('')}
  `;
}

async function addProduct() {
  const name = document.getElementById('p-name').value;
  const category = document.getElementById('p-cat').value;
  const description = document.getElementById('p-desc').value;
  const photo_url = document.getElementById('p-photo').value;
  if (!name || !category) { alert('ስም እና ምድብ ያስፈልጋል'); return; }
  await fetch('/api/admin/products', {
    method:'POST', headers:{'Content-Type':'application/json','X-Init-Data': initData},
    body: JSON.stringify({name, category, description, photo_url})
  });
  loadProducts();
}

async function delProduct(id) {
  await fetch('/api/admin/products/'+id, {method:'DELETE', headers:{'X-Init-Data': initData}});
  loadProducts();
}

async function loadCustomers() {
  const res = await fetch('/api/admin/customers', {headers:{'X-Init-Data': initData}});
  const customers = await res.json();
  document.getElementById('customers').innerHTML = customers.map(c => `
    <div class="list-item">
      👤 ${c.name || 'ስም የለም'} (@${c.username || 'የለም'})<br>
      🆔 ${c.user_id} | 💬 ${c.message_count} መልእክት<br>
      🕐 ${c.last_seen}
    </div>
  `).join('') || '<p class="denied">ምንም ደንበኛ የለም</p>';
}

init();
</script>
</body>
</html>
"""

@app.route('/admin')
def admin_dashboard():
    return render_template_string(ADMIN_HTML)

def require_admin():
    """Verifies the X-Init-Data header belongs to the owner OR a password-authenticated admin session."""
    init_data = request.headers.get('X-Init-Data', '')
    user = verify_telegram_webapp_data(init_data)
    if not user:
        return False
    return is_admin_chat(user.get('id'))

def is_authorized_manager(body):
    """Authorizes admin (via Telegram initData) OR a team_leader (via username+password in body)."""
    init_data = request.headers.get('X-Init-Data', '')
    user = verify_telegram_webapp_data(init_data)
    if user and is_admin_chat(user.get('id')):
        return True
    tl_username = body.get('tl_username')
    tl_password = body.get('tl_password')
    if tl_username and tl_password:
        emp = get_employee_by_credentials(tl_username.strip(), tl_password.strip())
        if emp and emp.get('role') == 'team_leader':
            return True
    return False

@app.route('/api/admin/jobs', methods=['POST'])
def api_admin_add_job():
    if not require_admin():
        return jsonify({"error": "forbidden"}), 403
    body = request.get_json(silent=True) or {}
    new_id = add_job(body.get('title'), body.get('description'), body.get('location'))
    return jsonify({"ok": True, "id": new_id})

@app.route('/api/admin/jobs/<int:job_id>', methods=['DELETE'])
def api_admin_delete_job(job_id):
    if not require_admin():
        return jsonify({"error": "forbidden"}), 403
    delete_job(job_id)
    return jsonify({"ok": True})

@app.route('/api/admin/verify', methods=['POST'])
def api_admin_verify():
    body = request.get_json(silent=True) or {}
    user = verify_telegram_webapp_data(body.get('initData', ''))
    if user and is_admin_chat(user.get('id')):
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 403

@app.route('/api/admin/stats')
def api_admin_stats():
    if not require_admin():
        return jsonify({"error": "forbidden"}), 403
    return jsonify(get_stats())

@app.route('/api/admin/customers')
def api_admin_customers():
    if not require_admin():
        return jsonify({"error": "forbidden"}), 403
    return jsonify(get_customers_list())

@app.route('/api/admin/products', methods=['POST'])
def api_admin_add_product():
    if not require_admin():
        return jsonify({"error": "forbidden"}), 403
    body = request.get_json(silent=True) or {}
    new_id = add_product(body.get('name'), body.get('category'), body.get('description'), body.get('photo_url'))
    return jsonify({"ok": True, "id": new_id})

@app.route('/api/admin/products/<int:product_id>', methods=['DELETE'])
def api_admin_delete_product(product_id):
    if not require_admin():
        return jsonify({"error": "forbidden"}), 403
    delete_product(product_id)
    return jsonify({"ok": True})

# ===== ዋና ሃንድለር =====
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return "Marshalom Bot is running! 🤖"

    if not TELEGRAM_TOKEN:
        return "TELEGRAM_TOKEN not set", 500

    try:
        data = request.get_json(silent=True)
        if not data or 'message' not in data:
            return "OK"

        msg = data['message']
        chat_id = msg['chat']['id']
        user = msg.get('from', {})
        text = msg.get('text', '')

        # Customer info
        name = user.get('first_name', '')
        if user.get('last_name'):
            name += ' ' + user['last_name']
        username = user.get('username', '')
        user_id = user.get('id', '')

        info = f"""👤 አዲስ መልእክት!
ስም: {name}
የተጠቃሚ ስም: @{username if username else 'የለም'}
መታወቂያ: {user_id}
📝: {text}
🔗: tg://user?id={user_id}"""

        url = f"{TELEGRAM_URL}/sendMessage"

        # Track this customer for the admin dashboard
        upsert_customer(user_id, name, username)

        # ===== Data sent from the Mini App (e.g. "ask price" button tapped) =====
        if 'web_app_data' in msg:
            try:
                wa_data = json.loads(msg['web_app_data'].get('data', '{}'))
            except Exception:
                wa_data = {}
            if wa_data.get('action') == 'ask_price':
                product_name = wa_data.get('product_name', 'ያልታወቀ ምርት')
                log_price_inquiry(user_id, name, username)
                requests.post(url, json={
                    'chat_id': chat_id,
                    'text': f'✅ ስለ "{product_name}" ዋጋ ጥያቄዎ ደርሶናል! በቅርቡ ምላሽ ያገኛሉ። 🙏'
                })
                requests.post(url, json={
                    'chat_id': OWNER_CHAT_ID,
                    'text': f"💰 የዋጋ ጥያቄ (ከካታሎግ)!\nምርት: {product_name}\n\n{info}"
                })
            return "OK"

        # ===== የይለፍ ቃል ማረጋገጫ ትዕዛዞች (ከየትኛውም መሳሪያ/አካውንት ይሰራል) =====

        # /admin <password> - full admin access from ANY telegram account/device
        if text.startswith('/admin'):
            parts = text.split(' ', 1)
            if len(parts) == 2:
                # password provided - try to authenticate
                entered = parts[1].strip()
                if (ADMIN_PASSWORD and entered == ADMIN_PASSWORD) or (ADMIN_PASSWORD_2 and entered == ADMIN_PASSWORD_2):
                    set_session(chat_id, 'admin')
                    requests.post(url, json={'chat_id': chat_id, 'text': '✅ የአድሚን መዳረሻ ተፈቅዷል! /admin ብለው ዳሽቦርድ ይክፈቱ።'})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': '❌ የተሳሳተ የይለፍ ቃል።'})
                return "OK"
            elif is_admin_chat(chat_id):
                # already authenticated (owner or valid session) - open dashboard
                send_with_webapp_button(chat_id, '⚙️ የአድሚን ዳሽቦርድ', '⚙️ ዳሽቦርድ ክፈት', '/webapp#page-admin')
                return "OK"
            else:
                requests.post(url, json={'chat_id': chat_id, 'text': '🔒 እባክዎ የይለፍ ቃል ያስገቡ፡ /admin የይለፍ_ቃል'})
                return "OK"

        # /technical <password> - limited technical access
        if text.startswith('/technical'):
            parts = text.split(' ', 1)
            if len(parts) == 2:
                if TECHNICAL_PASSWORD and parts[1].strip() == TECHNICAL_PASSWORD:
                    set_session(chat_id, 'technical')
                    requests.post(url, json={'chat_id': chat_id, 'text': '✅ የቴክኒክ መዳረሻ ተፈቅዷል (የተወሰነ)።'})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': '❌ የተሳሳተ የይለፍ ቃል።'})
                return "OK"
            elif is_technical_chat(chat_id):
                stats = get_stats()
                requests.post(url, json={'chat_id': chat_id, 'text': f"🔧 የስርዓት ሁኔታ:\n📦 ማስታወቂያ: {stats['promos']}\n🛍️ ምርቶች: {stats['products']}\n👥 ደንበኞች: {stats['customers']}"})
                return "OK"
            else:
                requests.post(url, json={'chat_id': chat_id, 'text': '🔒 እባክዎ የይለፍ ቃል ያስገቡ፡ /technical የይለፍ_ቃል'})
                return "OK"

        # /logout - clear any active session (admin/technical/employee)
        if text == '/logout':
            clear_session(chat_id)
            requests.post(url, json={'chat_id': chat_id, 'text': '✅ ወጥተዋል (logged out)።'})
            return "OK"

        # /login <username> <password> - employee login, from any device
        if text.startswith('/login '):
            parts = text.split(' ', 2)
            if len(parts) == 3:
                emp = get_employee_by_credentials(parts[1].strip(), parts[2].strip())
                if emp:
                    set_session(chat_id, 'employee', emp['id'])
                    set_employee_chat_id(emp['id'], chat_id)
                    if emp.get('must_change_password'):
                        requests.post(url, json={
                            'chat_id': chat_id,
                            'text': f"✅ እንኳን ደህና መጡ {emp['full_name']}!\n\n🔐 መጀመሪያ የይለፍ ቃልዎን መቀየር አለብዎት፡\n/setpassword አዲስ_የይለፍ_ቃል"
                        })
                    else:
                        requests.post(url, json={'chat_id': chat_id, 'text': f"✅ እንኳን ደህና መጡ {emp['full_name']}! /myprofile ብለው መገለጫዎን ይመልከቱ።"})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': '❌ የተሳሳተ username ወይም password።'})
            else:
                requests.post(url, json={'chat_id': chat_id, 'text': '🔒 ይህን ይጠቀሙ፡ /login username password'})
            return "OK"

        # /setpassword <new_password> - employee sets/changes their own password
        if text.startswith('/setpassword '):
            session = get_session(chat_id)
            if session and session['role'] == 'employee':
                emp = get_employee_by_id(session['employee_id'])
                new_pw = text[len('/setpassword '):].strip()
                if emp and new_pw:
                    set_employee_password(emp['username'], new_pw, must_change=False)
                    requests.post(url, json={'chat_id': chat_id, 'text': '✅ የይለፍ ቃልዎ ተቀይሯል! /myprofile ብለው ይቀጥሉ።'})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': '❌ ባዶ የይለፍ ቃል አይቀበልም።'})
            else:
                requests.post(url, json={'chat_id': chat_id, 'text': '🔒 መጀመሪያ ይግቡ፡ /login username password'})
            return "OK"

        # /resetpassword <username> - admin or team_leader resets an employee's password
        if text.startswith('/resetpassword '):
            if is_team_leader_or_admin(chat_id):
                target_username = text[len('/resetpassword '):].strip()
                emp = get_employee_by_username(target_username)
                if emp:
                    temp_pw = generate_temp_password()
                    set_employee_password(target_username, temp_pw, must_change=True)
                    requests.post(url, json={'chat_id': chat_id, 'text': f"✅ አዲስ ጊዜያዊ password ለ {target_username}: {temp_pw}\n(ሰራተኛው ሲገባ መቀየር ይጠየቃል)"})
                    if emp.get('telegram_chat_id'):
                        requests.post(url, json={'chat_id': emp['telegram_chat_id'], 'text': f"🔐 password ዎ ዳግም ተጀምሯል። ጊዜያዊ password: {temp_pw}\nበ /login {target_username} {temp_pw} ይግቡ፣ ከዚያ /setpassword አዲስ_ቃል ይጠቀሙ።"})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': '❌ ሰራተኛ አልተገኘም።'})
            else:
                requests.post(url, json={'chat_id': chat_id, 'text': '🚫 ይህ ትዕዛዝ ለአድሚን/ቲም ሊደር ብቻ ነው።'})
            return "OK"

        # /setrole <username> <employee|team_leader> - admin only
        if text.startswith('/setrole '):
            if is_admin_chat(chat_id):
                parts = text[len('/setrole '):].split(' ', 1)
                if len(parts) == 2 and parts[1].strip() in ('employee', 'team_leader'):
                    set_employee_role(parts[0].strip(), parts[1].strip())
                    requests.post(url, json={'chat_id': chat_id, 'text': f"✅ {parts[0]} ደረጃው ወደ {parts[1]} ተቀይሯል።"})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': '❌ ይህን ይጠቀሙ፡ /setrole username employee ወይም /setrole username team_leader'})
            else:
                requests.post(url, json={'chat_id': chat_id, 'text': '🚫 ይህ ትዕዛዝ ለአድሚን ብቻ ነው።'})
            return "OK"

        # /feedback <text> - any customer can leave feedback
        if text.startswith('/feedback '):
            feedback_text = text[len('/feedback '):].strip()
            if feedback_text:
                add_feedback(user_id, name, username, feedback_text)
                requests.post(url, json={'chat_id': chat_id, 'text': '🙏 እናመሰግናለን! አስተያየትዎ ደርሶናል።'})
            else:
                requests.post(url, json={'chat_id': chat_id, 'text': '❌ ባዶ አስተያየት አይቀበልም።'})
            return "OK"

        # /viewfeedback - admin views recent customer feedback
        if text == '/viewfeedback':
            if is_admin_chat(chat_id):
                items = get_recent_feedback(20)
                if items:
                    listing = "\n\n".join([f"👤 {f['name']} (@{f['username'] or 'የለም'})\n💬 {f['text']}\n🕐 {f['created_at']}" for f in items])
                else:
                    listing = "ምንም አስተያየት የለም።"
                requests.post(url, json={'chat_id': chat_id, 'text': f"📝 የደንበኛ አስተያየቶች:\n\n{listing}"})
            else:
                requests.post(url, json={'chat_id': chat_id, 'text': '🚫 ይህ ትዕዛዝ ለአድሚን ብቻ ነው።'})
            return "OK"

        # /myprofile - employee views their own profile
        if text == '/myprofile':
            session = get_session(chat_id)
            if session and session['role'] == 'employee':
                emp = get_employee_by_id(session['employee_id'])
                if emp:
                    role_label = "🌟 ቲም ሊደር" if emp.get('role') == 'team_leader' else "👤 ሰራተኛ"
                    profile_text = f"""👤 የግል መገለጫ ({role_label})

ስም: {emp['full_name']}
ስራ: {emp['position']}
ደመወዝ: {emp['salary']}

💰 ቦነስ:
{emp['bonus'] or 'የለም'}

⚠️ ማስጠንቀቂያ:
{emp['warnings'] or 'የለም'}

📋 ስራዎች:
{emp['tasks'] or 'የለም'}"""
                    requests.post(url, json={'chat_id': chat_id, 'text': profile_text})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': '❌ መገለጫ አልተገኘም።'})
            else:
                requests.post(url, json={'chat_id': chat_id, 'text': '🔒 መጀመሪያ ይግቡ፡ /login username password'})
            return "OK"

        # ===== Admin-only commands (owner OR password-authenticated admin, any device) =====
        if is_admin_chat(chat_id):

            # /addemployee username|password|full_name|position|salary
            if text.startswith('/addemployee '):
                try:
                    parts = text[len('/addemployee '):].split('|')
                    emp_username, emp_password, full_name, position, salary = [p.strip() for p in parts]
                    add_employee(emp_username, emp_password, full_name, position, salary)
                    requests.post(url, json={'chat_id': chat_id, 'text': f"✅ ሰራተኛ ተጨምሯል: {full_name} ({emp_username})"})
                except Exception:
                    requests.post(url, json={
                        'chat_id': chat_id,
                        'text': "❌ ትክክለኛ ፎርማት፡\n/addemployee username|password|ሙሉ ስም|ስራ|ደመወዝ"
                    })
                return "OK"

            # /employees - list all employees
            if text == '/employees':
                emps = list_employees()
                if emps:
                    listing = "\n".join([f"• {e['full_name']} (@{e['username']}) - {e['position']}" for e in emps])
                else:
                    listing = "ምንም ሰራተኛ የለም።"
                requests.post(url, json={'chat_id': chat_id, 'text': f"👥 ሰራተኞች:\n\n{listing}"})
                return "OK"

            # /setbonus username amount
            if text.startswith('/setbonus '):
                parts = text[len('/setbonus '):].split(' ', 1)
                if len(parts) == 2:
                    update_employee_field(parts[0].strip(), 'bonus', parts[1].strip(), append=True)
                    requests.post(url, json={'chat_id': chat_id, 'text': f"✅ ቦነስ ተጨመረ ለ {parts[0]}"})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': "❌ ይህን ይጠቀሙ፡ /setbonus username መጠን"})
                return "OK"

            # /warn username warning_text
            if text.startswith('/warn '):
                parts = text[len('/warn '):].split(' ', 1)
                if len(parts) == 2:
                    update_employee_field(parts[0].strip(), 'warnings', parts[1].strip(), append=True)
                    requests.post(url, json={'chat_id': chat_id, 'text': f"✅ ማስጠንቀቂያ ተጨመረ ለ {parts[0]}"})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': "❌ ይህን ይጠቀሙ፡ /warn username ጽሑፍ"})
                return "OK"

            # /addtask username task_text
            if text.startswith('/addtask '):
                parts = text[len('/addtask '):].split(' ', 1)
                if len(parts) == 2:
                    update_employee_field(parts[0].strip(), 'tasks', parts[1].strip(), append=True)
                    requests.post(url, json={'chat_id': chat_id, 'text': f"✅ ስራ ተጨመረ ለ {parts[0]}"})
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': "❌ ይህን ይጠቀሙ፡ /addtask username ጽሑፍ"})
                return "OK"

            # /seedproducts - one-time load of the 5 real products with photos
            if text == '/seedproducts':
                seed_data = [
                    ("CALUS VC9 4G Outdoor Solar Security Camera", "CCTV ካሜራ",
                     "ለገጠር/እርሻ መብራት በሚቆራረጥበት ቦታ የሚሆን። Battery አለው፣ PTZ 360° ይዞራል፣ 4G SIM ተገናኝቶ በስልክ ቁጥጥር፣ Night Vision፣ Motion Tracking፣ 128GB SD ይቀበላል።",
                     f"{BASE_URL}/static/product1.jpg"),
                    ("C92 MAX Dual HD Camera 4G Smartwatch", "ኤሌክትሮኒክስ",
                     "ባለ ሲም ስማርት ዋች፣ በሁለቱም በኩል ካሜራ ያለው። RAM 6GB፣ Internal 64GB፣ TikTok/Facebook/YouTube ይሰራል፣ 4G ኔትወርክ፣ 2.0'' HD ስክሪን።",
                     f"{BASE_URL}/static/product2.jpg"),
                    ("IMOU Ranger Dual 10MP", "CCTV ካሜራ",
                     "ባለ ሁለት ሌንስ የቤት ውስጥ ጥበቃ ካሜራ። 10MP Ultra HD፣ Dual Lens (2 አቅጣጫ በአንድ ጊዜ)፣ Full-Color Night Vision፣ Smart Tracking፣ Two-way Talk፣ Human & Pet Detection።",
                     f"{BASE_URL}/static/product3.jpg"),
                    ("Speed Dome 4inch 4MP 32X Network Camera", "CCTV ካሜራ",
                     "4MP resolution፣ DarkFighter + ColorVu technology፣ 32x optical zoom፣ እስከ 200m IR distance፣ WDR/HLC/BLC ድጋፍ፣ human/vehicle classification (AI)።",
                     f"{BASE_URL}/static/product4.jpg"),
                    ("Stellar AOV 2 Lens Solar Camera (2026 Model)", "CCTV ካሜራ",
                     "6MP Super HD፣ Safaricom/Ethiotel SIM የሚሰራ 360° Solar 4G ካሜራ፣ AOV (Always On Video)፣ 256GB SD ይቀበላል፣ ባለ 2 ሌንስ፣ Full Color፣ Bluetooth ድጋፍ። በጥቁር እና በነጭ ቀለም ይገኛል።",
                     f"{BASE_URL}/static/product5.jpg"),
                ]
                for name, category, desc, photo in seed_data:
                    add_product(name, category, desc, photo)
                requests.post(url, json={'chat_id': chat_id, 'text': f"✅ {len(seed_data)} ምርቶች ተጨምረዋል! /admin → 🛍️ ምርቶች tab ላይ ይመልከቱ።"})
                return "OK"

            # /addpromo <text> - add a new promo to rotation
            if text.startswith('/addpromo '):
                promo_text = text[len('/addpromo '):].strip()
                if promo_text:
                    count = add_promo(promo_text)
                    requests.post(url, json={
                        'chat_id': chat_id,
                        'text': f"✅ ማስታወቂያ ተጨመረ! አጠቃላይ ማስታወቂያዎች: {count}"
                    })
                else:
                    requests.post(url, json={'chat_id': chat_id, 'text': "❌ ባዶ ጽሑፍ አይቀበልም።"})
                return "OK"

            # /promocount - check how many promos stored
            if text == '/promocount':
                count = len(load_promos())
                requests.post(url, json={'chat_id': chat_id, 'text': f"📦 አጠቃላይ ማስታወቂያዎች: {count}"})
                return "OK"

            # /postnow - manually trigger a promo post immediately (for testing)
            if text == '/postnow':
                post_random_promo()
                requests.post(url, json={'chat_id': chat_id, 'text': "✅ ማስታወቂያ ወደ ቻናል ተልኳል።"})
                return "OK"

            # /send <user_id> <message> - message a person from the bot
            if text.startswith('/send '):
                try:
                    parts = text.split(' ', 2)
                    target_id = parts[1]
                    message_text = parts[2]
                    send_result = requests.post(url, json={'chat_id': target_id, 'text': message_text})
                    if send_result.ok and send_result.json().get('ok'):
                        requests.post(url, json={'chat_id': chat_id, 'text': f"✅ ተልኳል ወደ {target_id}"})
                    else:
                        err = send_result.json().get('description', 'unknown error')
                        requests.post(url, json={'chat_id': chat_id, 'text': f"❌ አልተላከም: {err}"})
                except (IndexError, ValueError):
                    requests.post(url, json={
                        'chat_id': chat_id,
                        'text': "❌ የተሳሳተ ፎርማት። ይህን ይጠቀሙ፡\n/send USER_ID መልእክት እዚህ"
                    })
                return "OK"

        # Forward every incoming message to owner (except owner's own admin commands, handled above)
        requests.post(
            f"{TELEGRAM_URL}/forwardMessage",
            json={'chat_id': OWNER_CHAT_ID, 'from_chat_id': chat_id, 'message_id': msg['message_id']}
        )
        requests.post(url, json={'chat_id': OWNER_CHAT_ID, 'text': info})

        # ===== /start handling, including price-inquiry deep link (?start=price) =====
        if text.startswith('/start'):
            parts = text.split(' ', 1)
            start_param = parts[1] if len(parts) > 1 else None

            if start_param == 'price':
                # Customer tapped "ዋጋ ጠይቁ" button from a promo post
                requests.post(url, json={
                    'chat_id': chat_id,
                    'text': '✅ ጥያቄዎ ደርሶናል! ስለ ዋጋ በቅርቡ በዚሁ ቦት በኩል ምላሽ ያገኛሉ። እናመሰግናለን! 🙏'
                })
                requests.post(url, json={
                    'chat_id': OWNER_CHAT_ID,
                    'text': f"💰 የዋጋ ጥያቄ ደረሰ!\n\n{info}"
                })
                return "OK"

            # Normal /start
            requests.post(url, json={'chat_id': chat_id, 'text': WELCOME_MESSAGE})
            send_with_webapp_button(chat_id, '🛍️ ካታሎግ ለማየት ይህን ይጫኑ', '🛍️ ምርቶች ይመልከቱ', '/webapp')
            requests.post(url, json={
                'chat_id': chat_id,
                'text': '📢 ቻናላችንን ይቀላቀሉ',
                'reply_markup': {'inline_keyboard': [[{'text': '📢 ቻናላችንን ይቀላቀሉ', 'url': 'https://t.me/cctvcamera2018'}]]}
            })
            requests.post(url, json={
                'chat_id': chat_id,
                'text': '📞 ስልክ ቁጥርዎን ማጋራት ይፈልጋሉ? ከታች ያለውን ቁልፍ ይጫኑ (አማራጭ ነው)',
                'reply_markup': {
                    'keyboard': [[
                        {'text': '📞 ስልክ ቁጥር አጋራ', 'request_contact': True}
                    ]],
                    'resize_keyboard': True,
                    'one_time_keyboard': True
                }
            })
            requests.post(url, json={
                'chat_id': OWNER_CHAT_ID,
                'text': f"{info}\n\n🤖 *AI መልስ:*\nWELCOME_MESSAGE",
                'parse_mode': 'Markdown'
            })
            return "OK"

        # Handle shared contact
        if 'contact' in msg:
            contact = msg['contact']
            phone = contact.get('phone_number', 'N/A')
            requests.post(url, json={
                'chat_id': OWNER_CHAT_ID,
                'text': f"📞 ስልክ ቁጥር ደረሰ!\nስም: {name}\nስልክ: {phone}\nመታወቂያ: {user_id}"
            })
            requests.post(url, json={'chat_id': chat_id, 'text': '✅ አመሰግናለሁ! ስልክ ቁጥርዎ ደርሶናል።'})
            return "OK"

        # AI reply for regular messages
        ai_reply = ask_deepseek(text)
        if ai_reply:
            reply = f"🤖 *Marshalom AI ረዳት*\n\n{ai_reply}"
            ai_reply_text = ai_reply
        else:
            reply = BUSY_MESSAGE
            ai_reply_text = "AI not available"

        requests.post(url, json={'chat_id': chat_id, 'text': reply, 'parse_mode': 'Markdown'})
        requests.post(url, json={
            'chat_id': OWNER_CHAT_ID,
            'text': f"{info}\n\n🤖 *AI መልስ:*\n{ai_reply_text}",
            'parse_mode': 'Markdown'
        })

        return "OK"
    except Exception as e:
        print(f"Error: {e}")
        return "OK"


# Initialize database table and start the promo scheduler when the app boots
init_db()
schedule_daily_promos()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
