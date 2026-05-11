import streamlit as st
import polars as pl
import pandas as pd
import os
import re

# ─── CONFIGURACIÓN DE PÁGINA ──────────────────────────────────────────────────
pd.set_option("styler.render.max_elements", 1000000)
st.set_page_config(
    layout="wide",
    page_title="Red San Pablo - Niño",
    page_icon="🏥",
    initial_sidebar_state="expanded"
)

# ─── CSS PROFESIONAL (TEMA CLARO) ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: #f4f6fb;
}

[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e2e8f0;
}
[data-testid="stSidebar"] * { color: #1e293b !important; }

/* Labels de multiselect e input */
[data-testid="stSidebar"] .stMultiSelect label,
[data-testid="stSidebar"] .stTextInput label {
    color: #64748b !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase;
}

/* Select container */
[data-testid="stSidebar"] [data-baseweb="select"] > div:first-child {
    background: #ffffff !important;
    border: 1.5px solid #cbd5e1 !important;
    border-radius: 8px !important;
    transition: border-color 0.15s ease !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div:first-child:focus-within {
    border-color: #1C398E !important;
    box-shadow: 0 0 0 3px rgba(28,57,142,0.08) !important;
}

/* Input DNI con borde visible */
[data-testid="stSidebar"] [data-baseweb="input"] {
    background: #ffffff !important;
    border: 1.5px solid #cbd5e1 !important;
    border-radius: 8px !important;
    transition: border-color 0.15s ease !important;
}
[data-testid="stSidebar"] [data-baseweb="input"]:focus-within {
    border-color: #1C398E !important;
    box-shadow: 0 0 0 3px rgba(28,57,142,0.08) !important;
}
[data-testid="stSidebar"] input[type="text"] {
    font-size: 0.83rem !important;
    color: #1e293b !important;
}

[data-testid="stSidebarNavItems"],
[data-testid="stSidebarNav"],
section[data-testid="stSidebarNav"],
div[data-testid="stSidebarNavItems"] { display: none !important; }

.btn-back {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    color: #1C398E !important;
    padding: 10px 20px;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-decoration: none !important;
    cursor: pointer;
    transition: all 0.2s ease;
    width: 100%;
    text-align: center;
    justify-content: center;
    margin-bottom: 20px;
    box-sizing: border-box;
}
.btn-back:hover {
    background: #e8eef8;
    border-color: #1C398E;
}

.hero-header { text-align: center; padding: 30px 20px 10px; margin-bottom: 10px; }
.hero-tag {
    display: inline-block;
    background: #e8eef8;
    border: 1px solid #c5d3ea;
    color: #1C398E;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 4px 14px;
    border-radius: 20px;
    margin-bottom: 12px;
}
.hero-title {
    font-family: 'Inter', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.01em;
    line-height: 1.1;
    margin: 0;
}
.hero-title span {
    color: #1C398E;
}
.hero-sub { font-size: 0.83rem; color: #64748b; margin-top: 8px; letter-spacing: 0.03em; }
.divider {
    height: 1px;
    background: #e2e8f0;
    margin: 16px 0 24px;
}

.metric-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px 22px;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: box-shadow 0.2s ease;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: #1C398E;
}
.metric-card:hover {
    box-shadow: 0 4px 16px rgba(28,57,142,0.10);
}
.metric-icon { font-size: 1.5rem; margin-bottom: 8px; }
.metric-label {
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: 6px;
}
.metric-value {
    font-family: 'Inter', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: #1C398E;
    line-height: 1;
}
.metric-value.green  { color: #059669; }
.metric-value.yellow { color: #b45309; }
.metric-value.red    { color: #dc2626; }

/* ── CONTENEDOR TABLA ── */
.stDataFrame {
    border: none !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 8px rgba(0,0,0,0.07) !important;
}

/* ── CABECERAS ── */
[data-testid="stDataFrame"] th {
    background: #1C398E !important;
    color: #ffffff !important;
    font-size: 0.67rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    padding: 10px 8px !important;
    border-bottom: 2px solid #2563eb !important;
    white-space: pre-line !important;
    text-align: center !important;
}

/* ── FILAS ALTERNAS ── */
[data-testid="stDataFrame"] tr:nth-child(even) td {
    background-color: #f8fafc !important;
}
[data-testid="stDataFrame"] tr:nth-child(odd) td {
    background-color: #ffffff !important;
}

/* ── CELDAS ── */
[data-testid="stDataFrame"] td {
    font-size: 0.78rem !important;
    padding: 7px 8px !important;
    border-bottom: 1px solid #f1f5f9 !important;
    border-right: 1px solid #f1f5f9 !important;
    text-align: center !important;
}

/* ── HOVER ── */
[data-testid="stDataFrame"] tr:hover td {
    background-color: #e8eef8 !important;
    transition: background-color 0.1s ease;
}

/* ── SELECCIONADA ── */
[data-testid="stDataFrame"] tr[aria-selected="true"] td {
    background-color: #dce7f7 !important;
    box-shadow: inset 3px 0 0 #1C398E;
}

/* ── CELDA ACTIVA ── */
[data-testid="stDataFrame"] td:focus,
[data-testid="stDataFrame"] td[aria-selected="true"] {
    outline: 2px solid rgba(28,57,142,0.4) !important;
    outline-offset: -2px;
}

.stDownloadButton button {
    background: #1C398E !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    padding: 10px 24px !important;
    font-size: 0.83rem !important;
    box-shadow: 0 2px 8px rgba(28,57,142,0.2) !important;
}
.stDownloadButton button:hover {
    background: #16307a !important;
}

.filtros-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 0.68rem;
    font-weight: 700;
    color: #94a3b8;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding: 10px 0 10px;
    border-bottom: 1px solid #f1f5f9;
    margin-bottom: 18px;
}
.sidebar-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 0.7rem;
    font-weight: 700;
    color: #475569;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 6px;
    margin-top: 4px;
}
.sidebar-group {
    margin-bottom: 18px;
}
.sidebar-divider {
    height: 1px;
    background: #f1f5f9;
    margin: 6px 0 18px;
}
.sidebar-footer {
    text-align: center;
    padding: 12px 0 4px;
    border-top: 1px solid #f1f5f9;
    margin-top: 8px;
}

.no-data { text-align: center; padding: 60px 20px; color: #94a3b8; }
.no-data-icon { font-size: 2.5rem; margin-bottom: 12px; }
.no-data-title { font-family: 'Inter', sans-serif; font-size: 1.3rem; font-weight: 600; color: #64748b; }

/* ── Botón limpiar DNI ── */
[data-testid="stSidebar"] button[kind="secondary"] {
    background: #f8fafc !important;
    border: 1.5px solid #e2e8f0 !important;
    color: #64748b !important;
    border-radius: 8px !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    margin-top: 8px !important;
    transition: all 0.15s ease !important;
    letter-spacing: 0.03em !important;
}
[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background: #fef2f2 !important;
    border-color: #fca5a5 !important;
    color: #dc2626 !important;
}

/* ── TOPBAR ── */
.topbar-sp {
    background: #1C398E;
    padding: 0 2rem;
    margin: 0 -2rem 2rem -2rem;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: fixed;
    top: 0; left: 0; right: 0;
    z-index: 999999;
    box-shadow: 0 1px 8px rgba(0,0,0,0.15);
}
.topbar-sp-left { display: flex; align-items: center; gap: 14px; }
.topbar-sp-title {
    font-family: 'Inter', sans-serif;
    font-weight: 700; font-size: 14px;
    color: #ffffff; letter-spacing: -0.2px;
}
.topbar-sp-sub {
    font-size: 11px; color: rgba(255,255,255,0.65);
    font-weight: 400; margin-top: 1px;
}
.topbar-sp-badge {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 20px; padding: 5px 14px;
    font-size: 11px; color: rgba(255,255,255,0.85);
    font-weight: 500;
    white-space: nowrap;
}
.block-container { padding-top: 80px !important; }

/* ── TABLA CUSTOM ── */
.table-scroll { overflow-x:auto; overflow-y:auto; max-height:680px; border-radius:12px; border:1px solid #e2e8f0; box-shadow:0 1px 8px rgba(0,0,0,0.06); }
.table-scroll::-webkit-scrollbar { width:5px; height:5px; }
.table-scroll::-webkit-scrollbar-track { background:#f8fafc; }
.table-scroll::-webkit-scrollbar-thumb { background:#cbd5e1; border-radius:3px; }
.joven-table { width:100%; border-collapse:collapse; font-family:'Plus Jakarta Sans','Inter',sans-serif; font-size:13px; }
.joven-table thead { position:sticky; top:0; z-index:10; }
.joven-table thead tr th { background:#1C398E; color:#ffffff; font-family:'Plus Jakarta Sans','Inter',sans-serif; font-size:11px; font-weight:700; letter-spacing:0.4px; padding:11px 10px; text-align:center; border:none; white-space:pre-line; line-height:1.3; }
.joven-table tbody tr:nth-child(odd) td  { background-color:#ffffff; }
.joven-table tbody tr:nth-child(even) td { background-color:#f8fafc; }
.joven-table tbody tr td { color:#334155; padding:9px 10px; border-bottom:1px solid #f1f5f9; font-family:'Plus Jakarta Sans','Inter',sans-serif; font-size:13px; text-align:center; white-space:nowrap; }
.joven-table tbody tr:hover td { background-color:#e8eef8 !important; color:#1e293b; }
.jt-idx  { color:#94a3b8 !important; font-size:12px !important; font-weight:600 !important; }
.jt-num  { color:#1C398E !important; font-weight:700 !important; }
.jt-grey { color:#94a3b8 !important; font-weight:500 !important; }
.jt-ok   { background-color:#f0fdf4 !important; color:#166534 !important; font-weight:600 !important; }
.jt-no   { background-color:#fef2f2 !important; color:#dc2626 !important; font-weight:700 !important; }
.jt-warn { background-color:#fff7ed !important; color:#b45309 !important; font-weight:700 !important; }
.jt-avok { background-color:#166534 !important; color:#ffffff !important; font-weight:800 !important; }
.jt-avmd { background-color:#b45309 !important; color:#ffffff !important; font-weight:700 !important; }
.jt-avno { background-color:#dc2626 !important; color:#ffffff !important; font-weight:700 !important; }
.jt-bgok { background-color:#f0fdf4 !important; }
.jt-bgmd { background-color:#fefce8 !important; }
.jt-bgno { background-color:#fef2f2 !important; }

/* ── Columnas sticky: #, DNI, Paciente ── */
.joven-table th.jt-sticky-idx,
.joven-table td.jt-sticky-idx {
    position: sticky; left: 0px; z-index: 4;
    background: inherit; min-width:40px; max-width:40px;
    border-right: 1px solid #e2e8f0;
}
.joven-table th.jt-sticky-dni,
.joven-table td.jt-sticky-dni {
    position: sticky; left: 40px; z-index: 4;
    background: inherit; min-width:100px; max-width:100px;
    border-right: 1px solid #e2e8f0;
}
.joven-table th.jt-sticky-pac,
.joven-table td.jt-sticky-pac {
    position: sticky; left: 140px; z-index: 4;
    background: inherit; min-width:260px; width:260px;
    border-right: 2px solid #cbd5e1; overflow:visible; white-space:nowrap;
}
.joven-table thead th.jt-sticky-idx,
.joven-table thead th.jt-sticky-dni,
.joven-table thead th.jt-sticky-pac { z-index: 6; background: #1C398E; }

/* ── Multiselect tags — azul marino suave en vez de rojo ── */
[data-baseweb="tag"] {
    background-color: #e8eef8 !important;
    border: 1px solid #c5d3ea !important;
    border-radius: 6px !important;
}
[data-baseweb="tag"] span { color: #1C398E !important; font-weight: 600 !important; }
[data-baseweb="tag"] button svg { fill: #1C398E !important; }
</style>
""", unsafe_allow_html=True)


# ─── CARGA DE DATOS ───────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(BASE_DIR) == "pages":
    BASE_DIR = os.path.dirname(BASE_DIR)

ARCHIVO_PARQUET = os.path.join(BASE_DIR, "data", "reporte.parquet")

@st.cache_data
def cargar_datos():
    if not os.path.exists(ARCHIVO_PARQUET):
        return None
    try:
        df = pl.read_parquet(ARCHIVO_PARQUET)
        df = df.rename({col: col.strip() for col in df.columns})
        return df
    except Exception as e:
        st.error(f"Error técnico al leer Parquet: {e}")
        return None

df_raw = cargar_datos()
if df_raw is None:
    st.error(f"⚠️ Archivo no encontrado: `{ARCHIVO_PARQUET}`")
    st.stop()

# ── Fecha de última modificación del parquet ──
import datetime as _dt
try:
    _mtime = os.path.getmtime(ARCHIVO_PARQUET)
    _fecha_excel = _dt.datetime.fromtimestamp(_mtime).strftime("%d/%m/%Y %H:%M")
except Exception:
    _fecha_excel = "N/D"

# ─── TOPBAR (logo + título + fecha) ─────────────────────────────────────────
_LOGO_B64 = "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"

st.markdown(f"""
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<div class="topbar-sp">
    <div class="topbar-sp-left">
        <img src="data:image/png;base64,{_LOGO_B64}"
             style="height:44px;width:44px;border-radius:50%;object-fit:cover;
                    box-shadow:0 0 12px rgba(0,195,255,0.2);flex-shrink:0;">
        <div>
            <div class="topbar-sp-title">RED DE SALUD SAN PABLO - 2026</div>
            <div class="topbar-sp-sub">Curso de Vida &nbsp;·&nbsp; Niño</div>
        </div>
    </div>
    <div class="topbar-sp-badge">⬤ &nbsp;Actualizado: {_fecha_excel}</div>
</div>
""", unsafe_allow_html=True)

ITEMS_CONFIG = [
    ("99801",    "99801_TA",   "99801\nPLAN ELABORADO"),
    ("99215.03", "99215.03",   "99215.03\nADULTO MAYOR FRAGIL"),
    ("99401",    "99401_PAM",  "99401\nPAM INDEPENDIENTE"),
    ("Z6361",   "Z6361",     "Z6361\nPAM INDEPENDIENTE"),
    ("Z6362",   "Z6362",     "Z6362\nDEPEN. PARCIAL"),
    ("Z6363",   "Z6363",     "Z6363\nDEPEN. TOTAL"),
    ("96150.01", "96150.01",   "96150.01\nTAMIZAJE VIF"),
    ("96150.02", "96150.02",   "96150.02\nALCOHOL Y DROGAS"),
    ("96150.03", "96150.03",   "96150.03\nDEPRESIÓN PHQ-9"),
    ("96150.07", "96150.07",   "96150.07\nDETERIORO COGNIT."),
    ("99402.09", "99402.09",   "99402.09\nCONS. S. MENTAL"),
    ("99173",    "99173",      "99173\nAGUDEZA VISUAL"),
    ("99401.16", "99401.16",   "99401.16\nCONS. S. OCULAR"),
    ("Z019",     "Z019",       "Z019\nVALORACIÓN RIESGO"),
    ("Z017",     "Z017",       "Z017\nEXAM. LABORATORIO"),
    ("99199.22", "99199.22",   "99199.22\nPRESION ART."),
    ("99401.13", "99401.13",   "99401.13\nESTILOS DE VIDA"),
    ("D0150",    "D0150",      "D0150\nORAL"),
    ("99801",    "99801_1",    "99801\nPLAN EJECUTADO"),
    ("90688",    "90688",      "90688\nVAC. INF. CUADRI."),
    ("90658",    "90658",      "90658\nVAC. INF. TRIVAL."),
    ("90670",    "90670",      "90670\nVAC. NEUMOCOCO"),
    ("90749.01", "90749.01",   "90749.01\nVAC. COVID"),
    ("C0011",    "C0011",      "C0011\nVISITA FAMILIAR"),
    ("88141",    "88141",      "88141\nCANCER UTERO"),
    ("84152",    "84152",      "84152\nCANCER PROSTATA"),
    ("Z030",     "Z030",       "Z030\nTAMIZAJE TB"),
    ("99199.58", "99199.58",   "99199.58\nTBC"),
    ("82270",    "82270",      "82270\nCANCER COLON"),
    ("Z128",     "Z128",       "Z128\nCANCER PIEL"),
    ("99386.03", "99386.03",   "99386.03\nEXAMEN MAMA"),
]

# AGREGA ESTA LÍNEA JUSTO AQUÍ:
N_ITEMS = len(ITEMS_CONFIG)


# ─── MESES ESPAÑOL ───────────────────────────────────────────────────────────
MESES_ES = {
    "January": "ENERO",    "February": "FEBRERO",  "March": "MARZO",
    "April": "ABRIL",      "May": "MAYO",           "June": "JUNIO",
    "July": "JULIO",       "August": "AGOSTO",      "September": "SETIEMBRE",
    "October": "OCTUBRE",  "November": "NOVIEMBRE", "December": "DICIEMBRE"
}

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
        <a href="/home" target="_self" class="btn-back"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#1C398E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:5px;flex-shrink:0;"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg> ← Inicio</a>
    """, unsafe_allow_html=True)

    st.markdown('<div class="filtros-header">⚙ Filtros</div>', unsafe_allow_html=True)

    df_tmp = df_raw.with_columns([
        pl.col("Fecha_Atencion").cast(pl.Date),
        pl.col("Fecha_Atencion").dt.month().alias("Mes_Num"),
        pl.col("Fecha_Atencion").dt.strftime("%B").alias("Mes_Nombre"),
    ]).with_columns(pl.col("Mes_Nombre").replace(MESES_ES))

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    lista_ipress = sorted([str(i).strip() for i in df_tmp["Nombre_Establecimiento"].unique().to_list()])
    target_name  = "SAN LUIS BAJO - GRANDE"
    default_sel  = [i for i in lista_ipress if target_name in i]
    sel_ipress   = st.multiselect("🏥 IPRESS", options=lista_ipress, default=default_sel)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    df_meses_lista = df_tmp.select(["Mes_Num", "Mes_Nombre"]).unique().sort("Mes_Num")
    sel_mes = st.multiselect("📅 Mes de Atención", options=df_meses_lista["Mes_Nombre"].to_list())
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.78rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">🔍 Buscar DNI(s)</p>', unsafe_allow_html=True)

    # Botón de limpiar con session_state
    if "dni_input" not in st.session_state:
        st.session_state["dni_input"] = ""

    def _limpiar_dni():
        st.session_state["dni_input"] = ""

    sel_dni_raw = st.text_input(
        "dni_label",
        placeholder="Ej: 70286548, 48066431...",
        key="dni_input",
        label_visibility="collapsed"
    )
    st.button(
        "🗑️ Limpiar búsqueda",
        on_click=_limpiar_dni,
        use_container_width=True,
        help="Limpia el campo de búsqueda de DNI"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<p style="font-size:0.68rem;color:#94a3b8;text-align:center;letter-spacing:0.05em;">'
        'RED SAN PABLO · NIÑO 0-11 AÑOS<br>© César Malca - 2026</p>',
        unsafe_allow_html=True
    )

# ─── ENCABEZADO ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
    <div class="hero-tag">Red San Pablo · 2026</div>
    <h1 class="hero-title">SEGUIMIENTO DE PAQUETE SEGUIMIENTO DE PAQUETE <span>NIÑO</span></h1>
    <p class="hero-sub">Población objetivo: 0 – 11 años · 30 indicadores evaluados</p>
</div>
<div class="divider"></div>
""", unsafe_allow_html=True)

# ─── PREPARAR Y FILTRAR DATOS ────────────────────────────────────────────────
df_base = df_raw.with_columns([
    pl.col("Fecha_Atencion").cast(pl.Date),
    pl.col("Fecha_Atencion").dt.month().alias("Mes_Num"),
    pl.col("Fecha_Atencion").dt.strftime("%B").alias("Mes_Nombre"),
    pl.col("Nombre_Establecimiento").str.strip_chars(),
    # Limpieza estricta de códigos: strip + uppercase para evitar diferencias de capitalización
    pl.col("Codigo_Item").cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias("Codigo_Item"),
    pl.col("Valor_Lab").cast(pl.Utf8).str.strip_chars().fill_null(""),
]).with_columns(pl.col("Mes_Nombre").replace(MESES_ES))

# Filtro edad adulto
df_base = df_base.filter(
    (pl.col("Anio_Actual_Paciente") >= 0) & (pl.col("Anio_Actual_Paciente") <= 11)
)
if sel_ipress:
    df_base = df_base.filter(pl.col("Nombre_Establecimiento").is_in(sel_ipress))
if sel_mes:
    df_base = df_base.filter(pl.col("Mes_Nombre").is_in(sel_mes))

if sel_dni_raw:
    # Esto sigue funcionando igual de bien para 1 o 100 DNIs en una línea
    lista_dni = re.findall(r'\d+', sel_dni_raw)
    
    if lista_dni:
        df_base = df_base.filter(
            pl.col("Numero_Documento_Paciente")
            .cast(pl.Utf8)
            .str.strip_chars()
            .is_in(lista_dni)
        )

# ─── PROCESAMIENTO ────────────────────────────────────────────────────────────
if not df_base.is_empty():

    # Agregar columna Profesional y Paciente unificada
    df_base = df_base.with_columns([
        (pl.col("Apellido_Paterno_Personal") + " " +
         pl.col("Apellido_Materno_Personal") + " " +
         pl.col("Nombres_Personal")).alias("Profesional"),
        (pl.col("Apellido_Paterno_Paciente") + " " +
         pl.col("Apellido_Materno_Paciente") + " " +
         pl.col("Nombres_Paciente")).alias("Paciente"),
    ])

    # Datos demográficos: última atención por paciente
    cols_demo = [
        "Numero_Documento_Paciente", "Paciente",
        "Anio_Actual_Paciente", "Genero", "Descripcion_Financiador",
        "Nombre_Establecimiento", "Lote", "Num_Pag", "Num_Reg",
        "Fecha_Atencion", "Profesional"
    ]
    df_info = (
        df_base
        .sort("Fecha_Atencion", descending=True)
        .unique(subset=["Numero_Documento_Paciente"], keep="first")
        .select(cols_demo)
        .with_columns(pl.col("Fecha_Atencion").dt.strftime("%d/%m/%Y"))
    )

    # Convertir a pandas para construcción item por item (exacta y sin ambigüedad)
    df_pd = df_base.to_pandas()
    # Normalizar códigos en pandas también
    df_pd["Codigo_Item"] = df_pd["Codigo_Item"].astype(str).str.strip().str.upper()
    df_pd["Valor_Lab"]   = df_pd["Valor_Lab"].astype(str).str.strip().fillna("")
    df_pd["Numero_Documento_Paciente"] = df_pd["Numero_Documento_Paciente"].astype(str)
    df_pd["Fecha_Atencion"] = pd.to_datetime(df_pd["Fecha_Atencion"])

    # ── FUNCIÓN AUXILIAR: Obtener la celda de fecha+valor para cada ítem ──────
    # Para cada ítem filtramos exactamente los registros que corresponden,
    # tomamos el más reciente por paciente y armamos "dd/mm/yyyy (valor)" o "dd/mm/yyyy"
   # ── FUNCIÓN AUXILIAR: Obtener la celda de fecha+valor para cada ítem ──────
    def extraer_item(df: pd.DataFrame, cod_item: str, id_col: str) -> dict:
        cod_upper = cod_item.strip().upper()

        if id_col == "99801_TA":
            mask = (df["Codigo_Item"] == cod_upper) & (df["Valor_Lab"] == "1")
        elif id_col == "99801_1":
            mask = (df["Codigo_Item"] == cod_upper) & (df["Valor_Lab"] == "TA")
        else:
            mask = df["Codigo_Item"] == cod_upper

        sub = df[mask].copy()
        if sub.empty:
            return {}

        resultado = {}
        
        # Agrupamos por DNI para que cada paciente sea una sola fila
        for dni, grupo in sub.groupby("Numero_Documento_Paciente"):
            grupo = grupo.sort_values("Fecha_Atencion", ascending=False)
            
            # CASO 99401: Prioridad fecha que más se repite (fecha de paquete)
            if cod_upper == "99401":
                fechas_totales = df[df["Numero_Documento_Paciente"] == dni]["Fecha_Atencion"]
                if not fechas_totales.empty:
                    fecha_paquete = fechas_totales.mode()[0]
                    match = grupo[grupo["Fecha_Atencion"] == fecha_paquete]
                    fila = match.iloc[0] if not match.empty else grupo.iloc[0]
                else:
                    fila = grupo.iloc[0]
                
                fecha_str = fila["Fecha_Atencion"].strftime("%d/%m/%Y")
                vlab = str(fila["Valor_Lab"]).strip()
                resultado[str(dni)] = f"{fecha_str} ({vlab})" if vlab and vlab not in ["", "nan", "None"] else fecha_str

            # CASO VALORES FUSIONADOS (Presión, Agudeza, VIH/Sífilis)
            
            elif cod_upper in ["99199.22", "99173", "86318.01"]:
                ultima_fecha = grupo["Fecha_Atencion"].iloc[0]
                registros_dia = grupo[grupo["Fecha_Atencion"] == ultima_fecha]
                
                fecha_str = ultima_fecha.strftime("%d/%m/%Y")
                
                # ELIMINAMOS .unique() para que jale todos los valores aunque sean iguales
                valores = [str(v).strip() for v in registros_dia["Valor_Lab"] 
                           if str(v).strip() not in ["", "nan", "None"]]
                
                if valores:
                    # Ahora si hay dos "RN", mostrará "RN / RN"
                    resultado[str(dni)] = f"{fecha_str} ({' / '.join(valores)})"
                else:
                    resultado[str(dni)] = fecha_str

            # CASO GENERAL
            else:
                fila = grupo.iloc[0]
                fecha_str = fila["Fecha_Atencion"].strftime("%d/%m/%Y")
                vlab = str(fila["Valor_Lab"]).strip()
                resultado[str(dni)] = f"{fecha_str} ({vlab})" if vlab and vlab not in ["", "nan", "None"] else fecha_str

        return resultado

    # Construir mapa de resultados por ítem
    resultado_items = {
        id_col: extraer_item(df_pd, cod_item, id_col)
        for cod_item, id_col, _ in ITEMS_CONFIG
    }

    # ── ARMAR DATAFRAME FINAL ─────────────────────────────────────────────────
    df_final = df_info.to_pandas()
    df_final["Numero_Documento_Paciente"] = df_final["Numero_Documento_Paciente"].astype(str)

    ids_pivot    = [c[1] for c in ITEMS_CONFIG]
    mapeo_visual = {c[1]: c[2] for c in ITEMS_CONFIG}

    # Asignar cada ítem usando el mapa exacto por DNI
    for id_col in ids_pivot:
        mapa = resultado_items.get(id_col, {})
        df_final[id_col] = df_final["Numero_Documento_Paciente"].map(mapa)  # NaN si no cumple

    # Renombrar a etiquetas visuales
    df_final = df_final.rename(columns=mapeo_visual)
    columnas_indicadores = list(mapeo_visual.values())

    # Calcular avance ANTES de rellenar con ❌
    df_final["Realizados"] = df_final[columnas_indicadores].notna().sum(axis=1)
    df_final["Faltan"]     = N_ITEMS - df_final["Realizados"]
    df_final["Avance %"]   = ((df_final["Realizados"] / N_ITEMS) * 100).round(1)

    # Ahora sí rellenar con ❌ los no realizados
    df_final[columnas_indicadores] = df_final[columnas_indicadores].fillna("❌")

    # Orden de columnas — Paciente y Profesional unificados en una sola columna c/u
    columnas_datos = [
        "Fecha_Atencion", "Lote", "Num_Pag", "Num_Reg",
        "Nombre_Establecimiento", "Numero_Documento_Paciente",
        "Paciente", "Anio_Actual_Paciente", "Genero",
        "Descripcion_Financiador", "Profesional"
    ]
    nuevo_orden = columnas_datos + ["Realizados", "Faltan", "Avance %"] + columnas_indicadores
    df_final = df_final[nuevo_orden]
    df_final = df_final.sort_values("Avance %", ascending=False).reset_index(drop=True)
    df_final.index = df_final.index + 1

    # ── MÉTRICAS ──────────────────────────────────────────────────────────────
    total       = len(df_final)
    completos   = len(df_final[df_final["Avance %"] >= 99.9])
    en_proceso  = len(df_final[(df_final["Avance %"] >= 50) & (df_final["Avance %"] < 99.9)])
    criticos    = len(df_final[df_final["Avance %"] < 50])
    avance_prom = df_final["Avance %"].mean()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">👥</div>
            <div class="metric-label">Total Pacientes</div>
            <div class="metric-value">{total}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">✅</div>
            <div class="metric-label">Completos 100%</div>
            <div class="metric-value green">{completos}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">🔄</div>
            <div class="metric-label">En Proceso ≥50%</div>
            <div class="metric-value yellow">{en_proceso}</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">⚠️</div>
            <div class="metric-label">Críticos &lt;50%</div>
            <div class="metric-value red">{criticos}</div>
        </div>""", unsafe_allow_html=True)
    with col5:
        color_prom = "#059669" if avance_prom >= 70 else "#d97706" if avance_prom >= 40 else "#dc2626"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">📊</div>
            <div class="metric-label">Avance Promedio</div>
            <div class="metric-value" style="color:{color_prom};">{avance_prom:.1f}%</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── TABLA ─────────────────────────────────────────────────────────────────
    styled = (
        df_final.style
        .format({"Avance %": "{:.1f}"})
        .map(
            lambda x: "color: #dc2626; font-weight:600;" if x == "❌"
                      else "color: #059669; font-weight:600;",
            subset=columnas_indicadores
        )
        .map(
            lambda val: (
                "background-color: #dcfce7; color: #166534; font-weight:700;" if val >= 99.9
                else "background-color: #fef9c3; color: #854d0e; font-weight:700;" if val >= 50
                else "background-color: #fee2e2; color: #991b1b; font-weight:700;"
            ),
            subset=["Avance %"]
        )
    )

    st.dataframe(
        styled,
        use_container_width=True,
        height=680,
        column_config={
            "Paciente": st.column_config.TextColumn(
                "Paciente",
                width="large",
                pinned=True,          # columna fija al scroll horizontal
            ),
            "Numero_Documento_Paciente": st.column_config.TextColumn(
                "DNI",
                width="small",
                pinned=True,          # DNI también fijo junto al nombre
            ),
            "Avance %": st.column_config.NumberColumn(
                "Avance %",
                format="%.1f",
                width="small",
            ),
            "Realizados": st.column_config.NumberColumn(width="small"),
            "Faltan":     st.column_config.NumberColumn(width="small"),
            "Profesional": st.column_config.TextColumn(width="large"),
        },
        selection_mode="single-row",   # activa el resaltado de fila al hacer clic
    )

 # ── DESCARGA ──────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_dl, col_info = st.columns([2, 3])
    with col_dl:
        import io
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_final.to_excel(writer, index=True, sheet_name="Niño")
        excel_bytes = buffer.getvalue()
        st.download_button(
            label="📥 Descargar Reporte Excel",
            data=excel_bytes,
            file_name="nino_san_pablo_2026.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with col_info:
        st.markdown(
            f'<p style="color:#64748b;font-size:0.78rem;padding-top:12px;">'
            f'Reporte con <b style="color:#0369a1;">{total}</b> pacientes · '
            f'Filtro: <b style="color:#0369a1;">{"Todos los meses" if not sel_mes else ", ".join(sel_mes)}</b>'
            f'</p>',
            unsafe_allow_html=True
        )
 
else:
    st.markdown("""
    <div class="no-data">
        <div class="no-data-icon">⚙️</div>
        <div class="no-data-title">Configure los filtros para visualizar los datos</div>
        <p style="color:#64748b;font-size:0.85rem;margin-top:8px;">Use el panel lateral para seleccionar IPRESS y período de atención.</p>
    </div>
    """, unsafe_allow_html=True)