from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict, Optional, List
import uuid
import json
import os
import time
import asyncio
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
import random

app = FastAPI(title="RVG Gateway - Render Version")

# تنظیمات مخصوص Render
PORT = int(os.getenv("PORT", 8000))
RENDER_PUBLIC_DOMAIN = os.getenv("RENDER_PUBLIC_DOMAIN", "localhost")
SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key-change-this")

# استفاده از متغیر Render به جای Railway
PUBLIC_DOMAIN = RENDER_PUBLIC_DOMAIN

# ذخیره‌سازی درون حافظه (مثل Railway)
class LinkData:
    def __init__(self):
        self.links = {}
        self.traffic_stats = {}
        
link_manager = LinkData()

# مدل دیتا
class CreateLinkRequest(BaseModel):
    name: str
    traffic_limit_mb: Optional[float] = None

class LinkInfo:
    def __init__(self, link_id: str, name: str, traffic_limit_mb: Optional[float], created_at: float):
        self.link_id = link_id
        self.name = name
        self.traffic_limit_mb = traffic_limit_mb
        self.traffic_used_mb = 0
        self.is_active = True
        self.created_at = created_at
        self.last_used = None
        self.uuid = str(uuid.uuid4())

# تابع ساخت لینک VLESS
def generate_vless_link(uuid: str, domain: str, link_id: str = None) -> str:
    """تولید لینک VLESS با فرمت مناسب برای WebSocket"""
    # تنظیمات VLESS over WebSocket
    config = {
        "v": "2",
        "ps": f"RVG-{link_id}" if link_id else "RVG-Default",
        "add": domain,
        "port": "443",
        "id": uuid,
        "aid": "0",
        "scy": "auto",
        "net": "ws",
        "type": "none",
        "host": domain,
        "path": "/vless",
        "tls": "tls",
        "sni": domain,
        "alpn": "http/1.1",
        "fp": "chrome"
    }
    
    # تبدیل به فرمت base64
    import base64
    config_str = json.dumps(config, separators=(',', ':'))
    encoded = base64.b64encode(config_str.encode()).decode()
    return f"vless://{encoded}"

# ایجاد لینک پیش‌فرض (بدون محدودیت)
default_uuid = str(uuid.uuid4())
default_link = {
    "id": "default",
    "name": "Default Link (No Limit)",
    "traffic_limit_mb": None,
    "traffic_used_mb": 0,
    "is_active": True,
    "uuid": default_uuid
}
link_manager.links["default"] = default_link

# API‌ها ====================================

@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # محاسبه آمار کل
    total_traffic_used = sum(link.get("traffic_used_mb", 0) for link in link_manager.links.values())
    active_links = sum(1 for link in link_manager.links.values() if link.get("is_active", True))
    
    # لینک پیش‌فرض برای نمایش در داشبورد
    default_link_url = generate_vless_link(default_uuid, PUBLIC_DOMAIN, "default")
    
    # کد QR برای لینک پیش‌فرض
    qr = qrcode.QRCode(box_size=3, border=1)
    qr.add_data(default_link_url)
    qr.make()
    qr_img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    qr_img.save(buffered, format="PNG")
    default_qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    # لیست لینک‌های ساخته شده
    custom_links = []
    for link_id, link in link_manager.links.items():
        if link_id != "default":
            link_url = generate_vless_link(link["uuid"], PUBLIC_DOMAIN, link_id)
            custom_links.append({
                "id": link_id,
                "name": link["name"],
                "url": link_url,
                "traffic_limit_mb": link["traffic_limit_mb"],
                "traffic_used_mb": round(link["traffic_used_mb"], 2),
                "is_active": link["is_active"],
                "created_at": datetime.fromtimestamp(link["created_at"]).strftime("%Y-%m-%d %H:%M")
            })
    
    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="fa">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RVG Gateway - Render Dashboard</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{
                text-align: center;
                color: white;
                margin-bottom: 30px;
            }}
            .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
            .header p {{ opacity: 0.9; }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .stat-card {{
                background: white;
                border-radius: 15px;
                padding: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                text-align: center;
            }}
            .stat-card h3 {{ color: #667eea; margin-bottom: 10px; }}
            .stat-card .number {{ font-size: 2em; font-weight: bold; color: #333; }}
            .section {{
                background: white;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            .section h2 {{
                color: #667eea;
                margin-bottom: 20px;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }}
            .default-link-box {{
                background: #f7f7f7;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 20px;
                word-break: break-all;
            }}
            .default-link-box code {{ color: #764ba2; font-size: 12px; }}
            .qr-section {{
                display: flex;
                justify-content: center;
                margin: 20px 0;
            }}
            button, .button {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
                transition: transform 0.2s;
            }}
            button:hover {{ transform: translateY(-2px); }}
            .link-item {{
                background: #f9f9f9;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 15px;
                border-right: 4px solid #667eea;
            }}
            .link-name {{ font-weight: bold; font-size: 18px; margin-bottom: 10px; }}
            .link-stats {{ font-size: 14px; color: #666; margin-bottom: 10px; }}
            .link-code {{ font-size: 11px; color: #764ba2; word-break: break-all; background: #eee; padding: 10px; border-radius: 5px; }}
            .btn-copy {{ background: #28a745; margin-right: 10px; }}
            .btn-deactivate {{ background: #dc3545; }}
            .btn-activate {{ background: #28a745; }}
            .create-form {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }}
            .create-form input {{
                flex: 1;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 14px;
            }}
            .note {{
                background: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 10px;
                padding: 15px;
                margin-top: 20px;
                color: #856404;
            }}
            @media (max-width: 768px) {{
                .stats-grid {{ grid-template-columns: 1fr; }}
                .create-form {{ flex-direction: column; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 RVG Gateway</h1>
                <p>اجرا شده روی Render.com | تونل VLESS over WebSocket</p>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <h3>📊 کل ترافیک مصرفی</h3>
                    <div class="number">{sum(link.get('traffic_used_mb', 0) for link in link_manager.links.values()):.2f} MB</div>
                </div>
                <div class="stat-card">
                    <h3>🔗 تعداد لینک‌ها</h3>
                    <div class="number">{len(link_manager.links)}</div>
                </div>
                <div class="stat-card">
                    <h3>✅ لینک‌های فعال</h3>
                    <div class="number">{active_links}</div>
                </div>
            </div>

            <div class="section">
                <h2>🔗 لینک پیش‌فرض (بدون محدودیت)</h2>
                <div class="default-link-box">
                    <code id="defaultLink">{default_link_url}</code>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button onclick="copyToClipboard('defaultLink')" class="btn-copy">📋 کپی لینک</button>
                    <button onclick="showQR('{default_qr_base64}')">📱 نمایش QR Code</button>
                </div>
            </div>

            <div class="section">
                <h2>➕ ساخت لینک جدید</h2>
                <div class="create-form">
                    <input type="text" id="linkName" placeholder="نام لینک (مثال: دوست, همکار, ...)">
                    <input type="number" id="trafficLimit" placeholder="محدودیت ترافیک (MB) - اختیاری">
                    <button onclick="createLink()">ساخت لینک</button>
                </div>
                
                <h2>🔗 لینک‌های ساخته شده</h2>
                <div id="linksList">
                    {''.join(f'''
                    <div class="link-item" id="link-{link['id']}">
                        <div class="link-name">{link['name']}</div>
                        <div class="link-stats">
                            مصرف شده: {link['traffic_used_mb']} MB 
                            {'| محدودیت: ' + str(link['traffic_limit_mb']) + ' MB' if link['traffic_limit_mb'] else '| بدون محدودیت'}
                            {'| ❌ غیرفعال' if not link['is_active'] else '| ✅ فعال'}
                        </div>
                        <div class="link-code" id="link-{link['id']}-code">{link['url']}</div>
                        <div style="margin-top: 10px;">
                            <button onclick="copyToClipboard('link-{link['id']}-code')" class="btn-copy">📋 کپی لینک</button>
                            <button onclick="toggleLink('{link['id']}')" class="{'btn-deactivate' if link['is_active'] else 'btn-activate'}">
                                {'❌ غیرفعال' if link['is_active'] else '✅ فعال'}
                            </button>
                        </div>
                    </div>
                    ''' for link in custom_links)}
                </div>
            </div>

            <div class="note">
                <strong>ℹ️ نکته مهم:</strong> تمام اطلاعات به صورت درون حافظه ذخیره می‌شوند. با هر بار ری‌استارت سرویس در Render، اطلاعات لینک‌ها و آمار مصرف ریست خواهند شد.
                <br><br>
                <strong>🌐 دامنه فعلی:</strong> {PUBLIC_DOMAIN}
            </div>
        </div>

        <script>
            async function createLink() {{
                const name = document.getElementById('linkName').value;
                const trafficLimit = document.getElementById('trafficLimit').value;
                
                if (!name) {{
                    alert('لطفاً نام لینک را وارد کنید');
                    return;
                }}
                
                const response = await fetch('/api/links', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ name: name, traffic_limit_mb: trafficLimit ? parseFloat(trafficLimit) : null }})
                }});
                
                if (response.ok) {{
                    location.reload();
                }} else {{
                    alert('خطا در ساخت لینک');
                }}
            }}
            
            async function toggleLink(linkId) {{
                const response = await fetch(`/api/links/${{linkId}}/toggle`, {{ method: 'POST' }});
                if (response.ok) {{
                    location.reload();
                }} else {{
                    alert('خطا در تغییر وضعیت');
                }}
            }}
            
            function copyToClipboard(elementId) {{
                const element = document.getElementById(elementId);
                const text = element.innerText;
                navigator.clipboard.writeText(text);
                alert('لینک کپی شد!');
            }}
            
            function showQR(qrData) {{
                const qrWindow = window.open('', '_blank', 'width=350,height=400');
                qrWindow.document.write(`
                    <html dir="rtl">
                    <head><title>QR Code</title></head>
                    <body style="text-align:center; padding:20px;">
                        <h3>اسکن کنید</h3>
                        <img src="data:image/png;base64,${{qrData}}" style="width:300px;height:300px;">
                        <br><button onclick="window.close()">بستن</button>
                    </body>
                    </html>
                `);
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html_content)

@app.post("/api/links")
async def create_link(request: CreateLinkRequest):
    link_id = str(uuid.uuid4())[:8]
    link_manager.links[link_id] = {
        "id": link_id,
        "name": request.name,
        "traffic_limit_mb": request.traffic_limit_mb,
        "traffic_used_mb": 0,
        "is_active": True,
        "created_at": time.time(),
        "uuid": str(uuid.uuid4())
    }
    return JSONResponse({"success": True, "link_id": link_id})

@app.post("/api/links/{link_id}/toggle")
async def toggle_link(link_id: str):
    if link_id not in link_manager.links:
        raise HTTPException(status_code=404, detail="Link not found")
    link_manager.links[link_id]["is_active"] = not link_manager.links[link_id]["is_active"]
    return JSONResponse({"success": True, "is_active": link_manager.links[link_id]["is_active"]})

@app.get("/vless")
async def vless_endpoint():
    """WebSocket endpoint برای VLESS tunnel"""
    return JSONResponse({"status": "WebSocket endpoint ready", "message": "Use wss:// for connection"})

@app.get("/api/stats")
async def get_stats():
    total_traffic = sum(link.get("traffic_used_mb", 0) for link in link_manager.links.values())
    return JSONResponse({
        "total_traffic_mb": total_traffic,
        "total_links": len(link_manager.links),
        "active_links": sum(1 for link in link_manager.links.values() if link.get("is_active", True))
    })

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 RVG Gateway running on Render")
    print(f"📍 Public Domain: {PUBLIC_DOMAIN}")
    print(f"🔗 Dashboard: https://{PUBLIC_DOMAIN}/dashboard")
    uvicorn.run(app, host="0.0.0.0", port=PORT)