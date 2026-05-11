from flask import Flask, Response, redirect, request, jsonify, make_response
import os, subprocess, sys, threading, time, socket, hashlib, secrets
from datetime import datetime, timedelta
import pytz, json

try:
    import requests as req_lib
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

app = Flask(__name__)
_dir = os.path.dirname(os.path.abspath(__file__))

# ── ENTORNO ───────────────────────────────────────────────────────────────────
PORT   = int(os.environ.get("PORT", 8000))
RENDER = bool(os.environ.get("RENDER", False))
PARQUET_PATH = os.path.join(_dir, "data", "reporte.parquet")
LIMA_TZ = pytz.timezone("America/Lima")

# En Render: UN solo Streamlit en puerto 8501 con todas las páginas
# En local:  Cada página en su propio puerto
STREAMLIT_PORT = 8501

PAGES = {
    "/tablero-his":  ("pages/app.py",                8501),
    "/prenatal":     ("pages/1_Periodo_Prenatal.py", 8502),
    "/nino":         ("pages/2_Nino.py",             8503),
    "/adolescente":  ("pages/3_Adolescente.py",      8504),
    "/joven":        ("pages/4_Joven.py",            8505),
    "/adulto":       ("pages/5_Adulto.py",           8506),
    "/adulto-mayor": ("pages/6_Adulto_Mayor.py",     8507),
}

# Mapeo de ruta Flask → nombre de página Streamlit (para multi-page)
PAGE_NAMES = {
    "/tablero-his":  "app",
    "/prenatal":     "1_Periodo_Prenatal",
    "/nino":         "2_Nino",
    "/adolescente":  "3_Adolescente",
    "/joven":        "4_Joven",
    "/adulto":       "5_Adulto",
    "/adulto-mayor": "6_Adulto_Mayor",
}

TITULOS = {
    "/tablero-his":  "Tablero HIS",
    "/prenatal":     "Período Prenatal",
    "/nino":         "Niño (0–11 años)",
    "/adolescente":  "Adolescente",
    "/joven":        "Joven",
    "/adulto":       "Adulto",
    "/adulto-mayor": "Adulto Mayor",
}

streamlit_proc = None

# ── SESIONES ──────────────────────────────────────────────────────────────────
_sessions_file = os.path.join(_dir, ".sessions.json")

def _load_sessions():
    try:
        if os.path.exists(_sessions_file):
            return json.load(open(_sessions_file))
    except:
        pass
    return {}

def _save_sessions(s):
    try:
        json.dump(s, open(_sessions_file, "w"))
    except:
        pass

def _clean_sessions(s):
    now = datetime.now().timestamp()
    return {k: v for k, v in s.items() if v.get("expires", 0) > now}

def create_session(usuario, nombre):
    token = secrets.token_hex(24)
    s = _clean_sessions(_load_sessions())
    s[token] = {"usuario": usuario, "nombre": nombre,
                "expires": (datetime.now() + timedelta(hours=8)).timestamp()}
    _save_sessions(s)
    return token

def get_session(token):
    if not token:
        return None
    data = _load_sessions().get(token)
    if not data or data.get("expires", 0) < datetime.now().timestamp():
        return None
    return data

def delete_session(token):
    s = _load_sessions()
    s.pop(token, None)
    _save_sessions(s)

# ── USUARIOS ──────────────────────────────────────────────────────────────────
USUARIOS = {
    "admin": {"hash": hashlib.sha256("sanpablo2026".encode()).hexdigest(), "nombre": "Administrador"},
    "cesar": {"hash": hashlib.sha256("salud2026".encode()).hexdigest(),    "nombre": "César E. Malca"},
}

# ── AUTH ──────────────────────────────────────────────────────────────────────
def get_token():    return request.cookies.get("rsp_token")
def logged_in():   return get_session(get_token()) is not None
def current_user(): return get_session(get_token()) or {}

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not logged_in():
            resp = make_response(redirect("/login"))
            resp.delete_cookie("rsp_token")
            return resp
        return fn(*args, **kwargs)
    return wrapper

# ── HELPERS ───────────────────────────────────────────────────────────────────
def is_port_open(port, host="localhost"):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False

def get_parquet_fecha():
    try:
        if not os.path.exists(PARQUET_PATH):
            return None
        mtime = os.path.getmtime(PARQUET_PATH)
        dt = datetime.utcfromtimestamp(mtime).replace(tzinfo=pytz.utc).astimezone(LIMA_TZ)
        m = {1:"ENE",2:"FEB",3:"MAR",4:"ABR",5:"MAY",6:"JUN",
             7:"JUL",8:"AGO",9:"SET",10:"OCT",11:"NOV",12:"DIC"}
        return f"{dt.day:02d} {m[dt.month]} {dt.year} · {dt.strftime('%H:%M')}"
    except:
        return None

def _load_logo():
    p = os.path.join(_dir, "logo_b64.txt")
    if os.path.exists(p):
        return open(p).read().strip()
    hp = os.path.join(_dir, "portada.html")
    if os.path.exists(hp):
        html = open(hp, encoding="utf-8").read()
        mk = 'src="data:image/png;base64,'
        i = html.find(mk)
        if i >= 0:
            s = i + len(mk)
            return html[s:html.find('"', s)]
    return ""

LOGO_B64 = _load_logo()

# ── STREAMLIT ─────────────────────────────────────────────────────────────────
def launch_streamlit_render():
    """En Render: lanza UNA instancia multi-page de Streamlit."""
    global streamlit_proc
    if is_port_open(STREAMLIT_PORT):
        return
    main_page = os.path.join(_dir, "pages", "app.py")
    if not os.path.exists(main_page):
        print(f"⚠️  No se encontró {main_page}")
        return
    cmd = [sys.executable, "-m", "streamlit", "run", main_page,
           "--server.port", str(STREAMLIT_PORT),
           "--server.address", "0.0.0.0",
           "--server.headless", "true",
           "--server.runOnSave", "false",
           "--browser.gatherUsageStats", "false",
           "--theme.base", "light"]
    streamlit_proc = subprocess.Popen(cmd, cwd=_dir,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
    print(f"  🔄 Streamlit multi-page → puerto {STREAMLIT_PORT}")

def launch_streamlit_local(route, page_file, port):
    """En local: lanza cada página en su propio puerto."""
    full = os.path.join(_dir, page_file)
    if not os.path.exists(full) or is_port_open(port):
        return
    cmd = [sys.executable, "-m", "streamlit", "run", full,
           "--server.port", str(port),
           "--server.address", "0.0.0.0",
           "--server.headless", "true",
           "--server.runOnSave", "false",
           "--browser.gatherUsageStats", "false",
           "--theme.base", "light"]
    subprocess.Popen(cmd, cwd=_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)

def preload_all():
    time.sleep(2)
    if RENDER:
        launch_streamlit_render()
    else:
        for route, (page_file, port) in PAGES.items():
            if not is_port_open(port):
                threading.Thread(target=launch_streamlit_local,
                                args=(route, page_file, port),
                                daemon=True).start()
                time.sleep(0.4)

def proxy_to_streamlit(port, path="", qs=""):
    """Proxy HTTP hacia Streamlit interno."""
    url = f"http://localhost:{port}"
    if path:
        url += "/" + path.lstrip("/")
    if qs:
        url += "?" + qs
    try:
        headers = {k: v for k, v in request.headers
                   if k.lower() not in ["host","content-length","transfer-encoding"]}
        r = req_lib.request(
            method=request.method, url=url, headers=headers,
            data=request.get_data(), cookies=request.cookies,
            allow_redirects=False, timeout=30, stream=True
        )
        resp_headers = {k: v for k, v in r.headers.items()
                       if k.lower() not in ["transfer-encoding","content-encoding"]}
        return Response(r.content, status=r.status_code,
                       headers=resp_headers,
                       content_type=r.headers.get("content-type","text/html"))
    except Exception as e:
        return Response(f"<h3>Error conectando al tablero: {e}</h3>", status=502)

def waiting_page(titulo):
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="4;url={request.path}">
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
*{{margin:0;padding:0;box-sizing:border-box;font-family:'Plus Jakarta Sans',sans-serif;}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#0a1a5c,#1C398E);}}
.box{{text-align:center;color:#fff;}}
.spinner{{width:52px;height:52px;border:4px solid rgba(255,255,255,.2);border-top-color:#fff;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 1.5rem;}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
h2{{font-size:1.4rem;font-weight:800;margin-bottom:.5rem;}}
p{{font-size:.9rem;color:rgba(255,255,255,.7);}}
.back{{margin-top:2rem;display:inline-block;color:rgba(255,255,255,.6);font-size:.8rem;text-decoration:none;border:1px solid rgba(255,255,255,.3);padding:6px 18px;border-radius:20px;}}
</style></head>
<body><div class="box">
<div class="spinner"></div>
<h2>Cargando {titulo}</h2>
<p>Iniciando el tablero, espera un momento...</p>
<a class="back" href="/">← Volver a la portada</a>
</div></body></html>"""

# ── LOGIN HTML ────────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Red de Salud San Pablo · Acceso</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Plus Jakarta Sans',sans-serif;}
:root{--blue:#1C398E;--txt:#0b1e42;--muted:#4a6280;--border:#e2eaf4;--bg:#f0f4fa;}
html,body{height:100%;background:var(--bg);}
body{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:1rem;}
.login-wrap{width:100%;max-width:420px;}
.login-brand{text-align:center;margin-bottom:2rem;}
.brand-logo{width:72px;height:72px;border-radius:50%;object-fit:cover;margin-bottom:1rem;box-shadow:0 4px 20px rgba(28,57,142,.18);}
.brand-title{font-size:1.1rem;font-weight:800;color:var(--txt);}
.brand-sub{font-size:.78rem;color:var(--muted);margin-top:3px;}
.login-card{background:#fff;border:1px solid var(--border);border-radius:20px;padding:2rem 2.2rem;box-shadow:0 8px 40px rgba(15,40,90,.10);}
.login-head{margin-bottom:1.6rem;}
.login-head h2{font-size:1.3rem;font-weight:800;color:var(--txt);margin-bottom:.3rem;}
.login-head p{font-size:.82rem;color:var(--muted);}
.field{margin-bottom:1.1rem;}
.field label{display:block;font-size:.75rem;font-weight:700;color:var(--txt);letter-spacing:.04em;text-transform:uppercase;margin-bottom:.45rem;}
.field-wrap{position:relative;}
.field input{width:100%;padding:.75rem 1rem .75rem 2.8rem;border:1.5px solid var(--border);border-radius:12px;font-size:.9rem;font-family:inherit;color:var(--txt);background:#fafbff;transition:border .15s;outline:none;}
.field input:focus{border-color:#1C398E;box-shadow:0 0 0 3px rgba(28,57,142,.1);}
.field-ico{position:absolute;left:.85rem;top:50%;transform:translateY(-50%);width:18px;height:18px;opacity:.45;}
.show-pw{position:absolute;right:.85rem;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:0;opacity:.4;}
.btn-login{width:100%;padding:.85rem;background:linear-gradient(135deg,#1C398E,#2563eb);border:none;border-radius:12px;color:#fff;font-family:inherit;font-size:.92rem;font-weight:700;cursor:pointer;transition:all .2s;margin-top:.4rem;}
.btn-login:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(28,57,142,.30);}
.error{background:#fff0f0;border:1px solid #fecaca;border-radius:10px;padding:.7rem 1rem;font-size:.82rem;color:#dc2626;display:flex;align-items:center;gap:.5rem;margin-bottom:1rem;}
.login-footer{text-align:center;margin-top:1.5rem;font-size:.72rem;color:#94a3b8;}
</style></head>
<body>
<div class="login-wrap">
  <div class="login-brand">
    <img class="brand-logo" src="data:image/png;base64,{LOGO}" alt="Logo">
    <div class="brand-title">Red de Salud San Pablo</div>
    <div class="brand-sub">Gobierno Regional de Cajamarca</div>
  </div>
  <div class="login-card">
    <div class="login-head"><h2>Iniciar sesión</h2><p>Ingresa tus credenciales para acceder</p></div>
    {ERROR}
    <form method="POST" action="/login">
      <div class="field">
        <label>Usuario</label>
        <div class="field-wrap">
          <svg class="field-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="7" r="4"/><path d="M5 21c0-3.866 3.134-7 7-7s7 3.134 7 7"/></svg>
          <input type="text" name="usuario" placeholder="tu usuario" autocomplete="username" required value="{USR}">
        </div>
      </div>
      <div class="field">
        <label>Contraseña</label>
        <div class="field-wrap">
          <svg class="field-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
          <input type="password" name="clave" id="pw-field" placeholder="••••••••" autocomplete="current-password" required>
          <button type="button" class="show-pw" onclick="var f=document.getElementById('pw-field');f.type=f.type==='password'?'text':'password'">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <button type="submit" class="btn-login">Ingresar a la plataforma</button>
    </form>
  </div>
  <div class="login-footer">© 2026 · Red de Salud San Pablo · César E. Malca Cabanillas</div>
</div>
</body></html>"""

# ── RUTAS ─────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    error_html, usr_val = "", ""
    if request.method == "POST":
        usuario = request.form.get("usuario","").strip().lower()
        clave   = request.form.get("clave","")
        usr_val = usuario
        if usuario in USUARIOS and USUARIOS[usuario]["hash"] == hashlib.sha256(clave.encode()).hexdigest():
            token = create_session(usuario, USUARIOS[usuario]["nombre"])
            resp = make_response(redirect("/"))
            resp.set_cookie("rsp_token", token, max_age=28800,
                           httponly=True, samesite="Lax", path="/")
            return resp
        error_html = '<div class="error"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>Usuario o contraseña incorrectos.</div>'
    html = LOGIN_HTML.replace("{LOGO}", LOGO_B64).replace("{ERROR}", error_html).replace("{USR}", usr_val)
    return Response(html, mimetype="text/html; charset=utf-8")

@app.route("/logout")
def logout():
    delete_session(get_token())
    resp = make_response(redirect("/login"))
    resp.delete_cookie("rsp_token")
    return resp

@app.route("/home")
def home():
    if logged_in():
        return redirect("/")
    sessions = _clean_sessions(_load_sessions())
    if sessions:
        token = list(sessions.keys())[0]
        resp = make_response(redirect("/"))
        resp.set_cookie("rsp_token", token, max_age=28800,
                       httponly=True, samesite="Lax", path="/")
        return resp
    resp = make_response(redirect("/login"))
    resp.delete_cookie("rsp_token")
    return resp

@app.route("/")
@login_required
def portada():
    with open(os.path.join(_dir, "portada.html"), encoding="utf-8") as f:
        content = f.read()
    nombre = current_user().get("nombre","")
    extra_css = """
.nd-user-badge{display:flex;align-items:center;gap:5px;font-size:.65rem;font-weight:700;color:var(--blue);background:#f0f4ff;border:1px solid #d0dcff;border-radius:20px;padding:4px 12px;white-space:nowrap;}
.nd-logout-btn{display:flex;align-items:center;gap:5px;font-size:.65rem;font-weight:700;color:#e05;text-decoration:none;background:#fff0f3;border:1px solid #ffd0db;border-radius:20px;padding:4px 12px;transition:background .15s;white-space:nowrap;}
.nd-logout-btn:hover{background:#ffe0e8;}
"""
    user_badge = f"""<div class="nd-user-badge">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="7" r="4"/><path d="M5 21c0-3.866 3.134-7 7-7s7 3.134 7 7"/></svg>
      {nombre}
    </div>
    <a href="/logout" class="nd-logout-btn">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
      Salir
    </a>"""
    content = content.replace("</style>", extra_css + "</style>", 1)
    content = content.replace('<div class="nd-dot"></div>', user_badge + '<div class="nd-dot"></div>')
    return Response(content, mimetype="text/html; charset=utf-8")

@app.route("/api/update-time")
@login_required
def api_update_time():
    fecha = get_parquet_fecha()
    if fecha:
        return jsonify({"fecha": fecha, "ok": True})
    dt = datetime.now(LIMA_TZ)
    m = {1:"ENE",2:"FEB",3:"MAR",4:"ABR",5:"MAY",6:"JUN",
         7:"JUL",8:"AGO",9:"SET",10:"OCT",11:"NOV",12:"DIC"}
    return jsonify({"fecha": f"{dt.day:02d} {m[dt.month]} {dt.year} · {dt.strftime('%H:%M')}", "ok": False})

# ── RUTAS DE TABLEROS ─────────────────────────────────────────────────────────
def make_tablero_route(route, titulo):
    def view():
        if not logged_in():
            resp = make_response(redirect("/login"))
            resp.delete_cookie("rsp_token")
            return resp

        if RENDER:
            # En Render: proxy HTTP — el navegador solo ve la URL de Render
            port = STREAMLIT_PORT
            if not is_port_open(port):
                threading.Thread(target=launch_streamlit_render, daemon=True).start()
                for _ in range(20):
                    if is_port_open(port):
                        break
                    time.sleep(1)
                else:
                    return Response(waiting_page(titulo), mimetype="text/html; charset=utf-8")
            # Proxy transparente — nunca redirige a 0.0.0.0 ni localhost
            page_name = PAGE_NAMES.get(route, "app")
            return proxy_to_streamlit(port, page_name, request.query_string.decode())

        else:
            # En local: cada página tiene su propio puerto
            _, port = PAGES[route]
            if not is_port_open(port):
                page_file, _ = PAGES[route]
                threading.Thread(target=launch_streamlit_local,
                                args=(route, page_file, port), daemon=True).start()
                for _ in range(20):
                    if is_port_open(port):
                        break
                    time.sleep(1)
                else:
                    return Response(waiting_page(titulo), mimetype="text/html; charset=utf-8")
            return redirect(f"http://localhost:{port}", code=302)

    view.__name__ = route.replace("/","").replace("-","_")
    return view

for route, titulo in TITULOS.items():
    app.add_url_rule(route, view_func=make_tablero_route(route, titulo))

@app.route("/_stcore/<path:subpath>", methods=["GET","POST"])
def stcore_proxy(subpath):
    """Proxy para recursos internos de Streamlit."""
    if RENDER and HAS_REQUESTS:
        return proxy_to_streamlit(STREAMLIT_PORT, f"_stcore/{subpath}", request.query_string.decode())
    return not_found(None)

@app.route("/static/<path:subpath>", methods=["GET","POST"])
def static_proxy(subpath):
    """Proxy para archivos estáticos de Streamlit."""
    if RENDER and HAS_REQUESTS:
        return proxy_to_streamlit(STREAMLIT_PORT, f"static/{subpath}", request.query_string.decode())
    return not_found(None)

@app.route("/stream", methods=["GET","POST"])
def stream_proxy():
    """Proxy para el endpoint de streaming de Streamlit."""
    if RENDER and HAS_REQUESTS:
        return proxy_to_streamlit(STREAMLIT_PORT, "stream", request.query_string.decode())
    return not_found(None)

@app.errorhandler(404)
def not_found(e):
    html = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>No encontrado</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Plus Jakarta Sans',sans-serif;}
body{min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#0a1a5c,#1C398E);}
.box{text-align:center;color:#fff;padding:2rem;}
.num{font-size:6rem;font-weight:900;opacity:.2;line-height:1;}h2{font-size:1.5rem;font-weight:800;margin-bottom:.5rem;}
p{font-size:.9rem;color:rgba(255,255,255,.7);margin-bottom:2rem;}
a{color:#fff;text-decoration:none;border:1px solid rgba(255,255,255,.4);padding:8px 24px;border-radius:20px;font-size:.85rem;font-weight:600;}
</style></head><body><div class="box"><div class="num">404</div><h2>Página no encontrada</h2>
<p>La ruta que buscas no existe.</p><a href="/">← Volver a la portada</a></div></body></html>"""
    return Response(html, status=404, mimetype="text/html; charset=utf-8")

# ── INICIO ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _save_sessions({})
    print("\n🚀  Red de Salud San Pablo — Plataforma Analítica")
    print("=" * 50)
    print(f"✅  Portada → http://localhost:{PORT}")
    print(f"🔐  Login  → http://localhost:{PORT}/login")
    print(f"🌍  Modo   → {'RENDER (producción)' if RENDER else 'LOCAL (desarrollo)'}")
    print()
    for u, d in USUARIOS.items():
        print(f"    · {u} ({d['nombre']})")
    fecha = get_parquet_fecha()
    if fecha:
        print(f"\n📊  reporte.parquet: {fecha}")
    print("=" * 50)
    print("\n⏳  Precargando tableros...")
    threading.Thread(target=preload_all, daemon=True).start()
    print("   (listos en ~15s)\n")
    try:
        app.run(host="0.0.0.0", port=PORT, debug=False)
    except KeyboardInterrupt:
        print("\n⏹️  Cerrando...")
        if streamlit_proc:
            streamlit_proc.terminate()


