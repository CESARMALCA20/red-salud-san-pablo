from flask import Flask, Response, redirect, request, jsonify, make_response
from adulto_mayor_flask import adulto_mayor_bp
from adulto_flask import adulto_bp
from joven_flask import joven_bp
from prenatal_flask import prenatal_bp
from tablero_his_flask import tablero_his_bp
from adolescente_flask import adolescente_bp
from nino_flask import nino_bp
import os, subprocess, sys, threading, time, socket, hashlib, secrets
from datetime import datetime, timedelta
import pytz, json

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rsp-san-pablo-2026-default")
app.register_blueprint(adulto_mayor_bp)
app.register_blueprint(adulto_bp)
app.register_blueprint(joven_bp)
app.register_blueprint(prenatal_bp)
app.register_blueprint(adolescente_bp)
app.register_blueprint(nino_bp)
app.register_blueprint(tablero_his_bp)

# ── SESIONES EN MEMORIA (compatible con Render) ──────────────────────────────
_sessions_store = {}

def _load_sessions():
    return _sessions_store

def _save_sessions(s):
    global _sessions_store
    _sessions_store = s

def _clean_sessions(s):
    now = datetime.now().timestamp()
    return {k: v for k, v in s.items() if v.get("expires", 0) > now}

def create_session(usuario, nombre):
    token = secrets.token_hex(24)
    s = _clean_sessions(_load_sessions())
    s[token] = {
        "usuario": usuario,
        "nombre": nombre,
        "expires": (datetime.now() + timedelta(hours=8)).timestamp()
    }
    _save_sessions(s)
    return token

def get_session(token):
    if not token:
        return None
    s = _load_sessions()
    data = s.get(token)
    if not data:
        return None
    if data.get("expires", 0) < datetime.now().timestamp():
        return None
    return data

def delete_session(token):
    s = _load_sessions()
    s.pop(token, None)
    _save_sessions(s)

_dir = os.path.dirname(os.path.abspath(__file__))
PARQUET_PATH = os.path.join(_dir, "data", "reporte.parquet")

# Cargar logo al inicio — desde logo_b64.txt o extraído de portada.html
def _load_logo():
    # Opción 1: archivo separado
    p = os.path.join(_dir, "logo_b64.txt")
    if os.path.exists(p):
        return open(p).read().strip()
    # Opción 2: extraer del portada.html (siempre disponible)
    html_path = os.path.join(_dir, "portada.html")
    if os.path.exists(html_path):
        html = open(html_path, encoding="utf-8").read()
        marker = 'src="data:image/png;base64,'
        idx = html.find(marker)
        if idx >= 0:
            start = idx + len(marker)
            end = html.find('"', start)
            return html[start:end]
    return ""

LOGO_B64 = _load_logo()
LIMA_TZ = pytz.timezone("America/Lima")

# ── USUARIOS ─────────────────────────────────────────────────────────────────
# Para cambiar contraseña: genera el hash con:
#   python3 -c "import hashlib; print(hashlib.sha256('TU_CLAVE'.encode()).hexdigest())"
USUARIOS = {
    "admin": {
        "hash": hashlib.sha256("sanpablo2026".encode()).hexdigest(),
        "nombre": "Administrador",
    },
    "cesar": {
        "hash": hashlib.sha256("salud2026".encode()).hexdigest(),
        "nombre": "César E. Malca",
    },
}

# ── PÁGINAS STREAMLIT ────────────────────────────────────────────────────────
PAGES = {
    # Todos los módulos → manejados por Flask directamente
    # "/tablero-his"  → tablero_his_flask.py
    # "/prenatal"     → prenatal_flask.py
    # "/nino"         → nino_flask.py
    # "/adolescente"  → adolescente_flask.py
    # "/joven"        → joven_flask.py
    # "/adulto"       → adulto_flask.py
    # "/adulto-mayor" → adulto_mayor_flask.py
}
TITULOS = {}
streamlit_procs = {}

# ── HELPERS ───────────────────────────────────────────────────────────────────
def is_port_open(port, host="localhost"):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False

def get_token():
    return request.cookies.get("rsp_token")

def logged_in():
    return get_session(get_token()) is not None

def current_user():
    data = get_session(get_token())
    return data or {}

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = get_token()
        data  = get_session(token)
        print(f"[AUTH] token={token[:8] if token else 'NONE'}... data={data}")
        if not data:
            resp = make_response(redirect("/login"))
            resp.delete_cookie("rsp_token")
            return resp
        return fn(*args, **kwargs)
    return wrapper

def get_parquet_fecha():
    try:
        if not os.path.exists(PARQUET_PATH):
            return None
        mtime = os.path.getmtime(PARQUET_PATH)
        import datetime as _dt
        dt_utc = _dt.datetime.fromtimestamp(mtime, tz=pytz.utc)
        dt_lima = dt_utc.astimezone(LIMA_TZ)
        meses = {1:"ENE",2:"FEB",3:"MAR",4:"ABR",5:"MAY",6:"JUN",
                 7:"JUL",8:"AGO",9:"SET",10:"OCT",11:"NOV",12:"DIC"}
        return f"{dt_lima.day:02d} {meses[dt_lima.month]} {dt_lima.year} · {dt_lima.strftime('%H:%M')}"
    except:
        return None

def launch_streamlit(route, page_file, port):
    full_path = os.path.join(_dir, page_file)
    if not os.path.exists(full_path) or is_port_open(port):
        return
    cmd = [sys.executable, "-m", "streamlit", "run", full_path,
           "--server.port", str(port),
           "--server.headless", "true",
           "--server.runOnSave", "false",
           "--browser.gatherUsageStats", "false",
           "--theme.base", "light"]
    proc = subprocess.Popen(cmd, cwd=_dir,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    streamlit_procs[route] = proc

def waiting_page(port, titulo):
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="3;url=http://localhost:{port}">
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

# ── LOGIN PAGE ────────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Red de Salud San Pablo · Acceso</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Plus Jakarta Sans',sans-serif;}
:root{--blue:#1C398E;--blue-dark:#0a1a5c;--txt:#0b1e42;--muted:#4a6280;--border:#e2eaf4;--bg:#f0f4fa;}
html,body{height:100%;background:var(--bg);}
body{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:1rem;}

.login-wrap{width:100%;max-width:420px;}

.login-brand{text-align:center;margin-bottom:2rem;}
.brand-logo{width:72px;height:72px;border-radius:50%;object-fit:cover;margin-bottom:1rem;box-shadow:0 4px 20px rgba(28,57,142,.18);}
.brand-title{font-size:1.1rem;font-weight:800;color:var(--txt);letter-spacing:-.01em;}
.brand-sub{font-size:.78rem;color:var(--muted);margin-top:3px;font-weight:500;}

.login-card{background:#fff;border:1px solid var(--border);border-radius:20px;padding:2rem 2.2rem;box-shadow:0 8px 40px rgba(15,40,90,.10);}

.login-head{margin-bottom:1.6rem;}
.login-head h2{font-size:1.3rem;font-weight:800;color:var(--txt);margin-bottom:.3rem;}
.login-head p{font-size:.82rem;color:var(--muted);}

.field{margin-bottom:1.1rem;}
.field label{display:block;font-size:.75rem;font-weight:700;color:var(--txt);letter-spacing:.04em;text-transform:uppercase;margin-bottom:.45rem;}
.field-wrap{position:relative;}
.field input{width:100%;padding:.75rem 1rem .75rem 2.8rem;border:1.5px solid var(--border);border-radius:12px;font-size:.9rem;font-family:inherit;color:var(--txt);background:#fafbff;transition:border .15s,box-shadow .15s;outline:none;}
.field input:focus{border-color:#1C398E;box-shadow:0 0 0 3px rgba(28,57,142,.1);}
.field-ico{position:absolute;left:.85rem;top:50%;transform:translateY(-50%);width:18px;height:18px;opacity:.45;}
.show-pw{position:absolute;right:.85rem;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:0;opacity:.4;transition:opacity .15s;}
.show-pw:hover{opacity:.75;}

.btn-login{width:100%;padding:.85rem;background:linear-gradient(135deg,#1C398E,#2563eb);border:none;border-radius:12px;color:#fff;font-family:inherit;font-size:.92rem;font-weight:700;cursor:pointer;letter-spacing:.02em;transition:all .2s;margin-top:.4rem;}
.btn-login:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(28,57,142,.30);}
.btn-login:active{transform:translateY(0);}

.error{background:#fff0f0;border:1px solid #fecaca;border-radius:10px;padding:.7rem 1rem;font-size:.82rem;color:#dc2626;display:flex;align-items:center;gap:.5rem;margin-bottom:1rem;}
.error svg{flex-shrink:0;}

.login-footer{text-align:center;margin-top:1.5rem;font-size:.72rem;color:#94a3b8;}
</style>
</head>
<body>
<div class="login-wrap">
  <div class="login-brand">
    <img class="brand-logo" src="data:image/png;base64,{LOGO}" alt="Logo Red de Salud San Pablo">
    <div class="brand-title">Red de Salud San Pablo</div>
    <div class="brand-sub">Gobierno Regional de Cajamarca</div>
  </div>

  <div class="login-card">
    <div class="login-head">
      <h2>Iniciar sesión</h2>
      <p>Ingresa tus credenciales para acceder a la plataforma analítica</p>
    </div>

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
          <button type="button" class="show-pw" onclick="togglePw()" id="pw-btn" aria-label="Mostrar contraseña">
            <svg id="ico-show" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
            <svg id="ico-hide" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          </button>
        </div>
      </div>
      <button type="submit" class="btn-login">Ingresar a la plataforma</button>
    </form>
  </div>

  <div class="login-footer">
    © 2026 · Red de Salud San Pablo · César E. Malca Cabanillas
  </div>
</div>
<script>
function togglePw(){
  var f=document.getElementById('pw-field');
  var s=document.getElementById('ico-show');
  var h=document.getElementById('ico-hide');
  if(f.type==='password'){f.type='text';s.style.display='none';h.style.display='';}
  else{f.type='password';s.style.display='';h.style.display='none';}
}
</script>
</body>
</html>"""

# ── RUTAS ─────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    logo = LOGO_B64

    error_html = ""
    usr_val = ""

    if request.method == "POST":
        usuario = request.form.get("usuario","").strip().lower()
        clave   = request.form.get("clave","")
        hash_clave = hashlib.sha256(clave.encode()).hexdigest()
        usr_val = usuario

        if usuario in USUARIOS and USUARIOS[usuario]["hash"] == hash_clave:
            token = create_session(usuario, USUARIOS[usuario]["nombre"])
            resp = make_response(redirect("/"))
            resp.set_cookie("rsp_token", token,
                           max_age=28800,  # 8 horas
                           httponly=True,
                           samesite="Lax",
                           path="/")
            return resp
        else:
            error_html = """<div class="error">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              Usuario o contraseña incorrectos. Intenta de nuevo.
            </div>"""

    html = LOGIN_HTML.replace("{LOGO}", logo).replace("{ERROR}", error_html).replace("{USR}", usr_val)
    return Response(html, mimetype="text/html; charset=utf-8")

@app.route("/home")
def home():
    """Regreso desde Streamlit — busca cualquier sesión activa válida."""
    # Primero intentar con cookie normal
    if logged_in():
        return redirect("/")
    # Si no hay cookie, buscar si hay alguna sesión activa en el archivo
    # (el usuario está logueado en otra pestaña/contexto)
    sessions = _clean_sessions(_load_sessions())
    if sessions:
        # Tomar el primer token válido y reinyectarlo como cookie
        token = list(sessions.keys())[0]
        resp = make_response(redirect("/"))
        resp.set_cookie("rsp_token", token,
                       max_age=28800,
                       httponly=True,
                       samesite="Lax",
                       path="/")
        return resp
    # No hay sesión activa
    resp = make_response(redirect("/login"))
    resp.delete_cookie("rsp_token")
    return resp

@app.route("/logout")
def logout():
    delete_session(get_token())
    resp = make_response(redirect("/login"))
    resp.delete_cookie("rsp_token")
    return resp

@app.route("/")
@login_required
def portada():
    with open(os.path.join(_dir, "portada.html"), encoding="utf-8") as f:
        content = f.read()
    # Inyectar nombre del usuario y botón logout en el navbar
    nombre = current_user().get("nombre","")
    user_badge = f"""<div class="nd-user-badge">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="7" r="4"/><path d="M5 21c0-3.866 3.134-7 7-7s7 3.134 7 7"/></svg>
      {nombre}
    </div>
    <a href="/logout" class="nd-logout-btn">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
      Salir
    </a>"""
    # Agregar CSS del badge/logout y el HTML antes del cierre del nav-right
    extra_css = """
.nd-user-badge{display:flex;align-items:center;gap:5px;font-size:.65rem;font-weight:700;color:var(--blue);letter-spacing:.03em;background:#f0f4ff;border:1px solid #d0dcff;border-radius:20px;padding:4px 12px;white-space:nowrap;}
.nd-logout-btn{display:flex;align-items:center;gap:5px;font-size:.65rem;font-weight:700;color:#e05;text-decoration:none;background:#fff0f3;border:1px solid #ffd0db;border-radius:20px;padding:4px 12px;transition:background .15s;white-space:nowrap;}
.nd-logout-btn:hover{background:#ffe0e8;}
"""
    content = content.replace("</style>", extra_css + "</style>", 1)
    content = content.replace(
        '<div class="nd-dot"></div>',
        user_badge + '<div class="nd-dot"></div>'
    )
    return Response(content, mimetype="text/html; charset=utf-8")

@app.route("/api/update-time")
@login_required
def api_update_time():
    fecha = get_parquet_fecha()
    if fecha:
        return jsonify({"fecha": fecha, "ok": True})
    dt_lima = datetime.now(LIMA_TZ)
    meses = {1:"ENE",2:"FEB",3:"MAR",4:"ABR",5:"MAY",6:"JUN",
             7:"JUL",8:"AGO",9:"SET",10:"OCT",11:"NOV",12:"DIC"}
    fecha_now = f"{dt_lima.day:02d} {meses[dt_lima.month]} {dt_lima.year} · {dt_lima.strftime('%H:%M')}"
    return jsonify({"fecha": fecha_now, "ok": False})

def make_route(route, titulo):
    def view():
        if not logged_in():
            resp = make_response(redirect("/login"))
            resp.delete_cookie("rsp_token")
            return resp
        page_file, port = PAGES[route]
        # Streamlit precargado — esperar hasta 20s antes de mostrar pantalla de carga
        for _ in range(20):
            if is_port_open(port):
                return redirect(f"http://localhost:{port}", code=302)
            time.sleep(1)
        # Si aún no está listo, mostrar pantalla de espera y lanzar
        threading.Thread(target=launch_streamlit,
                        args=(route, page_file, port),
                        daemon=True).start()
        return Response(waiting_page(port, titulo),
                       mimetype="text/html; charset=utf-8")
    view.__name__ = route.replace("/","").replace("-","_")
    return view

for route, titulo in TITULOS.items():
    app.add_url_rule(route, view_func=make_route(route, titulo))

# ── 404 personalizado ─────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    html = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Página no encontrada</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Plus Jakarta Sans',sans-serif;}
body{min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#0a1a5c,#1C398E);}
.box{text-align:center;color:#fff;padding:2rem;}
.num{font-size:6rem;font-weight:900;opacity:.2;line-height:1;}
h2{font-size:1.5rem;font-weight:800;margin-bottom:.5rem;}
p{font-size:.9rem;color:rgba(255,255,255,.7);margin-bottom:2rem;}
a{color:#fff;text-decoration:none;border:1px solid rgba(255,255,255,.4);padding:8px 24px;border-radius:20px;font-size:.85rem;font-weight:600;}
a:hover{background:rgba(255,255,255,.1);}
</style></head>
<body><div class="box">
<div class="num">404</div>
<h2>Página no encontrada</h2>
<p>La ruta que buscas no existe en esta plataforma.</p>
<a href="/">← Volver a la portada</a>
</div></body></html>"""
    return Response(html, status=404, mimetype="text/html; charset=utf-8")

# ── INICIO ────────────────────────────────────────────────────────────────────
def preload_all_streamlit():
    """Lanza todos los Streamlit en segundo plano al iniciar."""
    # Pequeña espera para que Flask arranque primero
    time.sleep(2)
    for route, (page_file, port) in PAGES.items():
        nombre = TITULOS.get(route, route)
        full_path = os.path.join(_dir, page_file)
        if not os.path.exists(full_path):
            print(f"  ⚠️  No encontrado: {page_file}")
            continue
        if is_port_open(port):
            print(f"  ♻️  Ya activo: {nombre} (:{port})")
            continue
        threading.Thread(
            target=launch_streamlit,
            args=(route, page_file, port),
            daemon=True
        ).start()
        print(f"  🔄  Iniciando: {nombre} → puerto {port}")
        time.sleep(0.4)  # escalonar para no saturar la CPU

if __name__ == "__main__":
    print("\n🚀  Red de Salud San Pablo — Plataforma Analítica")
    print("=" * 50)
    print("✅  Portada  → http://localhost:8000")
    print("🔐  Login    → http://localhost:8000/login")
    print()
    print("👤  Usuarios configurados:")
    for u, d in USUARIOS.items():
        print(f"    · {u} ({d['nombre']})")
    fecha = get_parquet_fecha()
    if fecha:
        print(f"\n📊  reporte.parquet: {fecha}")
    print("=" * 50)
    print("\n⏳  Precargando tableros en segundo plano...")

    # Lanzar todos los Streamlit en segundo plano
    threading.Thread(target=preload_all_streamlit, daemon=True).start()

    print("   (los tableros estarán listos en ~15 segundos)\n")

    try:
        port = int(os.environ.get("PORT", 8000))
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        print("\n⏹️  Cerrando...")
        for proc in streamlit_procs.values():
            proc.terminate()