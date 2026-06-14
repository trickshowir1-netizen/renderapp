from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import json
import os
import time
import base64
import qrcode
from io import BytesIO

app = FastAPI(title="RVG Gateway - Render Version")

# ========== تنظیمات ==========
PORT = int(os.getenv("PORT", 8000))
RENDER_PUBLIC_DOMAIN = os.getenv("RENDER_PUBLIC_DOMAIN", "localhost")
PUBLIC_DOMAIN = RENDER_PUBLIC_DOMAIN

# ========== ذخیره‌سازی ==========
class LinkManager:
    def __init__(self):
        self.links = {}
        
link_manager = LinkManager()

class CreateLinkRequest(BaseModel):
    name: str
    traffic_limit_mb: Optional[float] = None

def generate_vless_link(uuid_str: str, domain: str, name: str) -> str:
    """تولید لینک VLESS استاندارد"""
    config = {
        "v": "2",
        "ps": name,
        "add": domain,
        "port": "443",
        "id": uuid_str,
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
    config_str = json.dumps(config, separators=(',', ':'))
    encoded = base64.b64encode(config_str.encode()).decode()
    return f"vless://{encoded}"

# لینک پیش‌فرض
default_uuid = str(uuid.uuid4())
default_name = "RVG-Default"
default_link = {
    "id": "default",
    "name": default_name,
    "traffic_limit_mb": None,
    "traffic_used_mb": 0,
    "is_active": True,
    "uuid": default_uuid,
    "created_at": time.time()
}
link_manager.links["default"] = default_link

# ========== API ==========
@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "domain": PUBLIC_DOMAIN})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    default_link_url = generate_vless_link(default_uuid, PUBLIC_DOMAIN, default_name)
    
    # ساخت QR
    qr = qrcode.QRCode(box_size=3, border=1)
    qr.add_data(default_link_url)
    qr.make()
    qr_img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    # لیست لینک‌ها
    custom_links = []
    for link_id, link in link_manager.links.items():
        if link_id != "default":
            link_url = generate_vless_link(link["uuid"], PUBLIC_DOMAIN, link["name"])
            custom_links.append({
                "id": link_id,
                "name": link["name"],
                "url": link_url,
                "traffic_limit_mb": link.get("traffic_limit_mb"),
                "traffic_used_mb": round(link.get("traffic_used_mb", 0), 2),
                "is_active": link.get("is_active", True)
            })
    
    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RVG Gateway - مدیریت کانفیگ</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }}
        .header h1 {{ font-size: 2em; margin-bottom: 10px; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            color: white;
        }}
        .stat-card h3 {{ font-size: 14px; opacity: 0.8; margin-bottom: 10px; }}
        .stat-card .number {{ font-size: 2em; font-weight: bold; }}
        .section {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        .section h2 {{
            color: #1a1a2e;
            margin-bottom: 20px;
            border-bottom: 2px solid #1a1a2e;
            padding-bottom: 10px;
        }}
        .link-box {{
            background: #f0f0f0;
            border-radius: 10px;
            padding: 15px;
            word-break: break-all;
            font-family: monospace;
            font-size: 12px;
            margin-bottom: 15px;
        }}
        button {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            margin: 5px;
        }}
        button:hover {{ opacity: 0.9; }}
        .btn-copy {{ background: #28a745; }}
        .btn-delete {{ background: #dc3545; }}
        .create-form {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .create-form input {{
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 8px;
        }}
        .link-item {{
            background: #f9f9f9;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            border-right: 4px solid #1a1a2e;
        }}
        .note {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 10px;
            padding: 15px;
            color: #856404;
            margin-top: 20px;
        }}
        .qr-img {{ width: 150px; height: 150px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 RVG Gateway</h1>
            <p>مدیریت کانفیگ‌های VLESS over WebSocket</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>📊 کل ترافیک</h3>
                <div class="number">{sum(l.get('traffic_used_mb', 0) for l in link_manager.links.values()):.1f} MB</div>
            </div>
            <div class="stat-card">
                <h3>🔗 تعداد لینک‌ها</h3>
                <div class="number">{len(link_manager.links)}</div>
            </div>
            <div class="stat-card">
                <h3>✅ لینک‌های فعال</h3>
                <div class="number">{sum(1 for l in link_manager.links.values() if l.get('is_active', True))}</div>
            </div>
        </div>

        <div class="section">
            <h2>🔗 کانفیگ پیش‌فرض (بدون محدودیت)</h2>
            <div class="link-box" id="defaultLink">{default_link_url}</div>
            <button class="btn-copy" onclick="copyToClipboard('defaultLink')">📋 کپی لینک</button>
            <button onclick="showQR('{qr_base64}')">📱 QR Code</button>
        </div>

        <div class="section">
            <h2>➕ ساخت کانفیگ جدید</h2>
            <div class="create-form">
                <input type="text" id="linkName" placeholder="نام کانفیگ (مثال: دوست, همکار, موبایل)">
                <input type="number" id="trafficLimit" placeholder="محدودیت ترافیک (MB) - اختیاری">
                <button onclick="createLink()">ساخت کانفیگ</button>
            </div>
            
            <h2>📋 کانفیگ‌های ساخته شده</h2>
            <div id="linksList">
                {''.join(f'''
                <div class="link-item">
                    <strong>{link['name']}</strong><br>
                    مصرف: {link['traffic_used_mb']} MB
                    {f' | محدودیت: {link["traffic_limit_mb"]} MB' if link['traffic_limit_mb'] else ' | نامحدود'}
                    {' | ❌ غیرفعال' if not link['is_active'] else ' | ✅ فعال'}
                    <div class="link-box" style="font-size:10px; margin-top:10px;" id="link-{link['id']}">{link['url']}</div>
                    <button class="btn-copy" onclick="copyToClipboard('link-{link['id']}')">📋 کپی</button>
                    <button onclick="toggleLink('{link['id']}')" style="background:{'#dc3545' if link['is_active'] else '#28a745'}">
                        {'❌ غیرفعال' if link['is_active'] else '✅ فعال'}
                    </button>
                </div>
                ''' for link in custom_links)}
            </div>
        </div>

        <div class="note">
            ⚠️ <strong>نکته:</strong> اطلاعات به صورت موقت ذخیره می‌شوند. با هر بار ری‌استارت سرویس، کانفیگ‌ها ریست می‌شوند.
            <br>
            🌐 دامنه: {PUBLIC_DOMAIN}
        </div>
    </div>

    <script>
        async function createLink() {{
            const name = document.getElementById('linkName').value;
            const limit = document.getElementById('trafficLimit').value;
            if (!name) {{ alert('لطفاً نام کانفیگ را وارد کنید'); return; }}
            
            const response = await fetch('/api/links', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ name: name, traffic_limit_mb: limit ? parseFloat(limit) : null }})
            }});
            if (response.ok) location.reload();
            else alert('خطا در ساخت کانفیگ');
        }}
        
        async function toggleLink(linkId) {{
            const response = await fetch(`/api/links/${{linkId}}/toggle`, {{ method: 'POST' }});
            if (response.ok) location.reload();
            else alert('خطا');
        }}
        
        function copyToClipboard(elementId) {{
            const text = document.getElementById(elementId).innerText;
            navigator.clipboard.writeText(text);
            alert('✅ لینک کپی شد!');
        }}
        
        function showQR(qrData) {{
            const win = window.open('', '_blank', 'width=350,height=400');
            win.document.write(`
                <html><head><title>QR Code</title></head>
                <body style="text-align:center;padding:20px;">
                    <h3>اسکن کنید</h3>
                    <img src="data:image/png;base64,${{qrData}}" style="width:250px;">
                    <br><br><button onclick="window.close()">بستن</button>
                </body>
                </html>
            `);
        }}
    </script>
</body>
</html>
"""
    return HTMLResponse(html)

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
        raise HTTPException(status_code=404)
    link = link_manager.links[link_id]
    link["is_active"] = not link.get("is_active", True)
    return JSONResponse({"success": True})

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 RVG Gateway on Render")
    print(f"📍 Dashboard: https://{PUBLIC_DOMAIN}/dashboard")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
