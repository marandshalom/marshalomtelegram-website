from flask import Flask, request, jsonify, render_template_string
import requests
import os
import random
import json
from datetime import datetime
import pytz

app = Flask(__name__)

# ===== ከ Render Environment Variables =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
BASE_URL = os.environ.get("BASE_URL", "https://marshalomtelegram-website.onrender.com")
DATABASE_URL = os.environ.get("DATABASE_URL")

# ===== ፓስዎርዶች (ከRender ENV) =====
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "marshalom777")
TEAM_PASSWORD = os.environ.get("TEAM_PASSWORD", "team777")
EMP_PASSWORD = os.environ.get("EMP_PASSWORD", "emp777")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ===== የWebApp HTML (ሙሉ የተሻሻለ) =====
def get_webapp_html():
    social_links = {
        'youtube': 'https://youtube.com/@ShalomTechnology',
        'tiktok': 'https://www.tiktok.com/@marshalomcctv',
        'facebook': 'https://facebook.com/share/1YEeCpFBgp',
        'instagram': 'https://instagram.com/marshalom',
        'telegram': 'https://t.me/MarshalomTech',
        'website': 'https://marshalom.com'
    }
    
    js_code = f"""
    function showPage(id) {{
        document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
        document.getElementById(id).classList.add('active');
        document.getElementById('pagesContainer').scrollTop=0;
        document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
        if(id==='page-home') document.querySelector('.nav-item:nth-child(1)').classList.add('active');
        else if(id==='page-products') document.querySelector('.nav-item:nth-child(2)').classList.add('active');
        else if(id==='page-ai') document.querySelector('.nav-item:nth-child(3)').classList.add('active');
        else if(id==='page-share') document.querySelector('.nav-item:nth-child(4)').classList.add('active');
        else if(id==='page-jobs') document.querySelector('.nav-item:nth-child(5)').classList.add('active');
    }}
    function openSocial(url) {{ window.open(url, '_blank'); }}
    function openAdminLogin() {{
        var pwd = prompt('🔑 የአድሚን የይለፍ ቃል ያስገቡ:');
        if(pwd === '{ADMIN_PASSWORD}') {{ showPage('page-admin'); }} 
        else if(pwd !== null) {{ alert('❌ የተሳሳተ የይለፍ ቃል!'); }}
    }}
    function openEmployeeLogin() {{
        var user = prompt('👤 የተጠቃሚ ስም:');
        var pwd = prompt('🔑 የይለፍ ቃል:');
        if(user === 'teamleader' && pwd === '{TEAM_PASSWORD}') {{ showPage('page-teamleader'); }} 
        else if(user === 'employee' && pwd === '{EMP_PASSWORD}') {{ showPage('page-employee'); }} 
        else {{ alert('❌ የተሳሳተ መረጃ!'); }}
    }}
    function openModal(type) {{
        var titles = {{
            'stats': '📊 ስታቲስቲክስ',
            'products': '🛍️ ምርቶች',
            'customers': '👥 ደንበኞች',
            'addemp': '➕ ሰራተኛ ጨምር',
            'employees': '📋 ሰራተኞች',
            'banks': '🏦 ባንክ',
            'customize': '🎨 ማበጀት',
            'promo': '📢 ማስታወቂያ',
            'cameras': '📹 ካሜራዎች',
            'system': '🔧 ሲስተም'
        }};
        var contents = {{
            'stats': '📈 ዛሬ ጥያቄ: 24<br>📈 አዳዲስ ደንበኛ: 12<br>📈 ጠቅላላ ደንበኛ: 156<br>📈 ዛሬ ሽያጭ: 8<br>📈 ሰራተኞች: 5<br>📈 ካሜራዎች: 10',
            'products': '📦 CALUS VC9 - 4G Solar<br>📦 C92 MAX - Smartwatch<br>📦 IMOU Ranger - Dual Lens<br>📦 Speed Dome - 4MP<br>📦 Stellar AOV - Solar',
            'customers': '👤 አለሙ ተሾመ - 0931556590<br>👤 ሳራ አለሙ - 0912345678<br>👤 ዳዊት ሙሉ - 0923456789<br>... እና 151 ተጨማሪ',
            'addemp': '👤 ሙሉ ስም: _________<br>📧 የተጠቃሚ ስም: _________<br>🔑 የይለፍ ቃል: _________<br>💼 ስራ: _________<br>💰 ደመወዝ: _________<br><br>✅ ሰራተኛ ለመጨመር ቅጽ ተከፈተ!',
            'employees': '👤 አብይ አለሙ - CCTV ቴክኒሽያን<br>👤 ሳራ ተሾመ - የኔትወርክ መሐንዲስ<br>👤 ዳዊት ሙሉ - የሽያጭ ተወካይ<br>👤 ማርያም አለሙ - የሽያጭ ተወካይ<br>👤 ሄኖክ ተሾመ - ቴክኒሽያን',
            'banks': '🏦 ንግድ ባንክ: 1000134567890<br>🏦 አዋሽ ባንክ: 2000245678901<br>🏦 ዳሽን ባንክ: 3000345678902<br>🏦 አብይ ባንክ: 4000456789013',
            'customize': '🎨 የምርት ስሞች መቀየር<br>🎨 የአዝራሮች አዶዎች መቀየር<br>🎨 የመነሻ ገጽ ቀለም መቀየር',
            'promo': '📢 የሳምንቱ ቅናሽ! 10% ቅናሽ!<br>📢 Stellar AOV አዲስ ምርት!<br>📢 C92 MAX 15% ቅናሽ!',
            'cameras': '📷 CALUS VC9 - 4G Solar<br>📷 C92 MAX - Smartwatch<br>📷 IMOU Ranger - Dual Lens<br>📷 Speed Dome - 4MP<br>📷 Stellar AOV - Solar<br>📷 የግቢ ካሜራ<br>📷 የቤት ውስጥ ካሜራ<br>📷 ሶላር ካሜራ<br>📷 የመኪና ካሜራ<br>📷 360° ካሜራ',
            'system': '🔧 ስሪት: v2.0.1<br>🔧 የተሻሻለ: ጁላይ 2026<br>🔧 የደህንነት: ንቁ<br>🔧 የAI ሁኔታ: በመስራት ላይ<br>🔧 የዳታቤዝ: ተገናኝቷል'
        }};
        var modal = document.getElementById('adminModal');
        document.getElementById('adminModalTitle').textContent = titles[type] || '📱 ገጽ';
        document.getElementById('adminModalBody').innerHTML = contents[type] || 'ይህ ገጽ በቅርቡ ይጨመራል!';
        modal.classList.add('show');
    }}
    function closeModal() {{ document.getElementById('adminModal').classList.remove('show'); }}
    function copyText(text) {{
        navigator.clipboard.writeText(text).then(() => {{
            alert('✅ ተቀድቷል!');
        }}).catch(() => {{
            var input = document.createElement('input');
            input.value = text;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            alert('✅ ተቀድቷል!');
        }});
    }}
    """
    
    return f"""
<!DOCTYPE html>
<html lang="am">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ሻሎም ቴክኖሎጂ</title>
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
        .channel-link {{ padding: 8px; background: rgba(74,158,255,0.08); border-radius: 12px; text-align: center; border: 1px dashed #4a9eff; margin-bottom: 10px; cursor: pointer; }}
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
        .btn-primary.gold {{ background: #b8a84a; color: #1a1a2e; }}
        .btn-primary.gold:hover {{ background: #c8b85a; }}
        .modal {{ display: none; background: rgba(0,0,0,0.7); position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 100; justify-content: center; align-items: center; padding: 20px; }}
        .modal.show {{ display: flex; }}
        .modal .content {{ background: #1a2a3a; border-radius: 16px; padding: 20px; max-width: 380px; width: 100%; border: 1px solid #2b3a4a; }}
        .modal .content h3 {{ color: #b8a84a; font-size: 16px; margin-bottom: 12px; }}
        .modal .content p {{ color: #c0d8e8; font-size: 14px; line-height: 1.8; }}
        .modal .content .btn-close {{ background: rgba(255,255,255,0.08); border: none; border-radius: 30px; padding: 10px; color: #fff; font-weight: 600; font-size: 13px; width: 100%; cursor: pointer; margin-top: 12px; transition: 0.2s; }}
        .social-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-top: 6px; }}
        .social-item {{ background: rgba(255,255,255,0.04); border-radius: 12px; padding: 10px 4px; text-align: center; cursor: pointer; border: 1px solid rgba(255,255,255,0.06); transition: 0.25s; }}
        .social-item:hover {{ transform: scale(1.05); border-color: #4a9eff; }}
        .social-item .icon {{ font-size: 24px; display: block; }}
        .social-item .label {{ font-size: 8px; color: #c0d8e8; margin-top: 2px; }}
        .share-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 4px; margin-top: 6px; }}
        .share-item {{ background: rgba(255,255,255,0.04); border-radius: 10px; padding: 8px 2px; text-align: center; cursor: pointer; border: 1px solid rgba(255,255,255,0.06); transition: 0.25s; }}
        .share-item:hover {{ transform: scale(1.05); border-color: #4a9eff; }}
        .share-item .icon {{ font-size: 18px; display: block; }}
        .share-item .label {{ font-size: 7px; color: #c0d8e8; margin-top: 1px; }}
        .dash-card {{ background: rgba(255,255,255,0.04); border-radius: 10px; padding: 10px; text-align: center; cursor: pointer; border: 1px solid rgba(255,255,255,0.06); transition: 0.25s; }}
        .dash-card:hover {{ transform: scale(1.03); border-color: #4a9eff; }}
        .dash-card .icon {{ font-size: 20px; }}
        .dash-card .label {{ color: #c0d8e8; font-size: 9px; margin-top: 2px; }}
        .stat-box {{ background: rgba(255,255,255,0.04); border-radius: 8px; padding: 6px; text-align: center; }}
        .stat-box .num {{ font-size: 16px; font-weight: 700; color: #4a9eff; }}
        .stat-box .num.gold {{ color: #b8a84a; }}
        .stat-box .num.green {{ color: #4ecdc4; }}
        .stat-box .num.red {{ color: #ff6b6b; }}
        .stat-box .label {{ font-size: 7px; color: #8aa3b5; }}
        .bank-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 6px; }}
        .bank-item {{ background: rgba(255,255,255,0.04); border-radius: 12px; padding: 10px; text-align: center; border: 1px solid rgba(255,255,255,0.06); cursor: pointer; transition: 0.25s; }}
        .bank-item:hover {{ transform: scale(1.03); border-color: #4a9eff; }}
        .bank-item .logo {{ font-size: 22px; display: block; }}
        .bank-item .name {{ font-size: 10px; color: #b8a84a; font-weight: 600; }}
        .bank-item .account {{ font-size: 11px; color: #fff; font-weight: 700; letter-spacing: 1px; margin-top: 2px; display: flex; align-items: center; justify-content: center; gap: 6px; }}
        .bank-item .copy-btn {{ background: rgba(255,255,255,0.1); border: none; color: #4a9eff; font-size: 12px; cursor: pointer; padding: 2px 6px; border-radius: 6px; }}
        .bank-item .copy-btn:hover {{ background: rgba(74,158,255,0.2); }}
        .bank-item .account-holder {{ font-size: 8px; color: #8aa3b5; margin-top: 2px; }}
        .news-item {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 8px 10px; margin-bottom: 5px; border-left: 3px solid #4a9eff; }}
        .news-item .title {{ color: #b8a84a; font-weight: 600; font-size: 11px; }}
        .news-item .desc {{ color: #c0d8e8; font-size: 10px; margin-top: 2px; }}
        .compare-option {{ background: rgba(255,255,255,0.04); border-radius: 10px; padding: 6px 10px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center; }}
        .compare-option select {{ background: rgba(255,255,255,0.05); border: 1px solid #2b3a4a; border-radius: 8px; padding: 4px 8px; color: #fff; font-size: 10px; }}
        .job-item {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 8px; margin-bottom: 6px; border-left: 4px solid #4a9eff; }}
        .job-item h3 {{ color: #fff; font-size: 12px; }}
        .job-item p {{ color: #9bb0c0; font-size: 10px; }}
        .tip-item {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 8px; margin-bottom: 4px; }}
        .tip-item .title {{ color: #b8a84a; font-size: 11px; font-weight: 600; }}
        .tip-item .desc {{ color: #c0d8e8; font-size: 10px; margin-top: 2px; }}
        .apply-form input, .apply-form select, .apply-form textarea {{ width: 100%; padding: 8px; margin-bottom: 6px; background: rgba(255,255,255,0.05); border: 1px solid #2b3a4a; border-radius: 8px; color: #fff; font-size: 11px; }}
        .apply-form label {{ color: #c0d8e8; font-size: 10px; display: block; margin-bottom: 2px; }}
        @media (max-width:420px){{.app-container{{border-radius:0;min-height:100vh;}}.bottom-nav{{border-radius:0;}}}}
    </style>
</head>
<body>
<div class="app-container">
    <!-- HEADER -->
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
        <h1 id="mainTitle">ሻሎም ቴክኖሎጂ</h1>
        <div class="sub" id="mainSub">✨ የእርስዎ የደህንነት አጋር ✨</div>
    </div>

    <!-- PAGES -->
    <div class="pages" id="pagesContainer">
        <!-- HOME -->
        <div class="page active" id="page-home">
            <div class="menu-grid">
                <div class="menu-btn" onclick="showPage('page-products')"><span class="icon">🛍️</span><span data-key="m0">ምርቶች</span></div>
                <div class="menu-btn" onclick="showPage('page-call')"><span class="icon">📞</span><span data-key="m1">ይደውሉ</span></div>
                <div class="menu-btn" onclick="showPage('page-social')"><span class="icon">🌐</span><span data-key="m2">ማህበራዊ</span></div>
                <div class="menu-btn" onclick="showPage('page-share')"><span class="icon">👥</span><span data-key="m3">ማጋሪያ</span></div>
                <div class="menu-btn" onclick="showPage('page-news')"><span class="icon">📰</span><span data-key="m4">ዜና</span></div>
                <div class="menu-btn" onclick="showPage('page-compare')"><span class="icon">⚖️</span><span data-key="m5">ንጽጽር</span></div>
                <div class="menu-btn" onclick="showPage('page-jobs')"><span class="icon">💼</span><span data-key="m6">ክፍት ስራ</span></div>
                <div class="menu-btn" onclick="showPage('page-discount')"><span class="icon">🎁</span><span data-key="m7">ቅናሽ</span></div>
                <div class="menu-btn" onclick="showPage('page-ai')"><span class="icon">🤖</span><span data-key="m8">ረዳት</span></div>
                <div class="menu-btn" onclick="showPage('page-support')"><span class="icon">🛡️</span><span data-key="m9">ድጋፍ</span></div>
                <div class="menu-btn" onclick="showPage('page-promo')"><span class="icon">📢</span><span data-key="m10">ማስታወቂያ</span></div>
                <div class="menu-btn" onclick="showPage('page-tips')"><span class="icon">💡</span><span data-key="m11">ምክሮች</span></div>
                <div class="menu-btn" onclick="showPage('page-banks')"><span class="icon">🏦</span><span data-key="m12">ባንክ</span></div>
                <div class="menu-btn" onclick="openAdminLogin()"><span class="icon">🔑</span><span data-key="m14">አድሚን</span></div>
                <div class="menu-btn" onclick="openEmployeeLogin()"><span class="icon">👔</span><span data-key="m15">ቲም ሊደር</span></div>
                <div class="menu-btn" onclick="openEmployeeLogin()"><span class="icon">👤</span><span data-key="m16">ሰራተኛ</span></div>
            </div>
            <div class="promo-banner">
                <span style="font-size:18px;">🔥</span>
                <span class="text" id="promoText">✨ <strong>አዲስ የፀሐይ ካሜራ</strong> 15% ቅናሽ!</span>
                <span class="link" onclick="alert('🔥 ወደ ፕሮሞሽን ገጽ ይወሰዳሉ!')" id="promoLink">ተመልከት</span>
            </div>
            <div style="margin-top:6px; text-align:center; color:#6a8a9e; font-size:9px;">
                📢 ቻናላችን: <a href="https://t.me/MarshalomTech" target="_blank" style="color:#4a9eff; text-decoration:none;">@MarshalomTech</a>
            </div>
        </div>

        <!-- PRODUCTS - 4 PROMOTIONS -->
        <div class="page" id="page-products">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button><span id="pTitle">🛍️ ምርቶች</span></div>
            <div class="product-grid">
                <div class="product-card" style="border: 2px solid #b8a84a;">
                    <div class="promo-img">⭐</div>
                    <div class="info">
                        <div class="name" style="color:#ffd700;">🌟 አዲስ የፀሐይ ካሜራ</div>
                        <div class="desc">4ጂ፣ 360°፣ ባትሪ</div>
                        <button class="ask-btn" onclick="alert('💬 ዋጋ ጥያቄ ተልኳል! በቅርቡ ምላሽ ያገኛሉ!')">💬 15% ቅናሽ!</button>
                    </div>
                </div>
                <div class="product-card">
                    <div class="promo-img">📱</div>
                    <div class="info">
                        <div class="name">📱 ስማርት ሰዓት</div>
                        <div class="desc">6ጂቢ ራም፣ 4ጂ</div>
                        <button class="ask-btn" onclick="alert('💬 ዋጋ ጥያቄ ተልኳል!')">💬 ዋጋ ጠይቁ</button>
                    </div>
                </div>
                <div class="product-card">
                    <div class="promo-img">📷</div>
                    <div class="info">
                        <div class="name">📷 ባለሁለት ሌንስ ካሜራ</div>
                        <div class="desc">10ሜጋፒክስል</div>
                        <button class="ask-btn" onclick="alert('💬 ዋጋ ጥያቄ ተልኳል!')">💬 ዋጋ ጠይቁ</button>
                    </div>
                </div>
                <div class="product-card">
                    <div class="promo-img">🚀</div>
                    <div class="info">
                        <div class="name">🚀 ፈጣን ካሜራ</div>
                        <div class="desc">32x ማጉላት</div>
                        <button class="ask-btn" onclick="alert('💬 ዋጋ ጥያቄ ተልኳል!')">💬 ዋጋ ጠይቁ</button>
                    </div>
                </div>
            </div>
            <div class="promo-banner">
                <span style="font-size:16px;">🔥</span>
                <span class="text" style="font-size:11px;">✨ <strong>ሁሉም ምርቶች 10% ቅናሽ!</strong> ዛሬ ብቻ!</span>
                <span class="link" onclick="alert('🔥 ወደ ፕሮሞሽን ገጽ ይወሰዳሉ!')">ተመልከት</span>
            </div>
            <div class="channel-link">📢 <a href="https://t.me/MarshalomTech" target="_blank">ተጨማሪ ምርቶች ለማየት ቻናላችንን ይቀላቀሉ</a> 📢</div>
        </div>

        <!-- CALL -->
        <div class="page" id="page-call">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>📞 <span id="callTitle">ይደውሉ</span></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:16px; padding:14px 10px; text-align:center; border:2px solid rgba(255,255,255,0.06); cursor:pointer;" onclick="window.location.href='tel:0931556590'">
                    <div style="font-size:14px; font-weight:700; color:#fff;">0931556590</div>
                    <div style="font-size:9px; color:#8aa3b5;">ኢትዮ ቴሌኮም</div>
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:16px; padding:14px 10px; text-align:center; border:2px solid rgba(255,255,255,0.06); cursor:pointer;" onclick="window.location.href='tel:+251799556590'">
                    <div style="font-size:14px; font-weight:700; color:#fff;">+251799556590</div>
                    <div style="font-size:9px; color:#8aa3b5;">ሳፋሪኮም</div>
                </div>
            </div>
        </div>

        <!-- SOCIAL -->
        <div class="page" id="page-social">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🌐 <span id="socialTitle">ማህበራዊ ሚዲያ</span></div>
            <div class="social-grid">
                <div class="social-item" onclick="openSocial('{social_links['youtube']}')"><span class="icon">▶️</span><span class="label">YouTube</span></div>
                <div class="social-item" onclick="openSocial('{social_links['tiktok']}')"><span class="icon">🎵</span><span class="label">TikTok</span></div>
                <div class="social-item" onclick="openSocial('{social_links['facebook']}')"><span class="icon">📘</span><span class="label">Facebook</span></div>
                <div class="social-item" onclick="openSocial('{social_links['instagram']}')"><span class="icon">📸</span><span class="label">Instagram</span></div>
                <div class="social-item" onclick="openSocial('{social_links['telegram']}')"><span class="icon">✈️</span><span class="label">ቴሌግራም</span></div>
                <div class="social-item" onclick="openSocial('{social_links['website']}')"><span class="icon">🌐</span><span class="label">ድር ጣቢያ</span></div>
            </div>
        </div>

        <!-- SHARE -->
        <div class="page" id="page-share">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>👥 <span id="shareTitle">ማጋሪያ</span></div>
            <div style="background:rgba(74,158,255,0.04); border-radius:12px; padding:10px; margin-top:8px; border:1px solid rgba(74,158,255,0.06); font-size:11px; color:#c0d8e8; line-height:1.6;">
                <div style="color:#b8a84a; font-weight:700; font-size:13px; text-align:center;">✨ እንኳን ደህና መጡ ወደ ማርሻሎም! ✨</div>
                <span>ይህንን ቦት ለጓደኞችዎ ያጋሩ!</span>
            </div>
            <div class="share-grid">
                <div class="share-item" onclick="navigator.share?navigator.share({{title:'ሻሎም ቴክኖሎጂ',text:'ይህንን ቦት ይጠቀሙ!',url:'https://t.me/MarshalomTech'}}):alert('📤 ማጋሪያ ተከፈተ!')"><span class="icon">💬</span><span class="label">WhatsApp</span></div>
                <div class="share-item" onclick="navigator.share?navigator.share({{title:'ሻሎም ቴክኖሎጂ',text:'ይህንን ቦት ይጠቀሙ!',url:'https://t.me/MarshalomTech'}}):alert('📤 ማጋሪያ ተከፈተ!')"><span class="icon">📘</span><span class="label">Facebook</span></div>
                <div class="share-item" onclick="navigator.share?navigator.share({{title:'ሻሎም ቴክኖሎጂ',text:'ይህንን ቦት ይጠቀሙ!',url:'https://t.me/MarshalomTech'}}):alert('📤 ማጋሪያ ተከፈተ!')"><span class="icon">✈️</span><span class="label">Telegram</span></div>
                <div class="share-item" onclick="navigator.share?navigator.share({{title:'ሻሎም ቴክኖሎጂ',text:'ይህንን ቦት ይጠቀሙ!',url:'https://t.me/MarshalomTech'}}):alert('📤 ማጋሪያ ተከፈተ!')"><span class="icon">📸</span><span class="label">Instagram</span></div>
                <div class="share-item" onclick="navigator.share?navigator.share({{title:'ሻሎም ቴክኖሎጂ',text:'ይህንን ቦት ይጠቀሙ!',url:'https://t.me/MarshalomTech'}}):alert('📤 ማጋሪያ ተከፈተ!')"><span class="icon">🎵</span><span class="label">TikTok</span></div>
                <div class="share-item" onclick="navigator.share?navigator.share({{title:'ሻሎም ቴክኖሎጂ',text:'ይህንን ቦት ይጠቀሙ!',url:'https://t.me/MarshalomTech'}}):alert('📤 ማጋሪያ ተከፈተ!')"><span class="icon">💼</span><span class="label">LinkedIn</span></div>
                <div class="share-item" onclick="navigator.share?navigator.share({{title:'ሻሎም ቴክኖሎጂ',text:'ይህንን ቦት ይጠቀሙ!',url:'https://t.me/MarshalomTech'}}):alert('📤 ማጋሪያ ተከፈተ!')"><span class="icon">🐦</span><span class="label">Twitter</span></div>
                <div class="share-item" onclick="copyText('https://t.me/MarshalomTech')"><span class="icon">🔗</span><span class="label">ሊንክ</span></div>
            </div>
        </div>

        <!-- NEWS - 10 FUN NEWS -->
        <div class="page" id="page-news">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>📰 <span id="newsTitle">ዜና</span></div>
            <div class="news-item"><div class="title">📸 አዲስ ካሜራ ፊት ብቻ ሳይሆን የእግር ንዝረትን ይለያል!</div><div class="desc">የቻይና ኩባንያ አዲስ AI ካሜራ አስገባ — ሰዎችን በእግራቸው እንቅስቃሴ ይለያል! 🦶</div></div>
            <div class="news-item"><div class="title">🚀 በአሜሪካ የሰማይ ላይ ካሜራ ተፈተሸ</div><div class="desc">ሰዎችን ከ5 ኪሎ ሜትር ርቀት የሚያውቅ ካሜራ ተፈተሸ! 🌍</div></div>
            <div class="news-item"><div class="title">😂 አስቂኝ — "777" የማርሻሎም ምስጢር!</div><div class="desc">ማርሻሎም ለቦቱ ፓስዎርድ "777" አድርጎታል! እስካሁን ምስጢሩን አላወቀም! 🤫😂</div></div>
            <div class="news-item"><div class="title">🤖 AI አሁን የሰውን ስሜት ይረዳል!</div><div class="desc">አዲስ AI የተጠቃሚውን ስሜት በመለየት ምላሽ ይሰጣል! 😊</div></div>
            <div class="news-item"><div class="title">📱 የሚታጠፍ ስማርትፎን ተለቀቀ!</div><div class="desc">አዲሱ የሚታጠፍ ስማርትፎን አሁን በገበያ ላይ ይገኛል! 📱</div></div>
            <div class="news-item"><div class="title">🔒 አዲስ የደህንነት ስርዓት ተፈተሸ</div><div class="desc">የፊት መለያ እና የዓይን መለያ አንድ ላይ የሚሰራ ስርዓት! 👁️</div></div>
            <div class="news-item"><div class="title">🌞 ሶላር ካሜራ ከ10 ዓመት ባትሪ</div><div class="desc">አዲስ ሶላር ካሜራ ሙሉ በሙሉ በፀሐይ የሚሰራ እና የማይጠፋ ባትሪ አለው! ☀️</div></div>
            <div class="news-item"><div class="title">🎮 ካሜራ በጨዋታ ቁጥጥር!</div><div class="desc">አዲሱ ካሜራ በጨዋታ መቆጣጠሪያ ሊቆጣጠሩት ይችላሉ! 🎮</div></div>
            <div class="news-item"><div class="title">🐶 ካሜራ የቤት እንስሳትን ይከታተላል!</div><div class="desc">አዲስ ካሜራ የቤት እንስሳትን እንቅስቃሴ ይከታተላል እና ሪፖርት ያደርጋል! 🐕</div></div>
            <div class="news-item"><div class="title">💡 በማስተዋል የሚሰራ መብራት!</div><div class="desc">ካሜራ ሰው ሲያይ መብራቱን በራሱ ያበራል! 💡</div></div>
        </div>

        <!-- COMPARE -->
        <div class="page" id="page-compare">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>⚖️ <span id="compareTitle">ንጽጽር</span></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:6px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; border:1px solid rgba(255,255,255,0.06);">
                    <div class="compare-option"><span style="color:#8aa3b5; font-size:10px;">ካሜራ 1</span><select><option>CALUS VC9</option><option>C92 MAX</option><option>Speed Dome</option></select></div>
                    <div class="compare-option"><span style="color:#8aa3b5; font-size:10px;">ካሜራ 2</span><select><option>Speed Dome</option><option>IMOU Ranger</option><option>Stellar AOV</option></select></div>
                    <button class="btn-primary" style="margin-top:4px; padding:6px; font-size:11px;" onclick="alert('📊 ንጽጽር ውጤት እዚህ ይታያል!')">🔍 አወዳድር</button>
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; border:1px solid rgba(255,255,255,0.06);">
                    <div style="color:#b8a84a; font-weight:600; font-size:11px; text-align:center;">📊 ውጤት</div>
                    <div style="color:#c0d8e8; font-size:10px; padding:4px 0; text-align:center;">ካሜራዎችን ይምረጡ!</div>
                </div>
            </div>
        </div>

        <!-- JOBS -->
        <div class="page" id="page-jobs">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>💼 <span id="jobsTitle">ክፍት ስራ</span></div>
            <div class="job-item"><h3>📹 የCCTV ተከላ ቴክኒሽያን</h3><p>አዲስ አበባ — ልምድ ያለው</p></div>
            <div class="job-item"><h3>💻 የኔትወርክ መሐንዲስ</h3><p>ለድርጅቶች ኔትወርክ መጫን</p></div>
            <div class="promo-banner" style="margin-top:6px;">
                <span style="font-size:14px;">🔥</span>
                <span class="text" style="font-size:10px;">✨ <strong>አሁን ተቀላቀሉ!</strong> አዳዲስ ስራዎች በቅርቡ ይጨመራሉ!</span>
                <span class="link" onclick="alert('📢 ለወቅታዊ ማስታወቂያዎች ቻናላችንን ይቀላቀሉ!')">ተመልከት</span>
            </div>
            <button class="btn-primary" onclick="showPage('page-apply')">📝 አሁን አመልክት</button>
        </div>

        <!-- APPLY FORM -->
        <div class="page" id="page-apply">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-jobs')">‹</button>📝 ማመልከቻ</div>
            <div class="apply-form">
                <label>👤 ሙሉ ስም</label>
                <input type="text" placeholder="ሙሉ ስምዎ">
                <label>📱 ስልክ ቁጥር</label>
                <input type="tel" placeholder="09xxxxxxxx">
                <label>📧 ኢሜይል</label>
                <input type="email" placeholder="ኢሜይልዎ">
                <label>🎓 የትምህርት ደረጃ</label>
                <select><option>ዲፕሎማ</option><option>ባችለር</option><option>ማስተርስ</option></select>
                <label>📄 የመታወቂያ (ID) ፎቶ</label>
                <input type="file" accept="image/*" style="padding:6px;">
                <label>📄 የትምህርት ሰርተፊኬት</label>
                <input type="file" accept=".pdf,.jpg,.png" style="padding:6px;">
                <label>📝 ተጨማሪ መረጃ</label>
                <textarea rows="3" placeholder="ስለ እርስዎ ተጨማሪ መረጃ..."></textarea>
                <button class="btn-primary gold" onclick="alert('✅ ማመልከቻዎ ተልኳል! በቅርቡ እናገኝዎታለን!')">📨 አሁን አመልክት</button>
            </div>
        </div>

        <!-- DISCOUNT -->
        <div class="page" id="page-discount">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🎁 <span id="discountTitle">ቅናሽ</span></div>
            <div style="background:linear-gradient(135deg,#4a3a1a,#3a2a0a); border-radius:16px; padding:20px 12px; text-align:center; color:#b8a84a; border:1px solid #4a3a1a;">
                <div style="font-size:30px;">🎉</div>
                <div style="font-size:15px; font-weight:700;">እንኳን ደስ አለዎት!</div>
                <div style="font-size:28px; font-weight:900;">15%</div>
                <div style="font-size:13px; color:#c0d8e8;">ቅናሽ ለ <strong>C92 MAX</strong></div>
                <button class="btn-primary gold" style="margin-top:6px;" onclick="alert('🎁 ቅናሽ ተቀብለዋል! አድሚን ያግኙ!')">ቅናሹን አግኙ</button>
            </div>
            <div class="promo-banner" style="margin-top:6px;">
                <span style="font-size:14px;">🔥</span>
                <span class="text" style="font-size:10px;">✨ <strong>ሌሎች ቅናሾች:</strong> ሁሉም ምርቶች 10% ቅናሽ!</span>
                <span class="link" onclick="alert('📢 ለወቅታዊ ማስታወቂያዎች ቻናላችንን ይቀላቀሉ!')">ተመልከት</span>
            </div>
        </div>

        <!-- AI -->
        <div class="page" id="page-ai">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🤖 <span id="aiTitle">ረዳት</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:14px; padding:12px 10px; border:1px solid rgba(255,215,0,0.06);">
                <div style="color:#b8a84a; font-size:14px; font-weight:700; text-align:center;">🌟 ማርሻሎም የቴክኖሎጂ ረዳት 🌟</div>
                <div style="color:#c0d8e8; font-size:11px; line-height:1.6; margin-top:4px;">ሰላም! መልእክትዎን ስላደረሱን እናመሰግናለን። 🙏<br>አሁን ላይ እጅግ በጣም ብዙ ጥያቄዎችን በማስተናገድ ላይ ስለሆንን፣ ትክክለኛ ምላሽ ለእርስዎ ለመስጠት ፍቃድ በመጠበቅ ላይ እገኛለሁ። ⏳<br>አትጨነቁ! መልእክትዎ በአስተማማኝ ሁኔታ ተይዟል። 🤝✨</div>
                <div style="background:rgba(255,0,0,0.06); border-left:4px solid #ff4444; padding:5px; border-radius:5px; margin-top:5px; font-size:10px; color:#ffaaaa;"><strong>⚠️ አስቸኳይ ከሆነ:</strong> "አስቸኳይ" ብለው ይጻፉ። ወደ ማርሻሎም ይላካል! 📞</div>
                <button class="btn-primary" style="margin-top:6px; background:transparent; border:1px solid #4a9eff; color:#4a9eff;" onclick="alert('📨 አስቸኳይ መልእክት ለማርሻሎም ተልኳል!')">📨 አስቸኳይ ላክ</button>
            </div>
        </div>

        <!-- SUPPORT -->
        <div class="page" id="page-support">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🛡️ <span id="supportTitle">ድጋፍ</span></div>
            <div style="text-align:center;">
                <div style="font-size:32px;">🛡️</div>
                <p style="color:#c0d8e8; font-size:13px; font-weight:600;">24/7 ደንበኛ ድጋፍ</p>
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-top:6px;">
                    <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="window.location.href='tel:0931556590'"><span style="font-size:28px; display:block;">📞</span><span style="font-size:9px; color:#c0d8e8;">ስልክ</span><span style="font-size:8px; color:#8aa3b5;">0931556590</span></div>
                    <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="window.open('https://wa.me/251799556590','_blank')"><span style="font-size:28px; display:block;">💬</span><span style="font-size:9px; color:#c0d8e8;">ዋትሳፕ</span><span style="font-size:8px; color:#8aa3b5;">+251799556590</span></div>
                    <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:10px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06);" onclick="window.open('https://t.me/MarshalomTech','_blank')"><span style="font-size:28px; display:block;">✈️</span><span style="font-size:9px; color:#c0d8e8;">ቴሌግራም</span><span style="font-size:8px; color:#8aa3b5;">@MarshalomTech</span></div>
                </div>
                <button class="btn-primary" style="margin-top:6px;" onclick="window.location.href='tel:0931556590'">📞 ወዲያው ይደውሉ</button>
            </div>
        </div>

        <!-- PROMO -->
        <div class="page" id="page-promo">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>📢 <span id="promoTitle">ማስታወቂያ</span></div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; border-left:4px solid #4a9eff; margin-bottom:4px;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">📢 የሳምንቱ ቅናሽ!</div>
                <div style="color:#c0d8e8; font-size:11px;">ሁሉም CCTV ካሜራዎች 10% ቅናሽ! ዛሬ ብቻ!</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; border-left:4px solid #b8a84a; margin-bottom:4px;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">🎉 አዲስ ምርት!</div>
                <div style="color:#c0d8e8; font-size:11px;">Stellar AOV Solar Camera — አሁን ተገኝቷል!</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; border-left:4px solid #ff6b6b; margin-bottom:4px;">
                <div style="color:#ff6b6b; font-weight:600; font-size:11px;">🔥 ፍጥነት!</div>
                <div style="color:#c0d8e8; font-size:11px;">ለመጀመሪያ 10 ደንበኞች 20% ቅናሽ!</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; border-left:4px solid #4ecdc4;">
                <div style="color:#4ecdc4; font-weight:600; font-size:11px;">🎁 የልደት ቅናሽ!</div>
                <div style="color:#c0d8e8; font-size:11px;">የልደት ወር ላይ ሁሉም ምርቶች 15% ቅናሽ!</div>
            </div>
        </div>

        <!-- TIPS - 12 TIPS -->
        <div class="page" id="page-tips">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>💡 <span id="tipsTitle">ምክሮች</span></div>
            <div class="tip-item"><div class="title">💡 ምክር 1</div><div class="desc">ካሜራ ሲጭኑ የፀሐይ ብርሃን ወደሚያገኝ ቦታ ይጫኑ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 2</div><div class="desc">የካሜራ ስርዓትን በየጊዜው ያሻሽሉ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 3</div><div class="desc">ካሜራ በሚጭኑበት ጊዜ የWiFi ሲግናል ጠንካራ መሆኑን ያረጋግጡ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 4</div><div class="desc">የካሜራ ማህደረ ትውስታ (SD Card) በየጊዜው ያጽዱ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 5</div><div class="desc">የካሜራ ስርዓትን ከስልክዎ ጋር በማገናኘት የርቀት ቁጥጥር ያድርጉ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 6</div><div class="desc">ካሜራ በሚጭኑበት ጊዜ የመጀመሪያ ሙከራ ያድርጉ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 7</div><div class="desc">የካሜራ ስርዓትን ከሌሎች የደህንነት መሳሪያዎች ጋር ያገናኙ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 8</div><div class="desc">የካሜራ ፓስዎርድን በየጊዜው ይቀይሩ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 9</div><div class="desc">ካሜራ በሚጭኑበት ጊዜ የኤሌክትሪክ ገመድ በደህና መሆኑን ያረጋግጡ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 10</div><div class="desc">የካሜራ ስርዓትን ለረጅም ጊዜ ካልተጠቀሙ አጥፉት!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 11</div><div class="desc">ካሜራ በሚጭኑበት ጊዜ የሙቀት መጠኑን ያረጋግጡ!</div></div>
            <div class="tip-item"><div class="title">💡 ምክር 12</div><div class="desc">የካሜራ ስርዓትን በየጊዜው ያፅዱ እና ያጽዱ!</div></div>
        </div>

        <!-- BANKS -->
        <div class="page" id="page-banks">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>🏦 <span id="banksTitle">ባንክ ሂሳቦች</span></div>
            <div class="bank-grid">
                <div class="bank-item" onclick="copyText('1000453578058')">
                    <span class="logo">🏦</span>
                    <div class="name">ንግድ ባንክ</div>
                    <div class="account"><span>1000453578058</span><button class="copy-btn" onclick="event.stopPropagation();copyText('1000453578058')">📋</button></div>
                    <div class="account-holder">👤 Marshalom Tesfay</div>
                </div>
                <div class="bank-item" onclick="copyText('0931556590')">
                    <span class="logo">💳</span>
                    <div class="name">ቴሌብር 1</div>
                    <div class="account"><span>0931556590</span><button class="copy-btn" onclick="event.stopPropagation();copyText('0931556590')">📋</button></div>
                    <div class="account-holder">👤 Marshalom Tesfay</div>
                </div>
                <div class="bank-item" onclick="copyText('0967386958')">
                    <span class="logo">💳</span>
                    <div class="name">ቴሌብር 2</div>
                    <div class="account"><span>0967386958</span><button class="copy-btn" onclick="event.stopPropagation();copyText('0967386958')">📋</button></div>
                    <div class="account-holder">👤 Lwam Alem</div>
                </div>
                <div class="bank-item" onclick="copyText('01320877386700')">
                    <span class="logo">🏦</span>
                    <div class="name">አዋሽ ባንክ 1</div>
                    <div class="account"><span>01320877386700</span><button class="copy-btn" onclick="event.stopPropagation();copyText('01320877386700')">📋</button></div>
                    <div class="account-holder">👤 Marshalom Tesfay</div>
                </div>
                <div class="bank-item" onclick="copyText('01320779250100')">
                    <span class="logo">🏦</span>
                    <div class="name">አዋሽ ባንክ 2</div>
                    <div class="account"><span>01320779250100</span><button class="copy-btn" onclick="event.stopPropagation();copyText('01320779250100')">📋</button></div>
                    <div class="account-holder">👤 Lwam Alem</div>
                </div>
            </div>
        </div>

        <!-- ADMIN -->
        <div class="page" id="page-admin">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>⚙️ አድሚን</div>
            <div style="background:rgba(74,158,255,0.06); border-radius:14px; padding:12px; text-align:center; border:1px solid rgba(74,158,255,0.06); margin-bottom:8px;">
                <span style="font-size:36px; display:block;">👑</span>
                <div style="font-size:16px; font-weight:700; color:#fff;">ማርሻሎም</div>
                <div style="font-size:10px; color:#b8a84a;">🚀 ባለቤት</div>
                <div style="font-size:9px; color:#8aa3b5;">ሙሉ የስርዓት ቁጥጥር</div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:4px; margin-bottom:6px;">
                <div class="stat-box"><div class="num">24</div><div class="label">ዛሬ ጥያቄ</div></div>
                <div class="stat-box"><div class="num gold">12</div><div class="label">አዳዲስ</div></div>
                <div class="stat-box"><div class="num green">156</div><div class="label">ደንበኞች</div></div>
                <div class="stat-box"><div class="num red">8</div><div class="label">ዛሬ ሽያጭ</div></div>
                <div class="stat-box"><div class="num gold">5</div><div class="label">ሰራተኞች</div></div>
                <div class="stat-box"><div class="num">10</div><div class="label">ካሜራዎች</div></div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px;">
                <div class="dash-card" onclick="openModal('stats')"><span class="icon">📊</span><div class="label">ስታቲስቲክስ</div></div>
                <div class="dash-card" onclick="openModal('products')"><span class="icon">🛍️</span><div class="label">ምርቶች</div></div>
                <div class="dash-card" onclick="openModal('customers')"><span class="icon">👥</span><div class="label">ደንበኞች</div></div>
                <div class="dash-card" onclick="openModal('addemp')"><span class="icon">➕</span><div class="label">ሰራተኛ ጨምር</div></div>
                <div class="dash-card" onclick="openModal('employees')"><span class="icon">📋</span><div class="label">ሰራተኞች</div></div>
                <div class="dash-card" onclick="openModal('banks')"><span class="icon">🏦</span><div class="label">ባንክ</div></div>
                <div class="dash-card" onclick="openModal('customize')"><span class="icon">🎨</span><div class="label">ማበጀት</div></div>
                <div class="dash-card" onclick="openModal('promo')"><span class="icon">📢</span><div class="label">ማስታወቂያ</div></div>
                <div class="dash-card" onclick="openModal('cameras')"><span class="icon">📹</span><div class="label">ካሜራዎች</div></div>
                <div class="dash-card" onclick="openModal('system')"><span class="icon">🔧</span><div class="label">ሲስተም</div></div>
            </div>
            <div style="margin-top:8px; background:rgba(255,255,255,0.03); border-radius:10px; padding:8px;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">🔑 የይለፍ ቃል ማመንጨት</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px; margin-top:4px;">
                    <button class="btn-primary" style="padding:6px; font-size:10px; background:#b8a84a; color:#1a1a2e;" onclick="alert('🔑 አዲስ ፓስዎርድ ተፈጥሯል!')">🔑 አዲስ ፓስዎርድ</button>
                    <button class="btn-primary" style="padding:6px; font-size:10px; background:#ff6b6b; color:#fff;" onclick="alert('🔑 ሰራተኛ ፓስዎርድ ዳግም ተጀምሯል!')">🔄 ዳግም አስጀምር</button>
                </div>
            </div>
        </div>

        <!-- TEAM LEADER -->
        <div class="page" id="page-teamleader">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>👔 ቲም ሊደር</div>
            <div style="background:rgba(74,158,255,0.06); border-radius:14px; padding:12px; text-align:center; border:1px solid rgba(74,158,255,0.06); margin-bottom:8px;">
                <span style="font-size:36px; display:block;">👔</span>
                <div style="font-size:16px; font-weight:700; color:#fff;">የናስ ሞላ</div>
                <div style="font-size:10px; color:#b8a84a;">🌟 የቡድን አስተዳደር</div>
                <div style="font-size:9px; color:#8aa3b5;">የእርስዎ የደህንነት አጋር</div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:4px; margin-bottom:6px;">
                <div class="stat-box"><div class="num">12</div><div class="label">የቡድን ስራ</div></div>
                <div class="stat-box"><div class="num green">8</div><div class="label">ተጠናቀቀ</div></div>
                <div class="stat-box"><div class="num gold">4</div><div class="label">በመሄድ</div></div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px;">
                <div class="dash-card" onclick="alert('👤 ሰራተኞች ተከፈተ')"><span class="icon">👤</span><div class="label">ሰራተኞች</div></div>
                <div class="dash-card" onclick="alert('📋 ስራ መመደብ ተከፈተ')"><span class="icon">📋</span><div class="label">ስራ መመደብ</div></div>
                <div class="dash-card" onclick="alert('📊 ሪፖርት 1 ተከፈተ')"><span class="icon">📊</span><div class="label">ሪፖርት 1</div></div>
                <div class="dash-card" onclick="alert('📈 ሪፖርት 2 ተከፈተ')"><span class="icon">📈</span><div class="label">ሪፖርት 2</div></div>
                <div class="dash-card" onclick="alert('🔑 የይለፍ ቃል ማመንጨት ተከፈተ')"><span class="icon">🔑</span><div class="label">ፓስዎርድ አመንጭ</div></div>
                <div class="dash-card" onclick="alert('⚠️ ማስጠንቀቂያ ተከፈተ')"><span class="icon">⚠️</span><div class="label">ማስጠንቀቂያ</div></div>
                <div class="dash-card" onclick="alert('🚫 ማባረር ተከፈተ')"><span class="icon">🚫</span><div class="label">ማባረር</div></div>
                <div class="dash-card" onclick="alert('📝 መልእክት ላክ ተከፈተ')"><span class="icon">📝</span><div class="label">መልእክት ላክ</div></div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:8px; margin-top:6px;">
                <div style="color:#b8a84a; font-weight:600; font-size:11px;">📋 የቡድን ስራዎች</div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">📹 C92 MAX መጫን <span style="float:right; color:#4ecdc4;">✅ አለቀ</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">☀️ ሶላር ካሜራ ተከላ <span style="float:right; color:#b8a84a;">⏳ በመሄድ</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);">📅 የደንበኛ ቀጠሮ <span style="float:right; color:#ff6b6b;">🔴 10:00</span></div>
                <div style="color:#c0d8e8; font-size:10px; padding:2px 0;">🛠️ የኔትወርክ ጥገና <span style="float:right; color:#b8a84a;">⏳ በመሄድ</span></div>
            </div>
        </div>

        <!-- EMPLOYEE -->
        <div class="page" id="page-employee">
            <div class="page-title"><button class="back-btn" onclick="showPage('page-home')">‹</button>👤 ሰራተኛ</div>
            <div style="background:rgba(74,158,255,0.06); border-radius:14px; padding:12px; text-align:center; border:1px solid rgba(74,158,255,0.06); margin-bottom:8px;">
                <span style="font-size:36px; display:block;">👤</span>
                <div style="font-size:16px; font-weight:700; color:#fff;">አብይ አለሙ</div>
                <div style="font-size:10px; color:#b8a84a;">CCTV ቴክኒሽያን</div>
                <div style="font-size:9px; color:#8aa3b5;">⭐ ⭐ ⭐ ⭐ ⭐ (4.8)</div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:5px; margin-bottom:6px;">
                <div class="stat-box"><div class="num green">12,500</div><div class="label">ኮሚሽን</div></div>
                <div class="stat-box"><div class="num blue">8</div><div class="label">ተጠናቀቁ</div></div>
                <div class="stat-box"><div class="num">3</div><div class="label">በመሄድ</div></div>
            </div>
            <div style="background:rgba(255,255,255,0.03); border-radius:8px; padding:8px; margin-bottom:4px;">
                <div style="display:flex; justify-content:space-between; color:#c0d8e8; font-size:10px; padding:2px 0;"><span style="color:#8aa3b5;">ስራ</span><span>CCTV ቴክኒሽያን</span></div>
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

    <!-- BOTTOM NAV -->
    <div class="bottom-nav">
        <div class="nav-item active" onclick="showPage('page-home')"><span class="icon">🏠</span><span data-key="n0">መነሻ</span></div>
        <div class="nav-item" onclick="showPage('page-products')"><span class="icon">🛍️</span><span data-key="n1">ምርቶች</span></div>
        <div class="nav-item" onclick="showPage('page-ai')"><span class="icon">🤖</span><span data-key="n2">ረዳት</span></div>
        <div class="nav-item" onclick="showPage('page-share')"><span class="icon">👥</span><span data-key="n3">አጋራ</span></div>
        <div class="nav-item" onclick="showPage('page-jobs')"><span class="icon">💼</span><span data-key="n4">ስራ</span></div>
    </div>

    <!-- ADMIN MODAL -->
    <div class="modal" id="adminModal">
        <div class="content">
            <h3 id="adminModalTitle">📊 ስታቲስቲክስ</h3>
            <p id="adminModalBody">ይህ የስታቲስቲክስ ገጽ ነው!</p>
            <button class="btn-close" onclick="closeModal()">✖ ዝጋ</button>
        </div>
    </div>
</div>
<script>
    {js_code}
    // ===== LANGUAGE SWITCHER =====
    var translations = {{
        'am': {{
            'title': 'ሻሎም ቴክኖሎጂ',
            'sub': '✨ የእርስዎ የደህንነት አጋር ✨',
            'm0':'ምርቶች','m1':'ይደውሉ','m2':'ማህበራዊ','m3':'ማጋሪያ','m4':'ዜና','m5':'ንጽጽር','m6':'ክፍት ስራ','m7':'ቅናሽ','m8':'ረዳት','m9':'ድጋፍ','m10':'ማስታወቂያ','m11':'ምክሮች','m12':'ባንክ','m14':'አድሚን','m15':'ቲም ሊደር','m16':'ሰራተኛ',
            'promo':'✨ <strong>አዲስ የፀሐይ ካሜራ</strong> 15% ቅናሽ!',
            'promoLink':'ተመልከት',
            'n0':'መነሻ','n1':'ምርቶች','n2':'ረዳት','n3':'አጋራ','n4':'ስራ',
            'pTitle':'🛍️ ምርቶች',
            'callTitle':'ይደውሉ',
            'socialTitle':'ማህበራዊ ሚዲያ',
            'shareTitle':'ማጋሪያ',
            'newsTitle':'ዜና',
            'compareTitle':'ንጽጽር',
            'jobsTitle':'ክፍት ስራ',
            'discountTitle':'ቅናሽ',
            'aiTitle':'ረዳት',
            'supportTitle':'ድጋፍ',
            'promoTitle':'ማስታወቂያ',
            'tipsTitle':'ምክሮች',
            'banksTitle':'ባንክ ሂሳቦች'
        }},
        'en': {{
            'title': 'Shalom Technology',
            'sub': '✨ Your Security Partner ✨',
            'm0':'Products','m1':'Call','m2':'Social','m3':'Share','m4':'News','m5':'Compare','m6':'Jobs','m7':'Discount','m8':'Assistant','m9':'Support','m10':'Promo','m11':'Tips','m12':'Banks','m14':'Admin','m15':'Team Leader','m16':'Employee',
            'promo':'✨ <strong>New Solar Camera</strong> 15% OFF!',
            'promoLink':'View',
            'n0':'Home','n1':'Products','n2':'Assistant','n3':'Share','n4':'Jobs',
            'pTitle':'🛍️ Products',
            'callTitle':'Call',
            'socialTitle':'Social Media',
            'shareTitle':'Share',
            'newsTitle':'News',
            'compareTitle':'Compare',
            'jobsTitle':'Jobs',
            'discountTitle':'Discount',
            'aiTitle':'Assistant',
            'supportTitle':'Support',
            'promoTitle':'Promo',
            'tipsTitle':'Tips',
            'banksTitle':'Banks'
        }}
    }};
    function switchLanguage(lang) {{
        document.querySelectorAll('#langSelector button').forEach(b=>b.classList.remove('active'));
        document.querySelector('#langSelector button[data-lang=\"'+lang+'\"]').classList.add('active');
        var t = translations[lang];
        if(!t) return;
        document.getElementById('mainTitle').textContent = t.title;
        document.getElementById('mainSub').textContent = t.sub;
        document.querySelectorAll('#page-home .menu-btn [data-key]').forEach(el=>{{
            var key = el.dataset.key;
            if(t[key]) el.textContent = t[key];
        }});
        document.getElementById('promoText').innerHTML = t.promo;
        document.getElementById('promoLink').textContent = t.promoLink;
        document.querySelectorAll('.bottom-nav .nav-item [data-key]').forEach(el=>{{
            var key = el.dataset.key;
            if(t[key]) el.textContent = t[key];
        }});
        document.getElementById('pTitle').textContent = t.pTitle;
        document.getElementById('callTitle').textContent = t.callTitle;
        document.getElementById('socialTitle').textContent = t.socialTitle;
        document.getElementById('shareTitle').textContent = t.shareTitle;
        document.getElementById('newsTitle').textContent = t.newsTitle;
        document.getElementById('compareTitle').textContent = t.compareTitle;
        document.getElementById('jobsTitle').textContent = t.jobsTitle;
        document.getElementById('discountTitle').textContent = t.discountTitle;
        document.getElementById('aiTitle').textContent = t.aiTitle;
        document.getElementById('supportTitle').textContent = t.supportTitle;
        document.getElementById('promoTitle').textContent = t.promoTitle;
        document.getElementById('tipsTitle').textContent = t.tipsTitle;
        document.getElementById('banksTitle').textContent = t.banksTitle;
    }}
</script>
</body>
</html>
    """

# ===== የWebApp ገጽ =====
@app.route('/webapp')
def webapp():
    return render_template_string(get_webapp_html())

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
        text = msg.get('text', '')

        if text == '/start':
            webapp_url = f"{BASE_URL}/webapp"
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

        # AI Reply
        if DEEPSEEK_API_KEY:
            try:
                response = requests.post(
                    "https://api.deepseek.com/chat/completions",
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "አንተ Marshalom AI ነህ — የ Shalom Technology ረዳት። በአማርኛ መልስ ስጥ።"},
                            {"role": "user", "content": text}
                        ],
                        "max_tokens": 300
                    },
                    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                    timeout=25
                )
                if response.status_code == 200:
                    ai_reply = response.json()["choices"][0]["message"]["content"]
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
            except:
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
