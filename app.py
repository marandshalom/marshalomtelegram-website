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

# ===== ከ Render Environment Variables ይነበባል =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@MarshalomTech")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "marshalom_bot")
DATABASE_URL = os.environ.get("DATABASE_URL")
BASE_URL = os.environ.get("BASE_URL", "https://lwam-bot.onrender.com")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
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
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
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

# ===== ቋንቋ ትርጉሞች =====
def get_translations(lang='am'):
    translations = {
        'am': {
            'title': 'ሻሎም ቴክኖሎጂ',
            'sub': '✨ የእርስዎ የደህንነት አጋር ✨',
            'menu': ['🛍️ ምርቶች', '📞 ይደውሉ', '🌐 ማህበራዊ', '👥 ማጋሪያ', '📰 ዜና', '⚖️ ንጽጽር', '💼 ክፍት ስራ', '🎁 ቅናሽ', '🤖 ረዳት', '🛡️ ድጋፍ', '📢 ማስታወቂያ', '💡 ምክሮች', '🏦 ባንክ', '🔑 መግቢያ', '⚙️ አድሚን', '👔 ቲም ሊደር', '👤 ሰራተኛ'],
            'promo': '✨ <strong>አዲስ የፀሐይ ካሜራ</strong> 15% ቅናሽ!',
            'products': ['🌟 አዲስ የፀሐይ ካሜራ', '4ጂ፣ 360°፣ ባትሪ'],
            'call': ['ይደውሉ', 'ኢትዮ ቴሌኮም', 'ሳፋሪኮም'],
            'social': ['ማህበራዊ ሚዲያ'],
            'share': ['ማጋሪያ', '✨ እንኳን ደህና መጡ ወደ ማርሻሎም! ✨'],
            'news': ['ዜና', '📸 አዲስ ካሜራ ፊት ብቻ ሳይሆን የእግር ንዝረትን ይለያል!', '🚀 በአሜሪካ የሰማይ ላይ ካሜራ ተፈተሸ', '😂 አስቂኝ — "777" የማርሻሎም ምስጢር!'],
            'compare': ['ንጽጽር'],
            'jobs': ['ክፍት ስራ', '📹 የCCTV ተከላ ቴክኒሽያን', '💻 የኔትወርክ መሐንዲስ'],
            'discount': ['ቅናሽ', 'እንኳን ደስ አለዎት!'],
            'ai': ['ረዳት', '🌟 ማርሻሎም የቴክኖሎጂ ረዳት 🌟'],
            'support': ['ድጋፍ', '24/7 ደንበኛ ድጋፍ'],
            'banks': ['ባንክ'],
            'login': ['መግቢያ', 'ለባለቤት፣ ቲም ሊደር እና ሰራተኞች'],
            'admin': ['አድሚን', 'ማርሻሎም', '🚀 ባለቤት', 'ሙሉ የስርዓት ቁጥጥር'],
            'teamleader': ['ቲም ሊደር', 'የናስ ሞላ', '🌟 የቡድን አስተዳደር'],
            'employee': ['ሰራተኛ', 'አብይ አለሙ', 'CCTV ቴክኒሽያን']
        },
        'en': {
            'title': 'Shalom Technology',
            'sub': '✨ Your Security Partner ✨',
            'menu': ['🛍️ Products', '📞 Call', '🌐 Social', '👥 Share', '📰 News', '⚖️ Compare', '💼 Jobs', '🎁 Discount', '🤖 Assistant', '🛡️ Support', '📢 Promo', '💡 Tips', '🏦 Banks', '🔑 Login', '⚙️ Admin', '👔 Team Leader', '👤 Employee'],
            'promo': '✨ <strong>New Solar Camera</strong> 15% OFF!',
            'products': ['🌟 New Solar Camera', '4G, 360°, Battery'],
            'call': ['Call', 'Ethio Telecom', 'Safaricom'],
            'social': ['Social Media'],
            'share': ['Share', '✨ Welcome to Marshalom! ✨'],
            'news': ['News', '📸 New Camera Detects Footstep Vibration!', '🚀 Sky Camera Tested in USA', '😂 Funny — "777" Marshalom\'s Secret!'],
            'compare': ['Compare'],
            'jobs': ['Jobs', '📹 CCTV Installation Technician', '💻 Network Engineer'],
            'discount': ['Discount', 'Congratulations!'],
            'ai': ['Assistant', '🌟 Marshalom Technology Assistant 🌟'],
            'support': ['Support', '24/7 Customer Support'],
            'banks': ['Banks'],
            'login': ['Login', 'For Owner, Team Leader and Employees'],
            'admin': ['Admin', 'Marshalom', '🚀 Owner', 'Full System Control'],
            'teamleader': ['Team Leader', 'Yonas Mola', '🌟 Team Management'],
            'employee': ['Employee', 'Abiy Alemu', 'CCTV Technician']
        }
    }
    return translations.get(lang, translations['am'])

# ===== የWebApp HTML ገጽ (ተስተካክሏል) =====
def get_webapp_html(lang='am'):
    t = get_translations(lang)
    
    # JavaScript እና CSS በተናጥል
    js_code = """
    function showPage(id) {
        document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
        document.getElementById(id).classList.add('active');
        document.getElementById('pagesContainer').scrollTop=0;
        document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
        if(id==='page-home') document.querySelector('.nav-item:nth-child(1)').classList.add('active');
        else if(id==='page-products') document.querySelector('.nav-item:nth-child(2)').classList.add('active');
        else if(id==='page-ai') document.querySelector('.nav-item:nth-child(3)').classList.add('active');
        else if(id==='page-share') document.querySelector('.nav-item:nth-child(4)').classList.add('active');
        else if(id==='page-jobs') document.querySelector('.nav-item:nth-child(5)').classList.add('active');
    }
    function switchLanguage(lang) {
        document.querySelectorAll('#langSelector button').forEach(b=>b.classList.remove('active'));
        document.querySelector('#langSelector button[data-lang=\"'+lang+'\"]').classList.add('active');
        window.location.href = '/webapp?lang='+lang;
    }
    """
    
    html = f"""
<!DOCTYPE html>
<html lang="am">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{t['title']}</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', system-ui, sans-serif; }}
        body {{ background: #0b1219; min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 12px; }}
        .app-container {{ max-width: 420px; width: 100%; min-height: 780px; background: #17212b; border-radius: 36px; box-shadow: 0 20px 60px rgba(0,0,0,0.8), 0 0 0 2px #2b3a4a inset; overflow: hidden; padding: 16px; position: relative; }}
        .header {{ text-align: center; padding-bottom: 12px; border-bottom: 1px solid #2b3a4a; margin-bottom: 12px; }}
        .header .top-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }}
        .header .lang-selector {{ display: flex; gap: 4px; }}
        .header .lang-selector button {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); color: #8aa3b5; padding: 3px 8px; border-radius: 12px; font-size: 10px; cursor: pointer; transition: 0.2s; }}
        .header .lang-selector button.active {{ background: rgba(74,158,255,0.2); border-color: #4a9eff; color: #4a9eff; }}
        .cctv-container {{ display: inline-block; position: relative; width: 40px; height: 40px; animation: spin 4s linear infinite; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        .cctv-dome {{ width: 34px; height: 20px; background: linear-gradient(180deg,#4a9eff,#1a5a8a); border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%; position: absolute; top: 4px; left: 3px; box-shadow: 0 0 20px rgba(74,158,255,0.3); }}
        .cctv-dome::after {{ content: ''; width: 10px; height: 10px; background: radial-gradient(circle,#7ac7ff,#4a9eff); border-radius: 50%; position: absolute; top: 6px; left: 12px; box-shadow: inset 0 0 6px rgba(255,255,255,0.3); }}
        .cctv-base {{ width: 20px; height: 6px; background: linear-gradient(180deg,#2b3a4a,#1a2a3a); border-radius: 0 0 10px 10px; position: absolute; bottom: 4px; left: 10px; }}
        .cctv-red {{ width: 4px; height: 4px; background: #ff4444; border-radius: 50%; position: absolute; top: 2px; right: 6px; animation: blink 1s infinite; }}
        @keyframes blink {{ 0%,100%{{opacity:1;}} 50%{{opacity:0.2;}} }}
        .header h1 {{ font-size: 18px; font-weight: 700; background: linear-gradient(90deg,#4a9eff,#7ac7ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-top: 2px; }}
        .header .sub {{ font-size: 11px; color: #8aa3b5; }}
        .pages {{ flex: 1; overflow-y: auto; padding: 6px 0 70px; scroll-behavior: smooth; }}
        .page {{ display: none; animation: fadeSlide 0.3s ease; }}
        .page.active {{ display: block; }}
        @keyframes fadeSlide {{ 0% {{ opacity: 0; transform: translateY(12px); }} 100% {{ opacity: 1; transform: translateY(0); }} }}
        .page-title {{ font-size: 15px; font-weight: 600; color: #fff; display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }}
        .back-btn {{ background: rgba(255,255,255,0.08); border: none; color: #fff; font-size: 18px; padding: 2px 12px; border-radius: 30px; cursor: pointer; }}
        .menu-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 12px; }}
        .menu-btn {{ border-radius: 14px; padding: 10px 4px; text-align: center; font-size: 9px; font-weight: 500; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(0,0,0,0.3); color: #e0edf5; border: none; }}
        .menu-btn:hover {{ transform: scale(1.06) translateY(-3px); box-shadow: 0 8px 25px rgba(0,0,0,0.5); }}
        .menu-btn:active {{ transform: scale(0.95); }}
        .menu-btn .icon {{ font-size: 22px; display: block; margin-bottom: 2px; }}
        .menu-btn:nth-child(1){{background:linear-gradient(135deg,#2a3a4a,#1a2a3a);}}
        .menu-btn:nth-child(2){{background:linear-gradient(135deg,#4a2a22,#3a1a12);}}
        .menu-btn:nth-child(3){{background:linear-gradient(135deg,#4a3a1a,#3a2a0a);}}
        .menu-btn:nth-child(4){{background:linear-gradient(135deg,#1a4a3a,#0a3a2a);}}
        .menu-btn:nth-child(5){{background:linear-gradient(135deg,#3a2a5a,#2a1a4a);}}
        .menu-btn:nth-child(6){{background:linear-gradient(135deg,#4a2a3a,#3a1a2a);}}
        .menu-btn:nth-child(7){{background:linear-gradient(135deg,#4a3a1a,#3a2a0a);}}
        .menu-btn:nth-child(8){{background:linear-gradient(135deg,#1a4a3a,#0a3a2a);}}
        .menu-btn:nth-child(9){{background:linear-gradient(135deg,#2a3a5a,#1a2a4a);}}
        .menu-btn:nth-child(10){{background:linear-gradient(135deg,#1a4a3a,#0a3a2a);}}
        .menu-btn:nth-child(11){{background:linear-gradient(135deg,#4a2a1a,#3a1a0a);}}
        .menu-btn:nth-child(12){{background:linear-gradient(135deg,#2a4a4a,#1a3a3a);}}
        .menu-btn:nth-child(13){{background:linear-gradient(135deg,#4a4a1a,#3a3a0a);}}
        .menu-btn:nth-child(14){{background:linear-gradient(135deg,#4a2a2a,#3a1a1a);}}
        .menu-btn:nth-child(15){{background:linear-gradient(135deg,#1a2a4a,#0a1a3a);}}
        .menu-btn:nth-child(16){{background:linear-gradient(135deg,#3a2a5a,#2a1a4a);}}
        .menu-btn:nth-child(17){{background:linear-gradient(135deg,#4a2a3a,#3a1a2a);}}
        .section-title {{ color: #b8a84a; font-size: 13px; font-weight: 600; margin-bottom: 8px; }}
        .product-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }}
        .product-card {{ background: rgba(255,255,255,0.04); border-radius: 14px; overflow: hidden; border: 1px solid rgba(255,255,255,0.06); transition: 0.25s; cursor: pointer; }}
        .product-card:hover {{ transform: translateY(-4px); box-shadow: 0 8px 30px rgba(0,0,0,0.4); }}
        .product-card .promo-img {{ width: 100%; height: 100px; background: linear-gradient(135deg,#1a2a3a,#2a3a4a); display: flex; align-items: center; justify-content: center; font-size: 40px; color: #b8a84a; }}
        .product-card .info {{ padding: 6px 8px; text-align: center; }}
        .product-card .name {{ font-weight: 600; font-size: 11px; color: #b8a84a; }}
        .product-card .desc {{ font-size: 9px; color: #8aa3b5; margin: 2px 0 4px; }}
        .product-card .ask-btn {{ width: 100%; padding: 4px; border: none; border-radius: 8px; color: #fff; font-weight: 600; font-size: 10px; cursor: pointer; transition: 0.2s; background: linear-gradient(135deg,#4a3a1a,#3a2a0a); }}
        .product-card .ask-btn:hover {{ transform: scale(1.03); box-shadow: 0 4px 15px rgba(74,58,26,0.3); }}
        .channel-link {{ padding: 8px; background: rgba(74,158,255,0.08); border-radius: 12px; text-align: center; border: 1px dashed #4a9eff; margin-bottom: 10px; }}
        .channel-link a {{ color: #4a9eff; font-weight: 600; text-decoration: none; font-size: 12px; }}
        .promo-banner {{ background: linear-gradient(135deg,#4a2a2a,#3a1a1a); border-radius: 12px; padding: 10px 14px; margin-top: 10px; display: flex; align-items: center; gap: 10px; border: 1px solid #4a3a1a; }}
        .promo-banner .text {{ font-size: 12px; color: #c0d8e8; flex: 1; font-weight: 600; }}
        .promo-banner .text strong {{ color: #b8a84a; }}
        .promo-banner .link {{ color: #4a9eff; font-size: 11px; text-decoration: none; cursor: pointer; background: rgba(74,158,255,0.1); padding: 4px 12px; border-radius: 20px; font-weight: 600; transition: 0.2s; }}
        .promo-banner .link:hover {{ background: rgba(74,158,255,0.2); }}
        .bottom-nav {{ position: sticky; bottom: 0; background: rgba(15,26,36,0.92); backdrop-filter: blur(14px); border-top: 1px solid #2b3a4a; display: flex; justify-content: space-around; padding: 6px 0 12px; border-radius: 0 0 36px 36px; margin-top: 10px; }}
        .nav-item {{ color: #6a8a9e; font-size: 8px; text-align: center; cursor: pointer; padding: 2px 6px; border-radius: 30px; transition: 0.2s; }}
        .nav-item.active {{ color: #4a9eff; }}
        .nav-item .icon {{ font-size: 16px; display: block; }}
        .btn-primary {{ background: #4a9eff; border: none; border-radius: 30px; padding: 10px; color: #fff; font-weight: 600; font-size: 13px; width: 100%; cursor: pointer; transition: 0.2s; margin-top: 4px; }}
        .btn-primary:hover {{ background: #6ab0ff; }}
        .modal {{ display: none; background: rgba(0,0,0,0.7); position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 100; justify-content: center; align-items: center; padding: 20px; }}
        .modal.show {{ display: flex; }}
        .modal .content {{ background: #1a2a3a; border-radius: 16px; padding: 20px; max-width: 380px; width: 100%; border: 1px solid #2b3a4a; }}
        .modal .content h3 {{ color: #b8a84a; font-size: 16px; margin-bottom: 12px; }}
        .modal .content p {{ color: #c0d8e8; font-size: 14px; line-height: 1.8; }}
        .modal .content .btn-close {{ background: rgba(255,255,255,0.08); border: none; border-radius: 30px; padding: 10px; color: #fff; font-weight: 600; font-size: 13px; width: 100%; cursor: pointer; margin-top: 12px; transition: 0.2s; }}
        @media (max-width:420px){{.app-container{{border-radius:0;min-height:100vh;}}.bottom-nav{{border-radius:0;}}}}
    </style>
</head>
<body>
<div class="app-container">
    <div class="header">
        <div class="top-row">
            <div class="cctv-container"><div class="cctv-dome"></div><div class="cctv-base"></div><div class="cctv-red"></div></div>
            <div class="lang-selector" id="langSelector">
                <button class="active" data-lang="am" onclick="switchLanguage('am')">አማ</button>
                <button data-lang="en" onclick="switchLanguage('en')">EN</button>
                <button data-lang="ti" onclick="switchLanguage('ti')">ትግ</button>
                <button data-lang="or" onclick="switchLanguage('or')">ኦሮ</button>
            </div>
        </div>
        <h1 id="mainTitle">{t['title']}</h1>
        <div class="sub" id="mainSub">{t['sub']}</div>
    </div>
    <div class="pages" id="pagesContainer">
        <div class="page active" id="page-home">
            <div class="menu-grid" id="menuGrid">
                <div class="menu-btn" onclick="showPage('page-products')"><span class="icon">🛍️</span><span data-key="m0">{t['menu'][0]}</span></div>
                <div class="menu-btn" onclick="showPage('page-call')"><span class="icon">📞</span><span data-key="m1">{t['menu'][1]}</span></div>
                <div class="menu-btn" onclick="showPage('page-social')"><span class="icon">🌐</span><span data-key="m2">{t['menu'][2]}</span></div>
                <div class="menu-btn" onclick="showPage('page-share')"><span class="icon">👥</span><span data-key="m3">{t['menu'][3]}</span></div>
                <div class="menu-btn" onclick="showPage('page-news')"><span class="icon">📰</span><span data-key="m4">{t['menu'][4]}</span></div>
                <div class="menu-btn" onclick="showPage('page-compare')"><span class="icon">⚖️</span><span data-key="m5">{t['menu'][5]}</span></div>
                <div class="menu-btn" onclick="showPage('page-jobs')"><span class="icon">💼</span><span data-key="m6">{t['menu'][6]}</span></div>
                <div class="menu-btn" onclick="showPage('page-discount')"><span class="icon">🎁</span><span data-key="m7">{t['menu'][7]}</span></div>
                <div class="menu-btn" onclick="showPage('page-ai')"><span class="icon">🤖</span><span data-key="m8">{t['menu'][8]}</span></div>
                <div class="menu-btn" onclick="showPage('page-support')"><span class="icon">🛡️</span><span data-key="m9">{t['menu'][9]}</span></div>
                <div class="menu-btn" onclick="showPage('page-promo')"><span class="icon">📢</span><span data-key="m10">{t['menu'][10]}</span></div>
                <div class="menu-btn" onclick="showPage('page-tips')"><span class="icon">💡</span><span data-key="m11">{t['menu'][11]}</span></div>
                <div class="menu-btn" onclick="showPage('page-banks')"><span class="icon">🏦</span><span data-key="m12">{t['menu'][12]}</span></div>
                <div class="menu-btn" onclick="showPage('page-login')"><span class="icon">🔑</span><span data-key="m13">{t['menu'][13]}</span></div>
                <div class="menu-btn" onclick="showPage('page-admin')"><span class="icon">⚙️</span><span data-key="m14">{t['menu'][14]}</span></div>
                <div class="menu-btn" onclick="showPage('page-teamleader')"><span class="icon">👔</span><span data-key="m15">{t['menu'][15]}</span></div>
                <div class="menu-btn" onclick="showPage('page-employee')"><span class="icon">👤</span><span data-key="m16">{t['menu'][16]}</span></div>
            </div>
            <div class="promo-banner">
                <span style="font-size:18px;">🔥</span>
                <span class="text" id="promoText">{t['promo']}</span>
                <span class="link" onclick="alert('🔥 ወደ ፕሮሞሽን ገጽ ይወሰዳሉ!')">ተመልከት</span>
            </div>
            <div style="margin-top:6px; text-align:center; color:#6a8a9e; font-size:9px;">📢 ቻናላችን: <span style="color:#4a9eff;">@MarshalomTech</span></div>
        </div>
        <div class="page" id="page-products">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button><span id="pTitle">🛍️ {t['menu'][0]}</span></div>
            <div class="product-grid">
                <div class="product-card" style="grid-column: span 2;">
                    <div class="promo-img">⭐</div>
                    <div class="info">
                        <div class="name" id="prod1_name">{t['products'][0]}</div>
                        <div class="desc" id="prod1_desc">{t['products'][1]}</div>
                        <button class="ask-btn" onclick="alert('💬 ዋጋ ጥያቄ ተልኳል!')">💬 ዋጋ ጠይቁ</button>
                    </div>
                </div>
            </div>
            <div class="channel-link">📢 <a href="https://t.me/cctvcamera2018" target="_blank">ተጨማሪ ምርቶች ለማየት ቻናላችንን ይቀላቀሉ</a> 📢</div>
        </div>
        <div class="page" id="page-call">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>📞 <span id="callTitle">{t['call'][0]}</span></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:16px; padding:14px 10px; text-align:center; border:2px solid rgba(255,255,255,0.06); cursor:pointer;" onclick="alert('📞 ኢትዮ ቴሌኮም እየደወለ ነው...')">
                    <div style="font-size:14px; font-weight:700; color:#fff;">0931556590</div>
                    <div style="font-size:9px; color:#8aa3b5;">{t['call'][1]}</div>
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:16px; padding:14px 10px; text-align:center; border:2px solid rgba(255,255,255,0.06); cursor:pointer;" onclick="alert('📞 ሳፋሪኮም እየደወለ ነው...')">
                    <div style="font-size:14px; font-weight:700; color:#fff;">+251799556590</div>
                    <div style="font-size:9px; color:#8aa3b5;">{t['call'][2]}</div>
                </div>
            </div>
        </div>
        <div class="page" id="page-social">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🌐 <span id="socialTitle">{t['social'][0]}</span></div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-top:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px 4px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('🎵 TikTok ተከፈተ')"><span style="font-size:24px; display:block;">🎵</span><span style="font-size:8px; color:#c0d8e8;">TikTok</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px 4px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('▶️ YouTube ተከፈተ')"><span style="font-size:24px; display:block;">▶️</span><span style="font-size:8px; color:#c0d8e8;">YouTube</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px 4px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📘 Facebook ተከፈተ')"><span style="font-size:24px; display:block;">📘</span><span style="font-size:8px; color:#c0d8e8;">Facebook</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px 4px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📸 Instagram ተከፈተ')"><span style="font-size:24px; display:block;">📸</span><span style="font-size:8px; color:#c0d8e8;">Instagram</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px 4px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('💼 LinkedIn ተከፈተ')"><span style="font-size:24px; display:block;">💼</span><span style="font-size:8px; color:#c0d8e8;">LinkedIn</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px 4px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('🌐 ድር ጣቢያ ተከፈተ')"><span style="font-size:24px; display:block;">🌐</span><span style="font-size:8px; color:#c0d8e8;">www.marshalom.com</span></div>
            </div>
        </div>
        <div class="page" id="page-share">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>👥 <span id="shareTitle">{t['share'][0]}</span></div>
            <div style="background:rgba(74,158,255,0.04); border-radius:12px; padding:10px; margin-top:8px; border:1px solid rgba(74,158,255,0.06); font-size:11px; color:#c0d8e8; line-height:1.6;">
                <div style="color:#b8a84a; font-weight:700; font-size:13px; text-align:center;">{t['share'][1]}</div>
                <span>ይህንን ቦት ለጓደኞችዎ ያጋሩ!</span>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:4px; margin-top:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px 2px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📤 WhatsApp ተከፈተ')"><span style="font-size:18px; display:block;">💬</span><span style="font-size:7px; color:#c0d8e8;">WhatsApp</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px 2px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📤 Facebook ተከፈተ')"><span style="font-size:18px; display:block;">📘</span><span style="font-size:7px; color:#c0d8e8;">Facebook</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px 2px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📤 Telegram ተከፈተ')"><span style="font-size:18px; display:block;">✈️</span><span style="font-size:7px; color:#c0d8e8;">Telegram</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px 2px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📤 Instagram ተከፈተ')"><span style="font-size:18px; display:block;">📸</span><span style="font-size:7px; color:#c0d8e8;">Instagram</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px 2px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📤 TikTok ተከፈተ')"><span style="font-size:18px; display:block;">🎵</span><span style="font-size:7px; color:#c0d8e8;">TikTok</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px 2px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📤 LinkedIn ተከፈተ')"><span style="font-size:18px; display:block;">💼</span><span style="font-size:7px; color:#c0d8e8;">LinkedIn</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px 2px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📤 Twitter ተከፈተ')"><span style="font-size:18px; display:block;">🐦</span><span style="font-size:7px; color:#c0d8e8;">Twitter</span></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px 2px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('🔗 ሊንክ ተቀድቷል')"><span style="font-size:18px; display:block;">🔗</span><span style="font-size:7px; color:#c0d8e8;">ሊንክ</span></div>
            </div>
        </div>
        <div class="page" id="page-news">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>📰 <span id="newsTitle">{t['news'][0]}</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px 10px; margin-bottom:5px; border-left:3px solid #4a9eff;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">{t['news'][1]}</div>
                <div style="color:#c0d8e8; font-size:10px; margin-top:2px;">{t['news'][1]} 🦶</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px 10px; margin-bottom:5px; border-left:3px solid #4a9eff;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">{t['news'][2]}</div>
                <div style="color:#c0d8e8; font-size:10px; margin-top:2px;">{t['news'][2]} 🌍</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px 10px; margin-bottom:5px; border-left:3px solid #ff6b6b;">
                <div style="color:#ff6b6b; font-weight:600; font-size:11px;">{t['news'][3]}</div>
                <div style="color:#c0d8e8; font-size:10px; margin-top:2px;">{t['news'][3]} 🤫😂</div>
            </div>
        </div>
        <div class="page" id="page-compare">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>⚖️ <span id="compareTitle">{t['compare'][0]}</span></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; border:1px solid rgba(255,255,255,0.06);">
                    <div style="color:#b8a84a; font-weight:600; font-size:12px; text-align:center;">CALUS VC9</div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ጥራት</span><span style="color:#fff; float:right;">4MP</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ርቀት</span><span style="color:#fff; float:right;">50m</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ኔትወርክ</span><span style="color:#fff; float:right;">4G+WiFi</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0;"><span style="color:#8aa3b5;">PTZ</span><span style="color:#fff; float:right;">✅ 360°</span></div>
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; border:1px solid rgba(255,255,255,0.06);">
                    <div style="color:#b8a84a; font-weight:600; font-size:12px; text-align:center;">Speed Dome</div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ጥራት</span><span style="color:#fff; float:right;">4MP</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ርቀት</span><span style="color:#fff; float:right;">200m</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#8aa3b5;">ኔትወርክ</span><span style="color:#fff; float:right;">LAN+WiFi</span></div>
                    <div style="color:#c0d8e8; font-size:10px; padding:2px 0;"><span style="color:#8aa3b5;">PTZ</span><span style="color:#fff; float:right;">✅ 32x</span></div>
                </div>
            </div>
            <div style="text-align:center; font-size:18px; font-weight:900; color:#ff6b6b; padding:6px 0;">⚡ VS ⚡</div>
        </div>
        <div class="page" id="page-jobs">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>💼 <span id="jobsTitle">{t['jobs'][0]}</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; margin-bottom:6px; border-left:4px solid #4a9eff;">
                <h3 style="color:#fff; font-size:12px;">{t['jobs'][1]}</h3>
                <p style="color:#9bb0c0; font-size:10px;">አዲስ አበባ — ልምድ ያለው</p>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; margin-bottom:6px; border-left:4px solid #b8a84a;">
                <h3 style="color:#fff; font-size:12px;">{t['jobs'][2]}</h3>
                <p style="color:#9bb0c0; font-size:10px;">ለድርጅቶች ኔትወርክ መጫን</p>
            </div>
            <button class="btn-primary" onclick="alert('📝 ማመልከቻ ቅጽ ተከፈተ')">📝 አሁን አመልክት</button>
        </div>
        <div class="page" id="page-discount">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🎁 <span id="discountTitle">{t['discount'][0]}</span></div>
            <div style="background:linear-gradient(135deg,#4a3a1a,#3a2a0a); border-radius:16px; padding:20px 12px; text-align:center; color:#b8a84a; border:1px solid #4a3a1a;">
                <div style="font-size:30px;">🎉</div>
                <div style="font-size:15px; font-weight:700;">{t['discount'][1]}</div>
                <div style="font-size:28px; font-weight:900;">15%</div>
                <div style="font-size:13px; color:#c0d8e8;">ቅናሽ ለ <strong>C92 MAX</strong></div>
                <button class="btn-primary" style="margin-top:6px; background:#4a3a1a; color:#b8a84a;" onclick="alert('🎁 ቅናሽ ተቀብለዋል!')">ቅናሹን አግኙ</button>
            </div>
        </div>
        <div class="page" id="page-ai">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🤖 <span id="aiTitle">{t['ai'][0]}</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:14px; padding:12px 10px; border:1px solid rgba(255,215,0,0.06);">
                <div style="color:#b8a84a; font-size:14px; font-weight:700; text-align:center;">{t['ai'][1]}</div>
                <div style="color:#c0d8e8; font-size:11px; line-height:1.6; margin-top:4px;">ሰላም! መልእክትዎን ስላደረሱን እናመሰግናለን። 🙏<br>አሁን ላይ እጅግ በጣም ብዙ ጥያቄዎችን በማስተናገድ ላይ ስለሆንን፣ ትክክለኛ ምላሽ ለእርስዎ ለመስጠት ፍቃድ በመጠበቅ ላይ እገኛለሁ። ⏳<br>አትጨነቁ! መልእክትዎ በአስተማማኝ ሁኔታ ተይዟል። 🤝✨</div>
                <div style="background:rgba(255,0,0,0.06); border-left:4px solid #ff4444; padding:5px; border-radius:5px; margin-top:5px; font-size:10px; color:#ffaaaa;"><strong>⚠️ አስቸኳይ ከሆነ:</strong> "አስቸኳይ" ብለው ይጻፉ። ወደ ማርሻሎም ይላካል! 📞</div>
                <button class="btn-primary" style="margin-top:6px; background:transparent; border:1px solid #4a9eff; color:#4a9eff;" onclick="alert('📨 አስቸኳይ መልእክት ተልኳል!')">📨 አስቸኳይ ላክ</button>
            </div>
        </div>
        <div class="page" id="page-support">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🛡️ <span id="supportTitle">{t['support'][0]}</span></div>
            <div style="text-align:center;">
                <div style="font-size:32px;">🛡️</div>
                <p style="color:#c0d8e8; font-size:13px; font-weight:600;">{t['support'][1]}</p>
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-top:6px;">
                    <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📞 ስልክ እየደወለ ነው...')"><span style="font-size:28px; display:block;">📞</span><span style="font-size:9px; color:#c0d8e8;">ስልክ</span><span style="font-size:8px; color:#8aa3b5;">0931556590</span></div>
                    <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('💬 ዋትሳፕ ተከፈተ')"><span style="font-size:28px; display:block;">💬</span><span style="font-size:9px; color:#c0d8e8;">ዋትሳፕ</span><span style="font-size:8px; color:#8aa3b5;">+251799556590</span></div>
                    <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('✈️ ቴሌግራም ተከፈተ')"><span style="font-size:28px; display:block;">✈️</span><span style="font-size:9px; color:#c0d8e8;">ቴሌግራም</span><span style="font-size:8px; color:#8aa3b5;">@MarshalomTech</span></div>
                </div>
                <button class="btn-primary" style="margin-top:6px;" onclick="alert('📞 ድጋፍ እየተገናኘ ነው...')">📞 ወዲያው ይደውሉ</button>
            </div>
        </div>
        <div class="page" id="page-promo">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>📢 <span id="promoTitle">{t['menu'][10]}</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; border-left:4px solid #4a9eff; margin-bottom:4px;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">📢 የሳምንቱ ቅናሽ!</div>
                <div style="color:#c0d8e8; font-size:11px;">ሁሉም CCTV ካሜራዎች 10% ቅናሽ!</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; border-left:4px solid #b8a84a;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">🎉 አዲስ ምርት!</div>
                <div style="color:#c0d8e8; font-size:11px;">Stellar AOV Solar Camera — አሁን ተገኝቷል!</div>
            </div>
        </div>
        <div class="page" id="page-tips">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>💡 <span id="tipsTitle">{t['menu'][11]}</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; margin-bottom:4px;">
                <div style="color:#b8a84a; font-size:11px;">💡 ምክር 1</div>
                <div style="color:#c0d8e8; font-size:11px;">ካሜራ ሲጭኑ የፀሐይ ብርሃን ወደሚያገኝ ቦታ ይጫኑ!</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px;">
                <div style="color:#b8a84a; font-size:11px;">💡 ምክር 2</div>
                <div style="color:#c0d8e8; font-size:11px;">የካሜራ ስርዓትን በየጊዜው ያሻሽሉ!</div>
            </div>
        </div>
        <div class="page" id="page-banks">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🏦 <span id="banksTitle">{t['banks'][0]}</span></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; border:1px solid rgba(255,255,255,0.06);"><span style="font-size:22px; display:block;">🏦</span><div style="font-size:10px; color:#b8a84a; font-weight:600;">ንግድ ባንክ</div><div style="font-size:11px; color:#fff; font-weight:700; letter-spacing:1px; margin-top:2px;">1000134567890</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; border:1px solid rgba(255,255,255,0.06);"><span style="font-size:22px; display:block;">🏦</span><div style="font-size:10px; color:#b8a84a; font-weight:600;">አዋሽ ባንክ</div><div style="font-size:11px; color:#fff; font-weight:700; letter-spacing:1px; margin-top:2px;">2000245678901</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; border:1px solid rgba(255,255,255,0.06);"><span style="font-size:22px; display:block;">🏦</span><div style="font-size:10px; color:#b8a84a; font-weight:600;">ዳሽን ባንክ</div><div style="font-size:11px; color:#fff; font-weight:700; letter-spacing:1px; margin-top:2px;">3000345678902</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; border:1px solid rgba(255,255,255,0.06);"><span style="font-size:22px; display:block;">🏦</span><div style="font-size:10px; color:#b8a84a; font-weight:600;">አብይ ባንክ</div><div style="font-size:11px; color:#fff; font-weight:700; letter-spacing:1px; margin-top:2px;">4000456789013</div></div>
            </div>
        </div>
        <div class="page" id="page-login">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🔑 <span id="loginTitle">{t['login'][0]}</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:16px; padding:16px 12px; border:1px solid rgba(74,158,255,0.1);">
                <div style="text-align:center; font-size:28px; margin-bottom:4px;">🔐</div>
                <div style="color:#c0d8e8; font-size:12px; text-align:center; margin-bottom:6px;">{t['login'][1]}</div>
                <input type="text" placeholder="Username" style="width:100%; padding:10px; margin-bottom:8px; background:rgba(255,255,255,0.05); border:1px solid #2b3a4a; border-radius:10px; color:#fff; font-size:13px;">
                <input type="password" placeholder="Password" style="width:100%; padding:10px; margin-bottom:8px; background:rgba(255,255,255,0.05); border:1px solid #2b3a4a; border-radius:10px; color:#fff; font-size:13px;">
                <button class="btn-primary" onclick="alert('🔓 መግቢያ ተሳካ!')">🔓 ግባ</button>
            </div>
        </div>
        <div class="page" id="page-admin">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>⚙️ <span id="adminTitle">{t['admin'][0]}</span></div>
            <div style="background:rgba(74,158,255,0.06); border-radius:14px; padding:12px; text-align:center; border:1px solid rgba(74,158,255,0.06); margin-bottom:8px;">
                <span style="font-size:36px; display:block;">👑</span>
                <div style="font-size:16px; font-weight:700; color:#fff;">{t['admin'][1]}</div>
                <div style="font-size:10px; color:#b8a84a;">{t['admin'][2]}</div>
                <div style="font-size:9px; color:#8aa3b5;">{t['admin'][3]}</div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:4px; margin-bottom:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:6px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#4a9eff;">24</div><div style="font-size:7px; color:#8aa3b5;">ዛሬ ጥያቄ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:6px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#b8a84a;">12</div><div style="font-size:7px; color:#8aa3b5;">አዳዲስ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:6px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#4ecdc4;">156</div><div style="font-size:7px; color:#8aa3b5;">ደንበኞች</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:6px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#ff6b6b;">8</div><div style="font-size:7px; color:#8aa3b5;">ዛሬ ሽያጭ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:6px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#a29bfe;">5</div><div style="font-size:7px; color:#8aa3b5;">ሰራተኞች</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:6px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#b8a84a;">10</div><div style="font-size:7px; color:#8aa3b5;">ካሜራዎች</div></div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📊 ስታቲስቲክስ ተከፈተ')"><span style="font-size:20px;">📊</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ስታቲስቲክስ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('🛍️ ምርቶች ተከፈተ')"><span style="font-size:20px;">🛍️</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ምርቶች</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('👥 ደንበኞች ተከፈተ')"><span style="font-size:20px;">👥</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ደንበኞች</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('➕ ሰራተኛ ጨምር ተከፈተ')"><span style="font-size:20px;">➕</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ሰራተኛ ጨምር</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📋 ሰራተኞች ተከፈተ')"><span style="font-size:20px;">📋</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ሰራተኞች</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('🏦 ባንክ ተከፈተ')"><span style="font-size:20px;">🏦</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ባንክ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('🎨 ማበጀት ተከፈተ')"><span style="font-size:20px;">🎨</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ማበጀት</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📢 ማስታወቂያ ተከፈተ')"><span style="font-size:20px;">📢</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ማስታወቂያ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📹 ካሜራዎች ተከፈተ')"><span style="font-size:20px;">📹</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ካሜራዎች</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('🔧 ሲስተም ተከፈተ')"><span style="font-size:20px;">🔧</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ሲስተም</div></div>
            </div>
        </div>
        <div class="page" id="page-teamleader">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>👔 <span id="tlTitle">{t['teamleader'][0]}</span></div>
            <div style="background:rgba(74,158,255,0.06); border-radius:14px; padding:12px; text-align:center; border:1px solid rgba(74,158,255,0.06); margin-bottom:8px;">
                <span style="font-size:36px; display:block;">👔</span>
                <div style="font-size:16px; font-weight:700; color:#fff;">{t['teamleader'][1]}</div>
                <div style="font-size:10px; color:#b8a84a;">{t['teamleader'][2]}</div>
                <div style="font-size:9px; color:#8aa3b5;">የእርስዎ የደህንነት አጋር</div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:4px; margin-bottom:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:6px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#4a9eff;">12</div><div style="font-size:7px; color:#8aa3b5;">የቡድን ስራ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:6px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#4ecdc4;">8</div><div style="font-size:7px; color:#8aa3b5;">ተጠናቀቀ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:6px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#b8a84a;">4</div><div style="font-size:7px; color:#8aa3b5;">በመሄድ</div></div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('👤 ሰራተኞች ተከፈተ')"><span style="font-size:20px;">👤</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ሰራተኞች</div><div style="font-size:14px; font-weight:700; color:#4a9eff;">5</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📋 ስራ መመደብ ተከፈተ')"><span style="font-size:20px;">📋</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ስራ መመደብ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📊 ሪፖርት 1 ተከፈተ')"><span style="font-size:20px;">📊</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ሪፖርት 1</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📈 ሪፖርት 2 ተከፈተ')"><span style="font-size:20px;">📈</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ሪፖርት 2</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('🔑 የይለፍ ቃል ማመንጨት ተከፈተ')"><span style="font-size:20px;">🔑</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ፓስዎርድ አመንጭ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('⚠️ ማስጠንቀቂያ ተከፈተ')"><span style="font-size:20px;">⚠️</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ማስጠንቀቂያ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('🚫 ማባረር ተከፈተ')"><span style="font-size:20px;">🚫</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">ማባረር</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="alert('📝 መልእክት ላክ ተከፈተ')"><span style="font-size:20px;">📝</span><div style="color:#c0d8e8; font-size:9px; margin-top:2px;">መልእክት ላክ</div></div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; margin-top:6px;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">📋 የቡድን ስራዎች</div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">📹 C92 MAX መጫን <span style="float:right; color:#4ecdc4;">✅ አለቀ</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">☀️ ሶላር ካሜራ ተከላ <span style="float:right; color:#b8a84a;">⏳ በመሄድ</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">📅 የደንበኛ ቀጠሮ <span style="float:right; color:#ff6b6b;">🔴 10:00</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0;">🛠️ የኔትወርክ ጥገና <span style="float:right; color:#b8a84a;">⏳ በመሄድ</span></div>
            </div>
        </div>
        <div class="page" id="page-employee">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>👤 <span id="empTitle">{t['employee'][0]}</span></div>
            <div style="background:rgba(74,158,255,0.06); border-radius:14px; padding:12px; text-align:center; border:1px solid rgba(74,158,255,0.06); margin-bottom:8px;">
                <span style="font-size:36px; display:block;">👤</span>
                <div style="font-size:16px; font-weight:700; color:#fff;">{t['employee'][1]}</div>
                <div style="font-size:10px; color:#b8a84a;">{t['employee'][2]}</div>
                <div style="font-size:9px; color:#8aa3b5;">⭐ ⭐ ⭐ ⭐ ⭐ (4.8)</div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:5px; margin-bottom:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#4ecdc4;">12,500</div><div style="font-size:7px; color:#8aa3b5;">ኮሚሽን</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#4a9eff;">8</div><div style="font-size:7px; color:#8aa3b5;">ተጠናቀቁ</div></div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:8px; text-align:center;"><div style="font-size:16px; font-weight:700; color:#b8a84a;">3</div><div style="font-size:7px; color:#8aa3b5;">በመሄድ</div></div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:8px; padding:8px; margin-bottom:4px;">
                <div style="display:flex; justify-content:space-between; color:#c0d8e8; font-size:10px; padding:2px 0;"><span style="color:#8aa3b5;">ስራ</span><span>{t['employee'][2]}</span></div>
                <div style="display:flex; justify-content:space-between; color:#c0d8e8; font-size:10px; padding:2px 0;"><span style="color:#8aa3b5;">ቦነስ</span><span style="color:#4ecdc4;">2,000 ብር</span></div>
                <div style="display:flex; justify-content:space-between; color:#c0d8e8; font-size:10px; padding:2px 0;"><span style="color:#8aa3b5;">ማስጠንቀቂያ</span><span style="color:#4ecdc4;">የለም</span></div>
            </div>
            <div style="background:rgba(74,158,255,0.06); border-radius:10px; padding:8px; border-left:3px solid #4a9eff; margin-top:4px; font-size:10px; color:#c0d8e8;">
                <span style="color:#b8a84a; font-weight:600;">📨 ከቲም ሊደር:</span> ዛሬ ከሰአት 2 ላይ ስብሰባ አለ!
            </div>
            <div style="background:rgba(74,158,255,0.06); border-radius:10px; padding:8px; border-left:3px solid #b8a84a; margin-top:4px; font-size:10px; color:#c0d8e8;">
                <span style="color:#b8a84a; font-weight:600;">📨 ከአድሚን:</span> ጥሩ ስራ! ቀጥል!
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; margin-top:6px;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">📋 የእኔ ስራዎች</div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">📹 C92 MAX መጫን <span style="float:right; color:#4ecdc4;">✅ አለቀ</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">☀️ ሶላር ካሜራ ተከላ <span style="float:right; color:#b8a84a;">⏳ በመሄድ</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">🛠️ የኔትወርክ ጥገና <span style="float:right; color:#b8a84a;">⏳ በመሄድ</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">📅 የደንበኛ ቀጠሮ <span style="float:right; color:#ff6b6b;">🔴 10:00</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0;">📋 ሪፖርት መሙላት <span style="float:right; color:#b8a84a;">⏳ በመሄድ</span></div>
            </div>
            <button class="btn-primary" style="margin-top:4px;" onclick="alert('📝 አዲስ ስራ ማመልከቻ ተከፈተ')">📝 አዲስ ስራ አመልክት</button>
        </div>
    </div>
    <div class="bottom-nav">
        <div class="nav-item active" onclick="showPage('page-home')"><span class="icon">🏠</span><span data-key="n0">መነሻ</span></div>
        <div class="nav-item" onclick="showPage('page-products')"><span class="icon">🛍️</span><span data-key="n1">ምርቶች</span></div>
        <div class="nav-item" onclick="showPage('page-ai')"><span class="icon">🤖</span><span data-key="n2">ረዳት</span></div>
        <div class="nav-item" onclick="showPage('page-share')"><span class="icon">👥</span><span data-key="n3">አጋራ</span></div>
        <div class="nav-item" onclick="showPage('page-jobs')"><span class="icon">💼</span><span data-key="n4">ስራ</span></div>
    </div>
</div>
<script>
    {js_code}
</script>
</body>
</html>
    """
    return html

# ===== የWebApp ገጽ =====
@app.route('/webapp')
def webapp():
    lang = request.args.get('lang', 'am')
    return render_template_string(get_webapp_html(lang))

# ===== ቴሌግራም Webhook =====
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
        name = user.get('first_name', '') + (' ' + user['last_name'] if user.get('last_name') else '')
        username = user.get('username', '')
        user_id = user.get('id', '')

        # ===== WebApp ማስተናገጃ =====
        if text == '/start':
            webapp_url = f"{BASE_URL}/webapp?lang=am"
            requests.post(f"{TELEGRAM_URL}/sendMessage", json={
                'chat_id': chat_id,
                'text': "🌟 እንኳን ደህና መጡ ወደ Shalom Technology!\n\n📱 አፕሊኬሽናችንን ለመክፈት ከታች ያለውን ቁልፍ ይጫኑ!",
                'reply_markup': {
                    'inline_keyboard': [[{
                        'text': '🚀 አፕ ክፈት',
                        'web_app': {'url': webapp_url}
                    }]]
                }
            })
            return "OK"

        # ===== AI ምላሽ =====
        if DEEPSEEK_API_KEY:
            try:
                url = "https://api.deepseek.com/chat/completions"
                headers = {
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "አንተ Marshalom AI ነህ — የ Shalom Technology ረዳት። በአማርኛ መልስ ስጥ።"},
                        {"role": "user", "content": text}
                    ],
                    "max_tokens": 300
                }
                response = requests.post(url, json=payload, headers=headers, timeout=25)
                if response.status_code == 200:
                    data = response.json()
                    ai_reply = data["choices"][0]["message"]["content"]
                    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
                        'chat_id': chat_id,
                        'text': f"🤖 *Marshalom AI:*\n\n{ai_reply}",
                        'parse_mode': 'Markdown'
                    })
                else:
                    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
                        'chat_id': chat_id,
                        'text': "⏳ እባክዎ ይጠብቁ! በቅርቡ ምላሽ ያገኛሉ።"
                    })
            except Exception as e:
                requests.post(f"{TELEGRAM_URL}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "⏳ እባክዎ ይጠብቁ! በቅርቡ ምላሽ ያገኛሉ።"
                })
        else:
            requests.post(f"{TELEGRAM_URL}/sendMessage", json={
                'chat_id': chat_id,
                'text': "🌟 ማርሻሎም የቴክኖሎጂ ረዳት\n\nሰላም! መልእክትዎን ስላደረሱን እናመሰግናለን። በቅርቡ ምላሽ ያገኛሉ።"
            })

        return "OK"
    except Exception as e:
        print(f"Error: {e}")
        return "OK"

# ===== መነሻ =====
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
