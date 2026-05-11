"""
Punto de entrada para Render.com
Corre Streamlit directamente en el PORT expuesto con login integrado
"""
import streamlit as st
import hashlib, os, json, secrets
from datetime import datetime, timedelta
import pytz

# ── CONFIG ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Red de Salud San Pablo",
    layout="wide",
    initial_sidebar_state="collapsed"
)

_dir = os.path.dirname(os.path.abspath(__file__))
LIMA_TZ = pytz.timezone("America/Lima")

USUARIOS = {
    "admin": {"hash": hashlib.sha256("sanpablo2026".encode()).hexdigest(), "nombre": "Administrador"},
    "cesar": {"hash": hashlib.sha256("salud2026".encode()).hexdigest(), "nombre": "César E. Malca"},
}

# ── LOGO ──────────────────────────────────────────────────────────────────────
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

# ── CSS LOGIN ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, header, footer, [data-testid="stSidebar"] { display: none !important; }
.stApp { background: #f0f4fa; }
</style>
""", unsafe_allow_html=True)

# ── LOGIN ─────────────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.nombre = ""
    st.session_state.usuario = ""

if not st.session_state.logged_in:
    # Centrar el formulario
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        if LOGO_B64:
            st.markdown(f"""
            <div style="text-align:center;margin-bottom:1.5rem;">
              <img src="data:image/png;base64,{LOGO_B64}"
                   style="width:80px;height:80px;border-radius:50%;object-fit:cover;
                          box-shadow:0 4px 20px rgba(28,57,142,.2);">
              <div style="font-size:1.1rem;font-weight:800;color:#0b1e42;margin-top:.8rem;">Red de Salud San Pablo</div>
              <div style="font-size:.8rem;color:#4a6280;">Gobierno Regional de Cajamarca</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#fff;border:1px solid #e2eaf4;border-radius:20px;
                    padding:2rem 2.2rem;box-shadow:0 8px 40px rgba(15,40,90,.10);">
          <h2 style="font-size:1.3rem;font-weight:800;color:#0b1e42;margin-bottom:.3rem;">Iniciar sesión</h2>
          <p style="font-size:.82rem;color:#4a6280;margin-bottom:1.5rem;">
            Ingresa tus credenciales para acceder a la plataforma analítica</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            usuario = st.text_input("Usuario", placeholder="tu usuario")
            clave   = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Ingresar a la plataforma",
                                              use_container_width=True)
            if submitted:
                hash_clave = hashlib.sha256(clave.encode()).hexdigest()
                if usuario in USUARIOS and USUARIOS[usuario]["hash"] == hash_clave:
                    st.session_state.logged_in = True
                    st.session_state.nombre = USUARIOS[usuario]["nombre"]
                    st.session_state.usuario = usuario
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")

    st.markdown("""
    <div style="text-align:center;margin-top:1.5rem;font-size:.72rem;color:#94a3b8;">
      © 2026 · Red de Salud San Pablo · César E. Malca Cabanillas
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── PORTADA (usuario logueado) ────────────────────────────────────────────────
# Leer portada.html y mostrarla
portada_path = os.path.join(_dir, "portada.html")
if os.path.exists(portada_path):
    portada_html = open(portada_path, encoding="utf-8").read()
    
    # Ajustar links para Streamlit multi-page
    portada_html = portada_html.replace('href="/tablero-his"', 'href="app"')
    portada_html = portada_html.replace('href="/prenatal"',    'href="1_Periodo_Prenatal"')
    portada_html = portada_html.replace('href="/nino"',        'href="2_Nino"')
    portada_html = portada_html.replace('href="/adolescente"', 'href="3_Adolescente"')
    portada_html = portada_html.replace('href="/joven"',       'href="4_Joven"')
    portada_html = portada_html.replace('href="/adulto"',      'href="5_Adulto"')
    portada_html = portada_html.replace('href="/adulto-mayor"','href="6_Adulto_Mayor"')
    portada_html = portada_html.replace('href="/logout"',      'href="?logout=1"')
    
    st.components.v1.html(portada_html, height=700, scrolling=False)
else:
    st.error("portada.html no encontrado")

# Logout
if st.query_params.get("logout"):
    st.session_state.logged_in = False
    st.session_state.nombre = ""
    st.rerun()
