"""
Ruta Flask para el Tablero HIS
Portada.py:
    from tablero_his_flask import tablero_his_bp
    app.register_blueprint(tablero_his_bp)
"""

from flask import Blueprint, request
import polars as pl
import pandas as pd
import plotly.graph_objects as go
import os, datetime, calendar as _cal, base64
from urllib.parse import urlencode, quote_plus
from sqlalchemy import create_engine

tablero_his_bp = Blueprint("tablero_his", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── CONEXIÓN SUPABASE ────────────────────────────────────────────────────────
_SUPA_PASSWORD = os.environ.get("SUPABASE_PASSWORD", "TU_CONTRASEÑA_AQUI")
_SUPA_URL = (
    f"postgresql://postgres.exrktvebngrkhvjtkyhb:{quote_plus(_SUPA_PASSWORD)}"
    f"@aws-1-us-east-2.pooler.supabase.com:6543/postgres"
)
_engine = create_engine(_SUPA_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)

# ─── CACHÉ DE OPCIONES (se carga una sola vez al arrancar) ───────────────────
_cache_opciones = {}

def _cargar_opciones():
    """Carga las opciones de filtros una sola vez y las guarda en memoria."""
    global _cache_opciones
    if _cache_opciones:
        return _cache_opciones
    try:
        from sqlalchemy import text
        with _engine.connect() as con:
            ipress = sorted([r[0] for r in con.execute(text(
                'SELECT DISTINCT "Nombre_Establecimiento" FROM atenciones WHERE "Nombre_Establecimiento" IS NOT NULL'
            )).fetchall()])
            items = sorted([r[0] for r in con.execute(text(
                'SELECT DISTINCT "Codigo_Item" FROM atenciones WHERE "Codigo_Item" IS NOT NULL'
            )).fetchall()])
            edades = sorted([str(r[0]) for r in con.execute(text(
                'SELECT DISTINCT "Edad_Reg" FROM atenciones WHERE "Edad_Reg" IS NOT NULL'
            )).fetchall()])
            meses = sorted([r[0] for r in con.execute(text(
                'SELECT DISTINCT "Mes" FROM atenciones WHERE "Mes" IS NOT NULL'
            )).fetchall()])
        _cache_opciones = {
            "ipress": ipress,
            "items":  items,
            "edades": edades,
            "meses":  meses,
        }
        print(f"✅ Caché de opciones cargado — {len(ipress)} IPRESS, {len(items)} items")
    except Exception as e:
        print(f"⚠️ Error cargando caché: {e}")
    return _cache_opciones

# Precargar al importar el módulo (en segundo plano)
import threading
threading.Thread(target=_cargar_opciones, daemon=True).start()

def _build_where(p_ipress, p_item, p_edad, p_mes, p_desde, p_hasta):
    """Construye cláusula WHERE y params para los filtros activos."""
    where, params = [], {}
    if p_ipress:
        where.append('"Nombre_Establecimiento" = :ipress')
        params["ipress"] = p_ipress[0]
    if p_item:
        phs = ",".join([f":item{i}" for i in range(len(p_item))])
        where.append(f'"Codigo_Item" IN ({phs})')
        for i,v in enumerate(p_item): params[f"item{i}"] = v
    if p_edad:
        phs = ",".join([f":edad{i}" for i in range(len(p_edad))])
        where.append(f'CAST("Edad_Reg" AS TEXT) IN ({phs})')
        for i,v in enumerate(p_edad): params[f"edad{i}"] = v
    if p_mes:
        nums = [str(MESES_INV[m]) for m in p_mes if m in MESES_INV]
        if nums:
            phs = ",".join([f":mes{i}" for i in range(len(nums))])
            where.append(f'CAST("Mes" AS INTEGER) IN ({phs})')
            for i,v in enumerate(nums): params[f"mes{i}"] = int(v)
    if p_desde:
        where.append('"Fecha_Atencion" >= :desde')
        params["desde"] = p_desde
    if p_hasta:
        where.append('"Fecha_Atencion" <= :hasta')
        params["hasta"] = p_hasta
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return clause, params

def _consultar(sql, params=None):
    from sqlalchemy import text
    with _engine.connect() as con:
        result = con.execute(text(sql), params or {})
        return result.fetchall()

def _cargar_datos(p_ipress, p_item, p_edad, p_mes, p_desde, p_hasta):
    """Devuelve solo las filas filtradas — para la tabla de personal."""
    where, params = _build_where(p_ipress, p_item, p_edad, p_mes, p_desde, p_hasta)
    sql = f'SELECT * FROM atenciones {where} LIMIT 5000'
    from sqlalchemy import text
    df_pd = pd.read_sql(text(sql), _engine, params=params)
    return pl.from_pandas(df_pd)

def _cargar_kpis(where, params):
    """KPIs calculados directamente en SQL."""
    sql = f"""
        SELECT
            COUNT(*) AS total_atenciones,
            COUNT(DISTINCT CASE
                WHEN "Numero_Documento_Paciente" ~ '^[0-9]+$'
                THEN "Numero_Documento_Paciente" END) AS u_pac,
            COUNT(DISTINCT CASE
                WHEN "Numero_Documento_Paciente" ~ '^[0-9]+$'
                AND UPPER(CAST("Id_Condicion_Servicio" AS TEXT)) = 'N'
                THEN "Numero_Documento_Paciente" END) AS n_pac,
            COUNT(DISTINCT CASE
                WHEN "Numero_Documento_Paciente" ~ '^[0-9]+$'
                AND UPPER(CAST("Id_Condicion_Servicio" AS TEXT)) = 'C'
                THEN "Numero_Documento_Paciente" END) AS cont_pac
        FROM atenciones {where}
    """
    rows = _consultar(sql, params)
    if rows:
        r = rows[0]
        total = r[0] or 0
        u = r[1] or 0
        n = r[2] or 0
        c = r[3] or 0
        return total, u, n, c, (n/u if u>0 else 0.0)
    return 0, 0, 0, 0, 0.0

def _cargar_grafico(col, where, params, limit=6):
    """Top N para gráficos — calculado en SQL."""
    null_filter = f'AND "{col}" IS NOT NULL' if where else f'WHERE "{col}" IS NOT NULL'
    sql = f"""
        SELECT CAST("{col}" AS TEXT) as lbl, COUNT(*) as n
        FROM atenciones {where}
        {null_filter}
        GROUP BY "{col}"
        ORDER BY n DESC
        LIMIT {limit}
    """
    rows = _consultar(sql, params)
    return [(r[0], r[1]) for r in rows if r[0] and str(r[0]).strip() not in ("None","")]

def _cargar_personal(where, params):
    """Lista de personal con total de atenciones — calculado en SQL."""
    sql = f"""
        SELECT
            CAST("Apellido_Paterno_Personal" AS TEXT) as ap,
            CAST("Nombres_Personal" AS TEXT) as nom,
            COUNT(*) as total
        FROM atenciones {where}
        WHERE "Apellido_Paterno_Personal" IS NOT NULL
        GROUP BY "Apellido_Paterno_Personal", "Nombres_Personal"
        ORDER BY total DESC
    """
    return _consultar(sql, params)

def _cargar_pacientes(where, params, sel_ap, sel_nom, p_dni):
    """Pacientes de un personal específico o búsqueda por DNI."""
    extra = []
    p2 = dict(params)
    if sel_ap:
        extra.append('CAST("Apellido_Paterno_Personal" AS TEXT) = :sel_ap')
        p2["sel_ap"] = sel_ap
    if sel_nom:
        extra.append('CAST("Nombres_Personal" AS TEXT) = :sel_nom')
        p2["sel_nom"] = sel_nom
    if p_dni:
        extra.append('CAST("Numero_Documento_Paciente" AS TEXT) = :dni')
        p2["dni"] = p_dni
    if not extra:
        return None, p2
    w2 = where + (" AND " if where else "WHERE ") + " AND ".join(extra)
    sql = f'SELECT * FROM atenciones {w2} LIMIT 500'
    from sqlalchemy import text
    df_pd = pd.read_sql(text(sql), _engine, params=p2)
    return pl.from_pandas(df_pd), p2

MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
         7:"Julio",8:"Agosto",9:"Setiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
MESES_INV = {v:k for k,v in MESES.items()}
MAPA_DIAG = {"D":"Definitivo","P":"Presuntivo","R":"Repetitivo",
             "S":"Sintomático","E":"Enfermedad crónica"}
DAZUL = ["#3b82f6","#2563eb","#06b6d4","#0ea5e9","#818cf8","#38bdf8"]
DGRIS = ["#64748b","#475569","#94a3b8","#334155","#cbd5e1","#1e293b"]

# ─── CSS / HTML ESTÁTICO ─────────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ── Variables ── */
:root{
  --bg:       #0d1117;
  --bg2:      #161b22;
  --bg3:      #1c2330;
  --border:   #2a3444;
  --border2:  #334155;
  --accent:   #3b82f6;
  --accent2:  #1d4ed8;
  --cyan:     #06b6d4;
  --gold:     #f59e0b;
  --text:     #e2e8f0;
  --text2:    #94a3b8;
  --text3:    #64748b;
  --success:  #10b981;
  --danger:   #ef4444;
}

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);font-family:'Inter',sans-serif;color:var(--text);}

/* ── Topbar ── */
.topbar{
  background:linear-gradient(90deg,#0d1f4e 0%,#112266 50%,#0d1f4e 100%);
  display:flex;align-items:center;justify-content:space-between;
  padding:0 28px;height:62px;position:sticky;top:0;z-index:100;
  border-bottom:1px solid rgba(59,130,246,0.25);
  box-shadow:0 4px 24px rgba(0,0,0,0.5);
}
.topbar-left{display:flex;align-items:center;gap:14px;}
.topbar-logo{height:38px;width:38px;border-radius:10px;object-fit:contain;
  background:#fff;padding:3px;box-shadow:0 0 0 2px rgba(59,130,246,0.4);}
.topbar-title{font-size:13px;font-weight:800;color:#fff;letter-spacing:0.07em;
  text-transform:uppercase;line-height:1.2;}
.topbar-sub{font-size:10px;color:rgba(255,255,255,0.5);font-weight:500;letter-spacing:0.05em;margin-top:2px;}
.topbar-badge{
  background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.35);
  border-radius:20px;padding:5px 16px;font-size:11px;
  color:rgba(255,255,255,0.8);font-weight:600;
  box-shadow:0 0 10px rgba(59,130,246,0.1);
}

/* ── Layout ── */
.container{padding:1.5rem 2rem;}

/* ── Section labels ── */
.section-label{
  font-size:10px;font-weight:700;color:var(--accent);text-transform:uppercase;
  letter-spacing:0.2em;margin:28px 0 14px;display:flex;align-items:center;gap:12px;
}
.section-label::after{content:'';flex:1;height:1px;
  background:linear-gradient(90deg,rgba(59,130,246,0.3),transparent);}

/* ── Cards ── */
.card{
  background:var(--bg2);border:1px solid var(--border);border-radius:16px;
  padding:20px 22px;box-shadow:0 4px 24px rgba(0,0,0,0.3);margin-bottom:20px;
}

/* ── Grids ── */
.filters-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;}
.filters-grid-cal{display:grid;grid-template-columns:1fr 1fr 2fr;gap:16px;margin-top:16px;}

/* ── Filter labels ── */
.filter-label{font-size:10px;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px;}
.filter-label.active{color:var(--cyan);}

/* ── Selects ── */
select:not([multiple]){
  width:100%;border:1.5px solid var(--border);border-radius:10px;
  padding:10px 12px;font-family:inherit;font-size:13px;color:var(--text);
  background:var(--bg3);outline:none;
  transition:border-color .18s,box-shadow .18s;
  appearance:auto;
}
select:not([multiple]):hover{border-color:var(--border2);}
select:not([multiple]):focus{
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(59,130,246,0.15);
}
select option{background:var(--bg3);color:var(--text);}
select[multiple].hidden-select{display:none;}

/* ── Dropdown personalizado ── */
.dd-wrap{position:relative;width:100%;}
.dd-trigger{
  width:100%;border:1.5px solid var(--border);border-radius:10px;
  padding:10px 12px;font-family:inherit;font-size:13px;color:var(--text);
  background:var(--bg3);cursor:pointer;display:flex;align-items:center;
  justify-content:space-between;gap:8px;user-select:none;
  transition:border-color .18s,box-shadow .18s;
}
.dd-trigger:hover{border-color:var(--border2);}
.dd-trigger.open{
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(59,130,246,0.15);
}
.dd-trigger-text{flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;}
.dd-trigger-text.placeholder{color:var(--text3);}
.dd-badge{
  background:var(--accent);color:#fff;border-radius:10px;
  font-size:10px;font-weight:700;padding:2px 8px;flex-shrink:0;
}
.dd-arrow{flex-shrink:0;transition:transform .2s;color:var(--text3);}
.dd-trigger.open .dd-arrow{transform:rotate(180deg);}
.dd-panel{
  display:none;position:absolute;top:calc(100% + 6px);left:0;right:0;
  background:var(--bg2);border:1.5px solid var(--border);border-radius:12px;
  box-shadow:0 16px 40px rgba(0,0,0,0.5);z-index:200;
  max-height:240px;overflow:hidden;flex-direction:column;
}
.dd-panel.open{display:flex;}
.dd-search{padding:8px 10px;border-bottom:1px solid var(--border);}
.dd-search input{
  width:100%;border:1.5px solid var(--border);border-radius:8px;
  padding:7px 10px;font-size:12px;font-family:inherit;
  color:var(--text);background:var(--bg3);outline:none;
}
.dd-search input:focus{border-color:var(--accent);}
.dd-search input::placeholder{color:var(--text3);}
.dd-list{overflow-y:auto;max-height:180px;padding:4px 0;}
.dd-item{
  display:flex;align-items:center;gap:10px;padding:8px 14px;
  cursor:pointer;font-size:13px;color:var(--text);transition:background .12s;
}
.dd-item:hover{background:rgba(59,130,246,0.1);}
.dd-item.selected{background:rgba(59,130,246,0.15);color:var(--accent);font-weight:600;}
.dd-item input[type=checkbox]{
  width:15px;height:15px;accent-color:var(--accent);flex-shrink:0;cursor:pointer;
}
.dd-empty{padding:16px;text-align:center;color:var(--text3);font-size:12px;}
.dd-footer{
  padding:6px 10px;border-top:1px solid var(--border);
  display:flex;justify-content:flex-end;gap:8px;
}
.dd-btn-clear{
  font-size:11px;color:var(--text3);cursor:pointer;padding:3px 8px;border-radius:6px;
  border:1px solid var(--border);background:var(--bg3);transition:all .15s;
}
.dd-btn-clear:hover{color:var(--danger);border-color:var(--danger);background:rgba(239,68,68,0.08);}

/* ── Inputs ── */
input[type=date]{
  width:100%;border:1.5px solid var(--border);border-radius:10px;
  padding:10px 12px;font-family:inherit;font-size:13px;color:var(--text);
  background:var(--bg3);outline:none;
  transition:border-color .18s,box-shadow .18s;
  color-scheme:dark;
}
input[type=date]:disabled{
  background:var(--bg);color:var(--text3);
  cursor:not-allowed;border-color:var(--border);opacity:0.5;
}
input[type=date]:focus{
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(59,130,246,0.15);
}
input[type=text]{
  border:1.5px solid var(--border);border-radius:10px;
  padding:10px 12px;font-family:inherit;font-size:13px;color:var(--text);
  background:var(--bg3);outline:none;width:100%;
  transition:border-color .18s,box-shadow .18s;
}
input[type=text]::placeholder{color:var(--text3);}
input[type=text]:focus{
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(59,130,246,0.15);
}

/* ── Cal msg ── */
.cal-msg{
  background:rgba(6,182,212,0.07);
  border:1.5px dashed rgba(6,182,212,0.35);
  border-radius:10px;padding:12px 18px;font-size:12px;
  color:var(--cyan);font-weight:500;display:flex;align-items:center;
}

/* ── Buttons ── */
.btn{
  background:linear-gradient(135deg,var(--accent2),var(--accent));
  color:#fff;border:none;border-radius:10px;
  padding:11px 26px;font-size:13px;font-weight:700;cursor:pointer;
  letter-spacing:0.05em;transition:all 0.2s;margin-top:14px;
  box-shadow:0 4px 14px rgba(59,130,246,0.3);
}
.btn:hover{
  background:linear-gradient(135deg,#1a3fc0,var(--accent2));
  box-shadow:0 6px 20px rgba(59,130,246,0.4);
  transform:translateY(-1px);
}
.btn-sm{margin-top:0;padding:10px 18px;}

/* ── KPI grid ── */
.kpi-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px;}
.kpi-card{
  background:var(--bg2);border:1px solid var(--border);border-radius:14px;
  padding:18px 20px;position:relative;overflow:hidden;
  transition:transform .2s,box-shadow .2s;
  box-shadow:0 4px 20px rgba(0,0,0,0.25);
}
.kpi-card:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,0.35);}
.kpi-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--accent),var(--cyan));
  border-radius:14px 14px 0 0;
}
.kpi-card::after{
  content:'';position:absolute;bottom:0;right:0;
  width:80px;height:80px;border-radius:50%;
  background:radial-gradient(circle,rgba(59,130,246,0.06),transparent);
  pointer-events:none;
}
.kpi-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;}
.kpi-icon{
  width:36px;height:36px;border-radius:10px;display:flex;align-items:center;
  justify-content:center;
  background:linear-gradient(135deg,rgba(59,130,246,0.2),rgba(6,182,212,0.1));
  border:1px solid rgba(59,130,246,0.2);
}
.kpi-dot{
  width:7px;height:7px;border-radius:50%;
  background:var(--success);margin-top:4px;
  box-shadow:0 0 6px var(--success);
}
.kpi-value{
  font-size:30px;font-weight:900;color:#fff;line-height:1;
  letter-spacing:-1.5px;margin-bottom:6px;
}
.kpi-label{
  font-size:10px;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:0.14em;
}

/* ── Charts ── */
.charts-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:8px;}
.chart-card{
  background:var(--bg2);border:1px solid var(--border);border-radius:16px;
  overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.25);
  transition:transform .2s,box-shadow .2s;
}
.chart-card:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,0.35);}
.chart-title{
  padding:13px 16px 11px;
  background:linear-gradient(90deg,rgba(59,130,246,0.06),transparent);
  border-bottom:1px solid var(--border);
  font-size:11px;font-weight:700;color:var(--text2);
  text-transform:uppercase;letter-spacing:0.12em;
  display:flex;align-items:center;gap:8px;
}
.chart-accent{
  display:inline-block;width:3px;height:14px;
  background:linear-gradient(180deg,var(--accent),var(--cyan));
  border-radius:2px;
}
.chart-body{background:var(--bg);padding:4px 6px 6px;}

/* ── Tables ── */
.tables-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:8px;}
.table-title{
  font-size:12px;font-weight:700;color:var(--text2);text-transform:uppercase;
  letter-spacing:0.1em;margin-bottom:10px;
  display:flex;align-items:center;gap:8px;flex-wrap:wrap;
}
.table-accent{
  display:inline-block;width:3px;height:14px;
  background:linear-gradient(180deg,var(--accent),var(--cyan));
  border-radius:2px;flex-shrink:0;
}
.pac-badge{
  display:inline-flex;align-items:center;border-radius:20px;
  padding:2px 11px;font-size:11px;font-weight:700;
}
.table-filters{display:flex;gap:10px;margin-bottom:12px;align-items:flex-end;flex-wrap:wrap;}

/* ── Footer ── */
.footer{
  margin-top:48px;padding:20px 0;
  border-top:1px solid var(--border);
  text-align:center;font-size:11px;color:var(--text3);
  letter-spacing:0.04em;
}

/* ── Scrollbar dark ── */
::-webkit-scrollbar{width:6px;height:6px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px;}
::-webkit-scrollbar-thumb:hover{background:var(--accent);}

/* ── Responsive ── */
@media(max-width:900px){
  .filters-grid{grid-template-columns:1fr 1fr;}
  .kpi-grid{grid-template-columns:repeat(3,1fr);}
  .charts-grid{grid-template-columns:1fr 1fr;}
  .tables-grid{grid-template-columns:1fr;}
  .filters-grid-cal{grid-template-columns:1fr 1fr;}
}
"""

JS = """

window.addEventListener('resize', function() {
  document.querySelectorAll('.js-plotly-plot').forEach(function(g) {
    Plotly.relayout(g, {autosize: true});
  });
});

// ── Dropdowns personalizados ──────────────────────────────────────────────
function initDropdowns() {
  document.querySelectorAll('.dd-wrap').forEach(function(wrap) {
    var trigger  = wrap.querySelector('.dd-trigger');
    var panel    = wrap.querySelector('.dd-panel');
    var search   = wrap.querySelector('.dd-search input');
    var list     = wrap.querySelector('.dd-list');
    var hidden   = wrap.querySelector('select.hidden-select');
    var txtEl    = wrap.querySelector('.dd-trigger-text');
    var badge    = wrap.querySelector('.dd-badge');
    var btnClear = wrap.querySelector('.dd-btn-clear');
    var isMes    = hidden && hidden.name === 'mes';
    var MAX_SEL  = isMes ? 2 : 9999;

    function getSelected() {
      return Array.from(hidden.selectedOptions).map(function(o){ return o.value; });
    }

    function updateTrigger() {
      var sel = getSelected();
      if (sel.length === 0) {
        txtEl.textContent = isMes ? 'Todos los meses' : 'Todos';
        txtEl.classList.add('placeholder');
        badge.style.display = 'none';
      } else {
        // Mostrar nombres — para mes el option tiene texto diferente al value
        var labels = Array.from(hidden.selectedOptions).map(function(o){ return o.textContent; });
        txtEl.textContent = labels.length <= 2
          ? labels.join(', ')
          : labels.slice(0,2).join(', ') + ' +' + (labels.length-2) + ' más';
        txtEl.classList.remove('placeholder');
        badge.textContent = sel.length;
        badge.style.display = 'inline-block';
      }
    }

    function renderItems(filter) {
      filter = (filter || '').toLowerCase();
      list.innerHTML = '';
      var opts = Array.from(hidden.options);
      var visible = opts.filter(function(o) {
        return !filter || o.textContent.toLowerCase().includes(filter);
      });
      if (visible.length === 0) {
        list.innerHTML = '<div class="dd-empty">Sin resultados</div>';
        return;
      }
      visible.forEach(function(opt) {
        var item = document.createElement('div');
        item.className = 'dd-item' + (opt.selected ? ' selected' : '');

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = opt.selected;

        var lbl = document.createElement('span');
        lbl.textContent = opt.textContent;

        item.appendChild(cb);
        item.appendChild(lbl);

        // CLICK EN CUALQUIER PARTE DEL ITEM — no cierra el panel
        item.addEventListener('mousedown', function(e) {
          e.preventDefault(); // evita que el panel pierda foco y se cierre
          e.stopPropagation();

          var currentSel = Array.from(hidden.selectedOptions).length;
          if (!opt.selected && currentSel >= MAX_SEL) {
            // Límite alcanzado
            var warn = list.querySelector('.dd-max-warn');
            if (!warn) {
              warn = document.createElement('div');
              warn.className = 'dd-max-warn';
              warn.style.cssText = 'padding:6px 12px;font-size:11px;color:#dc2626;' +
                'background:#fff5f5;border-top:1px solid #fca5a5;text-align:center;';
              warn.textContent = 'Máximo ' + MAX_SEL + ' meses permitidos';
              list.appendChild(warn);
              setTimeout(function() { if (warn.parentNode) warn.parentNode.removeChild(warn); }, 2000);
            }
            return;
          }

          opt.selected = !opt.selected;
          cb.checked = opt.selected;
          item.classList.toggle('selected', opt.selected);
          updateTrigger();
        });

        list.appendChild(item);
      });
    }

    function openPanel() {
      document.querySelectorAll('.dd-panel.open').forEach(function(p) {
        if (p !== panel) {
          p.classList.remove('open');
          p.closest('.dd-wrap').querySelector('.dd-trigger').classList.remove('open');
        }
      });
      trigger.classList.add('open');
      panel.classList.add('open');
      if (search) { search.value = ''; search.focus(); }
      renderItems('');
    }

    function closePanel() {
      trigger.classList.remove('open');
      panel.classList.remove('open');
      if (wrap.dataset.autosubmit) {
        var params = new URLSearchParams();
        Array.from(hidden.selectedOptions).forEach(function(o) {
          params.append(hidden.name, o.value);
        });
        ['ipress','item','edad'].forEach(function(name) {
          var sel = document.querySelector('#formFiltros select[name="' + name + '"]');
          if (sel) {
            Array.from(sel.selectedOptions).forEach(function(o) {
              if (o.value !== '') params.append(name, o.value);
            });
          }
        });
        window.location.href = '/tablero-his?' + params.toString();
      }
    }

    // Toggle panel al hacer click en trigger
    trigger.addEventListener('mousedown', function(e) {
      e.preventDefault();
      e.stopPropagation();
      panel.classList.contains('open') ? closePanel() : openPanel();
    });

    // Panel no propaga — no se cierra al hacer click dentro
    panel.addEventListener('mousedown', function(e) { e.stopPropagation(); });

    // Búsqueda
    if (search) {
      search.addEventListener('input', function() { renderItems(this.value); });
      search.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    }

    // Limpiar
    if (btnClear) {
      btnClear.addEventListener('mousedown', function(e) {
        e.preventDefault();
        e.stopPropagation();
        Array.from(hidden.options).forEach(function(o) { o.selected = false; });
        renderItems(search ? search.value : '');
        updateTrigger();
      });
    }

    updateTrigger();
  });

  // Click fuera → cerrar todos
  document.addEventListener('mousedown', function() {
    document.querySelectorAll('.dd-panel.open').forEach(function(p) {
      p.classList.remove('open');
      p.closest('.dd-wrap').querySelector('.dd-trigger').classList.remove('open');
    });
  });
}

document.addEventListener('DOMContentLoaded', function() {
  initDropdowns();
});

// Al aplicar filtros: limpiar fechas si cambió el mes, limpiar personal si cambió IPRESS
(function(){
  var form = document.getElementById('formFiltros');
  if(!form) return;
  var urlParams = new URLSearchParams(window.location.search);
  var mesBefore    = urlParams.getAll('mes').sort().join(',');
  var ipressBefore = urlParams.getAll('ipress').sort().join(',');

  form.addEventListener('submit', function(){
    // Detectar cambio de mes
    var mesHidden = form.querySelectorAll('select[name="mes"] option:checked');
    var mesAfter  = Array.from(mesHidden).map(function(o){return o.value;}).sort().join(',');
    if(mesAfter !== mesBefore){
      var d = form.querySelector('input[name="desde"]');
      var h = form.querySelector('input[name="hasta"]');
      if(d) d.removeAttribute('name');
      if(h) h.removeAttribute('name');
    }

    // Detectar cambio de IPRESS — limpiar personal
    var ipressHidden = form.querySelectorAll('select[name="ipress"] option:checked');
    var ipressAfter  = Array.from(ipressHidden).map(function(o){return o.value;}).sort().join(',');
    if(ipressAfter !== ipressBefore){
      var p = form.querySelector('input[name="personal"]');
      if(p) p.value = '';
      var d = form.querySelector('input[name="dni"]');
      if(d) d.value = '';
    }
  });
})();
"""

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def _logo_b64():
    for name in ["logo","LOGO","Logo"]:
        for ext in ["png","jpg","jpeg","PNG","JPG","JPEG"]:
            p = os.path.join(BASE_DIR, f"{name}.{ext}")
            if os.path.exists(p):
                with open(p,"rb") as f:
                    return base64.b64encode(f.read()).decode()
    return ""

def abreviar(t, n=22):
    t = str(t).strip()
    return t[:n-1].rstrip()+"…" if len(t)>n else t

def sel_opts(lista, sel):
    sel_str = {str(s) for s in sel}
    out = ""
    for o in lista:
        s = str(o)
        selected = ' selected' if s in sel_str else ''
        esc = s.replace('&','&amp;').replace('"','&quot;').replace('<','&lt;')
        out += f'<option value="{esc}"{selected}>{esc}</option>'
    return out

ARROW_SVG = ('<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
             'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
             'stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>')

def build_dropdown(name, lista, sel, placeholder="Todos"):
    sel_str = {str(s) for s in sel}
    opts_html = sel_opts(lista, sel)
    if sel_str:
        txt = ", ".join(sorted(sel_str))
        badge = f'<span class="dd-badge">{len(sel_str)}</span>'
        ph_class = ""
    else:
        txt = placeholder
        badge = '<span class="dd-badge" style="display:none">0</span>'
        ph_class = " placeholder"
    return (
        f'<div class="dd-wrap">'
        f'<div class="dd-trigger" tabindex="0">'
        f'<span class="dd-trigger-text{ph_class}">{txt}</span>'
        f'{badge}'
        f'<span class="dd-arrow">{ARROW_SVG}</span>'
        f'</div>'
        f'<div class="dd-panel">'
        f'<div class="dd-search"><input type="text" placeholder="Buscar..."></div>'
        f'<div class="dd-list"></div>'
        f'<div class="dd-footer"><span class="dd-btn-clear">Limpiar</span></div>'
        f'</div>'
        f'<select name="{name}" multiple class="hidden-select">{opts_html}</select>'
        f'</div>'
    )

def build_select_simple(name, lista, sel, placeholder="Todas"):
    """Select simple de un solo valor (sin checkbox, sin dropdown personalizado)."""
    sel_str = sel[0] if sel else ""
    opts = f'<option value="">{placeholder}</option>'
    for o in lista:
        s = str(o)
        esc = s.replace('&','&amp;').replace('"','&quot;').replace('<','&lt;')
        selected = ' selected' if s == sel_str else ''
        opts += f'<option value="{esc}"{selected}>{esc}</option>'
    return (
        f'<select name="{name}" style="width:100%;border:1.5px solid #c5d3ea;border-radius:8px;'
        f'padding:9px 10px;font-family:inherit;font-size:13px;color:#334155;'
        f'background:#fff;outline:none;">{opts}</select>'
    )

def tabla_html(df_pd, num_cols=None, fecha_cols=None):
    num_cols   = num_cols   or []
    fecha_cols = fecha_cols or []
    ths = '<th style="width:38px;text-align:center;color:#c5d3ea;">#</th>'
    for c in df_pd.columns:
        al = "right" if c in num_cols else "left"
        ths += f'<th style="text-align:{al};">{c}</th>'
    rows = ""
    for i, (_, row) in enumerate(df_pd.iterrows(), 1):
        bg = "background:#1c2330;" if i % 2 == 0 else "background:#161b22;"
        celdas = f'<td style="text-align:center;color:#475569;font-size:11px;{bg}">{i}</td>'
        for col in df_pd.columns:
            val = row[col]; val = "" if pd.isna(val) else str(val)
            if col in num_cols:
                st = f"text-align:right;color:#60a5fa;font-weight:700;{bg}"
            elif col in fecha_cols:
                st = f"color:#64748b;font-size:12px;{bg}"
            else:
                st = f"color:#cbd5e1;{bg}"
            celdas += f'<td style="{st}">{val}</td>'
        rows += f"<tr>{celdas}</tr>"
    return (
        '<div style="overflow-x:auto;max-height:400px;overflow-y:auto;'
        'border-radius:12px;border:1px solid #2a3444;">'
        '<table style="width:100%;border-collapse:collapse;font-family:Inter,sans-serif;font-size:13px;">'
        f'<thead style="position:sticky;top:0;">'
        f'<tr style="background:linear-gradient(90deg,#1d2d50,#1a2744);color:#e2e8f0;">{ths}</tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )

# ─── PLOTLY ──────────────────────────────────────────────────────────────────
def hacer_radar(cats_raw, vals):
    import math
    cs = [abreviar(c, 16) for c in cats_raw]
    max_v = max(vals) if vals else 1

    # Escala raíz cuadrada: comprime dominantes, expande los pequeños
    sqrt_vals = [math.sqrt(v) for v in vals]
    max_sqrt  = max(sqrt_vals) if sqrt_vals else 1
    vals_norm = [round(v / max_sqrt * 100, 1) for v in sqrt_vals]

    cc = cs + [cs[0]]
    vc = vals_norm + [vals_norm[0]]
    fc = cats_raw + [cats_raw[0]]

    def fmt(v):
        if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
        if v >= 1_000:     return f"{v/1_000:.1f}k"
        return str(v)

    fig = go.Figure()

    # Área principal
    fig.add_trace(go.Scatterpolar(
        r=vc, theta=cc, fill='toself',
        fillcolor='rgba(28,57,142,0.13)',
        line=dict(color='#1C398E', width=2.5),
        marker=dict(color='#1C398E', size=7, line=dict(color='white', width=1.5)),
        customdata=list(zip(fc, vals + [vals[0]])),
        hovertemplate="<b>%{customdata[0]}</b><br>Total: %{customdata[1]:,}<extra></extra>",
        mode='lines+markers',
        showlegend=False,
    ))

    # Texto sobre cada punto (solo los n originales, no el de cierre)
    fig.add_trace(go.Scatterpolar(
        r=[v + 8 for v in vals_norm],   # desplazar levemente hacia afuera
        theta=cs,
        mode='text',
        text=[fmt(v) for v in vals],
        textfont=dict(size=10, color='#1C398E', family='Inter', weight=700),
        hoverinfo='skip',
        showlegend=False,
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter,sans-serif", color="#94a3b8", size=10),
        height=300, margin=dict(l=65,r=65,t=65,b=65), showlegend=False,
        polar=dict(
            bgcolor="rgba(28,43,64,0.4)",
            domain=dict(x=[0.0,1.0],y=[0.0,1.0]),
            angularaxis=dict(
                tickfont=dict(size=8.5, color="#64748b", family="Inter"),
                linecolor="rgba(59,130,246,0.15)",
                gridcolor="rgba(59,130,246,0.08)",
                direction="clockwise",
            ),
            radialaxis=dict(
                visible=True, range=[0, 120],
                showticklabels=False,
                gridcolor="rgba(59,130,246,0.08)",
                linecolor="rgba(59,130,246,0.10)",
                layer="below traces",
            )
        )
    )
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"responsive":True,"displayModeBar":False})

def hacer_barras(etiquetas_raw, vals, colores):
    ets = [abreviar(e,28) for e in etiquetas_raw]
    n   = len(vals)
    clrs = colores[:n] if len(colores)>=n else ["#1C398E"]*n
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=vals, y=ets, orientation='h',
        marker=dict(color=clrs,line=dict(width=0)),
        text=[f"{v:,}" for v in vals], textposition="outside",
        textfont=dict(color="#94a3b8",size=10,family="Inter"),
        customdata=list(zip(etiquetas_raw,vals)),
        hovertemplate="<b>%{customdata[0]}</b><br>Total: %{customdata[1]:,}<extra></extra>",
        cliponaxis=False,
    ))
    mv = max(vals) if vals else 1
    fig.update_xaxes(range=[0, mv*1.28])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter,sans-serif", color="#94a3b8", size=10),
        height=300, margin=dict(l=8,r=50,t=8,b=8), showlegend=False,
        xaxis=dict(showgrid=True,gridcolor="rgba(42,52,68,0.8)",zeroline=False,
                   tickfont=dict(color="#64748b",size=9),linecolor="#2a3444"),
        yaxis=dict(showgrid=False,zeroline=False,
                   tickfont=dict(color="#94a3b8",size=10),
                   linecolor="#2a3444",automargin=True)
    )
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"responsive":True,"displayModeBar":False})

EMPTY = '<div style="padding:60px 20px;text-align:center;color:#94a3b8;font-size:13px;">Sin datos</div>'

# ─── ROUTE ────────────────────────────────────────────────────────────────────

# ── KPI helper (fuera de la route para no contaminar el f-string) ──
def _kpi(label, value, svg_path):
    return (
        '<div class="kpi-card">'
        '<div class="kpi-header">'
        f'<div class="kpi-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        f'stroke="#60a5fa" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f'{svg_path}</svg></div>'
        '<div class="kpi-dot"></div></div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-label">{label}</div>'
        '</div>'
    )
@tablero_his_bp.route("/tablero-his")
def tablero_his():
    p_mes      = request.args.getlist("mes") or ["Enero"]
    # Limitar a máximo 2 meses para evitar Out of Memory en Render gratuito
    MAX_MESES = 2
    if len(p_mes) > MAX_MESES:
        p_mes = p_mes[:MAX_MESES]
    p_ipress   = [request.args.get("ipress","")] if request.args.get("ipress","") else []
    p_item     = request.args.getlist("item")
    p_edad     = request.args.getlist("edad")
    p_desde    = request.args.get("desde","")
    p_hasta    = request.args.get("hasta","")
    p_personal = request.args.get("personal","")  # formato: "AP||NOM"
    p_dni      = "".join(c for c in request.args.get("dni","") if c.isdigit())

    try:
        # Opciones desde caché
        opts = _cargar_opciones()
        ipress_opts = opts.get("ipress", [])
        item_opts   = opts.get("items",  [])
        edad_opts   = opts.get("edades", [])
        meses_nums  = opts.get("meses",  [])
        meses_noms  = [MESES.get(int(m), str(m)) for m in meses_nums]

        # WHERE clause compartida para todas las consultas
        where, params = _build_where(p_ipress, p_item, p_edad, p_mes, p_desde, p_hasta)

        # KPIs directo en SQL
        total_atenciones, u_pac, n_pac, cont_pac, pct_cap = _cargar_kpis(where, params)

        # Gráficos directo en SQL
        rows_c1 = _cargar_grafico("Descripcion_Item",       where, params)
        rows_c2 = _cargar_grafico("Tipo_Diagnostico",       where, params)
        rows_c3 = _cargar_grafico("Nombre_Establecimiento", where, params)
        rows_c4 = _cargar_grafico("Descripcion_Financiador",where, params)

        # Personal directo en SQL
        personal_sql = _cargar_personal(where, params)

    except Exception as e:
        return f"<h3 style='padding:40px;font-family:monospace'>Error Supabase: {e}</h3>", 500

    fecha_excel = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    COL_FECHA  = "Fecha_Atencion"
    anio_datos = 2026

    # ── Filtros en memoria (df_f vacío — ya no se usa para cálculos) ──
    df_f = pl.DataFrame()

    # Calendario
    calendario_activo = len(p_mes) == 1
    min_fecha_str = max_fecha_str = ""

    if calendario_activo:
        primer_mes_n = MESES_INV.get(p_mes[0], 1)
        try:
            from sqlalchemy import text
            with _engine.connect() as con:
                r = con.execute(text(
                    'SELECT MIN("Fecha_Atencion"), MAX("Fecha_Atencion") '
                    'FROM atenciones WHERE "Mes" = :mes'
                ), {"mes": primer_mes_n}).fetchone()
                if r and r[0]:
                    min_fecha_str = str(r[0])[:10]
                    max_fecha_str = str(r[1])[:10]
        except: pass
        if not min_fecha_str:
            min_fecha_str = f"{anio_datos}-{primer_mes_n:02d}-01"
            max_fecha_str = f"{anio_datos}-{primer_mes_n:02d}-{_cal.monthrange(anio_datos,primer_mes_n)[1]:02d}"
        if not p_desde: p_desde = min_fecha_str
        if not p_hasta: p_hasta = max_fecha_str

    # ── KPIs (ya calculados en SQL) ──
    # total_atenciones, u_pac, n_pac, cont_pac, pct_cap ya están disponibles

    # ── Gráficos ──
    html_c1=html_c2=html_c3=html_c4=""

    if rows_c1:
        html_c1 = hacer_radar([r[0] for r in rows_c1], [r[1] for r in rows_c1])

    if rows_c2:
        etiq = [MAPA_DIAG.get(str(r[0]).strip().upper(), str(r[0]).strip()) for r in rows_c2]
        html_c2 = hacer_barras(etiq, [r[1] for r in rows_c2], DAZUL)

    if rows_c3:
        html_c3 = hacer_barras([r[0] for r in rows_c3], [r[1] for r in rows_c3], DAZUL)

    if rows_c4:
        html_c4 = hacer_barras([r[0] for r in rows_c4], [r[1] for r in rows_c4], DGRIS)

    # ── Personal (ya calculado en SQL) ──
    html_t_personal = ""
    personal_data = [("— Todos —", "", "")]

    if personal_sql and total_atenciones > 0:
        for row in personal_sql:
            ap  = str(row[0] or "").strip()
            nom = str(row[1] or "").strip()
            personal_data.append((f"{ap} {nom}".strip(), ap, nom))

        # Buscar por "AP||NOM" — estable ante cambios de filtro
        sel_ap = sel_nom = sel_label = ""
        p_idx = 0
        if p_personal and "||" in p_personal:
            parts = p_personal.split("||", 1)
            sel_ap  = parts[0].strip()
            sel_nom = parts[1].strip()
            for i, (lbl, ap, nom) in enumerate(personal_data):
                if ap == sel_ap and nom == sel_nom:
                    p_idx = i; sel_label = lbl; break
        # sel_ap ya está vacío si no se encontró match

        # Tabla de personal desde datos SQL
        import pandas as pd
        df_personal_pd = pd.DataFrame([(r[0], r[1], r[2]) for r in personal_sql],
                                       columns=["Apellido_Paterno_Personal","Nombres_Personal","Total_Atenciones"])
        if sel_ap:
            mask = df_personal_pd["Apellido_Paterno_Personal"].astype(str).str.strip() == sel_ap
            if sel_nom:
                mask = mask & (df_personal_pd["Nombres_Personal"].astype(str).str.strip() == sel_nom)
            res_p_disp = df_personal_pd[mask]
        else:
            fila_tot = pd.DataFrame({"Apellido_Paterno_Personal":["TOTAL GENERAL"],
                                     "Nombres_Personal":[""],
                                     "Total_Atenciones":[int(df_personal_pd["Total_Atenciones"].sum())]})
            res_p_disp = pd.concat([df_personal_pd, fila_tot], ignore_index=True)
        html_t_personal = tabla_html(res_p_disp, num_cols=["Total_Atenciones"])
    else:
        p_idx = 0
        sel_label, sel_ap, sel_nom = "— Todos —", "", ""

    opciones_personal_sel = [(f"{ap}||{nom}" if ap else "", lbl) for lbl,ap,nom in personal_data]

    # ── Pacientes desde SQL ──
    df_pac_pl, _ = _cargar_pacientes(where, params, sel_ap, sel_nom, p_dni)
    if df_pac_pl is not None:
        cols_pac = ["Numero_Documento_Paciente"]
        for c in ["Nombres_Paciente","Apellido_Paterno_Paciente","Fecha_Ultima_Regla"]:
            if c in df_pac_pl.columns: cols_pac.append(c)
        df_lista_pl = (df_pac_pl
                       .filter(pl.col("Numero_Documento_Paciente").cast(pl.Utf8)
                               .str.strip_chars().str.contains(r"^[0-9]+$"))
                       .select(cols_pac)
                       .unique(subset=["Numero_Documento_Paciente"], keep="first"))
        if "Fecha_Ultima_Regla" in df_lista_pl.columns:
            df_lista_pl = df_lista_pl.with_columns(
                pl.col("Fecha_Ultima_Regla").cast(pl.Utf8).fill_null("").alias("Fecha_Ultima_Regla"))
        df_lista = df_lista_pl.to_pandas()
    else:
        import pandas as pd
        df_lista = pd.DataFrame()
    n_pac_filt = len(df_lista)
    html_t_pac = tabla_html(df_lista, fecha_cols=["Fecha_Ultima_Regla"])

    # ── Construir piezas HTML (sin f-string para las que contienen Plotly) ──
    logo_b64  = _logo_b64()
    if logo_b64:
        logo_tag = f'<img class="topbar-logo" src="data:image/png;base64,{logo_b64}">'
    else:
        # Logo SVG embebido — cruz médica con fondo blanco, siempre visible
        logo_tag = (
            '<div class="topbar-logo" style="display:flex;align-items:center;justify-content:center;background:#fff;border-radius:8px;">'
            '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="9" y="2" width="6" height="20" rx="2" fill="#1C398E"/>'
            '<rect x="2" y="9" width="20" height="6" rx="2" fill="#1C398E"/>'
            '</svg></div>'
        )

    # Calendario HTML
    cal_disabled = "" if calendario_activo else "disabled"
    lbl_clase = "active" if calendario_activo else ""
    lbl_suf   = "" if calendario_activo else " — inactivo"
    if len(p_mes)==0:
        cal_extra = '<div class="cal-msg">📅 Selecciona <b>un mes</b> para activar el filtro de días</div>'
    elif len(p_mes)==1:
        if p_desde and p_hasta:
            try:
                d_s = datetime.date.fromisoformat(p_desde).strftime("%d/%m/%Y")
                h_s = datetime.date.fromisoformat(p_hasta).strftime("%d/%m/%Y")
                cal_extra = (
                    '<div style="background:rgba(59,130,246,0.08);border:1.5px solid rgba(59,130,246,0.2);border-radius:10px;'
                    'padding:11px 18px;font-size:13px;color:#cbd5e1;display:flex;align-items:center;gap:10px;">'
                    f'<span style="font-size:18px;">🗓️</span>'
                    f'<span>Filtrando del <b style="color:#60a5fa;">{d_s}</b>'
                    f' al <b style="color:#60a5fa;">{h_s}</b></span></div>'
                )
            except: cal_extra=""
        else: cal_extra=""
    else:
        cal_extra = f'<div class="cal-msg">⚠️ Máximo 2 meses permitidos. Selecciona <b>un solo mes</b> para el filtro de días.</div>'

    # Hidden inputs
    hidden = ""
    for m in p_mes:    hidden += f'<input type="hidden" name="mes"    value="{m}">\n'
    for i in p_ipress: hidden += f'<input type="hidden" name="ipress" value="{i}">\n'
    for i in p_item:   hidden += f'<input type="hidden" name="item"   value="{i}">\n'
    for e in p_edad:   hidden += f'<input type="hidden" name="edad"   value="{e}">\n'
    if p_desde: hidden += f'<input type="hidden" name="desde" value="{p_desde}">\n'
    if p_hasta: hidden += f'<input type="hidden" name="hasta" value="{p_hasta}">\n'

    # Badge pacientes
    bc = "#1C398E" if n_pac_filt>0 else "#dc2626"
    bb = "rgba(28,57,142,0.08)" if n_pac_filt>0 else "rgba(220,38,38,0.07)"
    bbd= "rgba(28,57,142,0.2)"  if n_pac_filt>0 else "rgba(220,38,38,0.2)"
    dni_hint = f" · DNI: {p_dni}" if p_dni else ""
    titulo_pac = ("Pacientes de "+sel_label if sel_ap else "Lista de Pacientes")
    badge_pac = (f'<span class="pac-badge" style="color:{bc};background:{bb};border:1px solid {bbd};">'
                 f'● {n_pac_filt:,}{dni_hint}</span>')

    badge_personal = ""
    if sel_ap:
        badge_personal = (f'<div style="display:inline-flex;align-items:center;gap:10px;background:rgba(59,130,246,0.1);'
                          f'border:1px solid rgba(59,130,246,0.25);border-radius:20px;padding:6px 16px;margin-bottom:10px;'
                          f'font-family:Inter,sans-serif;font-size:13px;color:#cbd5e1;">'
                          f'👤 Mostrando pacientes de: <b style="color:#60a5fa;">{sel_label}</b></div>')

    qs = urlencode([("mes",m) for m in p_mes]+[("ipress",i) for i in p_ipress]+
                   [("item",i) for i in p_item]+[("edad",e) for e in p_edad]+
                   ([("desde",p_desde)] if p_desde else [])+([("hasta",p_hasta)] if p_hasta else []))
    limpiar_tabla = (f'<a href="/tablero-his?{qs}" style="font-size:12px;color:#94a3b8;text-decoration:none;">✕ Limpiar</a>'
                     if sel_ap or p_dni else "")

    # Opciones select personal (pre-construidas para evitar f-string anidado)
    _sel_personal_opts = ''.join(
        '<option value="' + v + '"' + (' selected' if v == (f'{sel_ap}||{sel_nom}' if sel_ap else '') else '') + '>' + lbl + '</option>'
        for v,lbl in opciones_personal_sel
    )

    # ── HTML estático (sin Plotly adentro — se inyecta con replace luego) ──
    html = (
        '<!DOCTYPE html><html lang="es"><head>'
        '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '<title>Red San Pablo \u2014 Tablero HIS</title>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">'
        '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>'
        
        f'<style>{CSS}</style></head><body>'

        # Topbar
        '<div class="topbar">'
        f'<div class="topbar-left">{logo_tag}'
        '<div><div class="topbar-title">RED DE SALUD SAN PABLO \u2014 2026</div>'
        '<div class="topbar-sub">Tablero HIS \u00b7 An\u00e1lisis de Atenciones</div></div></div>'
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<a href="/" style="display:flex;align-items:center;gap:6px;'
        'background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.22);'
        'border-radius:20px;padding:5px 16px;font-size:12px;font-weight:600;'
        'color:#fff;text-decoration:none;letter-spacing:0.04em;">'
        '<svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5"'
        ' stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24">'
        '<polyline points="15 18 9 12 15 6"/></svg> Inicio</a>'
        f'<div class="topbar-badge">\u25cf &nbsp;Actualizado: {fecha_excel}</div>'
        '</div></div>'

        '<div class="container">'

        # Filtros
        '<div class="section-label">B\u00fasqueda Avanzada</div>'
        '<div class="card"><form method="GET" action="/tablero-his" id="formFiltros">'
        '<div class="filters-grid">'
        '<div><div class="filter-label">Mes</div>' + build_dropdown("mes", meses_noms, p_mes, "Todos los meses") + '</div>'
        '<div><div class="filter-label">IPRESS</div>' + build_select_simple("ipress", ipress_opts, p_ipress, "Todas") + '</div>'
        '<div><div class="filter-label">C\u00f3digo \u00cdtem</div>' + build_dropdown("item", item_opts, p_item, "Todos") + '</div>'
        '<div><div class="filter-label">Edad Paciente</div>' + build_dropdown("edad", edad_opts, p_edad, "Todas") + '</div>'
        '</div>'
        '<div class="filters-grid-cal">'
        f'<div><div class="filter-label {lbl_clase}">Fecha Desde{lbl_suf}</div>'
        f'<input type="date" name="desde" value="{p_desde}" min="{min_fecha_str}" max="{max_fecha_str}" {cal_disabled}></div>'
        f'<div><div class="filter-label {lbl_clase}">Fecha Hasta{lbl_suf}</div>'
        f'<input type="date" name="hasta" value="{p_hasta}" min="{min_fecha_str}" max="{max_fecha_str}" {cal_disabled}></div>'
        f'<div style="display:flex;align-items:center;">{cal_extra}</div>'
        '</div>'
        f'<input type="hidden" name="personal" value="{sel_ap}||{sel_nom}">'
        f'<input type="hidden" name="dni" value="{p_dni}">'
        '<div style="display:flex;align-items:center;gap:16px;margin-top:14px;">'
        '<button type="submit" class="btn" style="margin-top:0;">Aplicar filtros</button>'
        '<a href="/tablero-his" style="display:inline-flex;align-items:center;gap:7px;'
        'font-size:12px;font-weight:600;color:#94a3b8;text-decoration:none;'
        'border:1.5px solid #2a3444;border-radius:10px;padding:10px 18px;'
        'background:#1c2330;letter-spacing:0.04em;'
        'transition:all 0.18s;" '
        'onmouseover="this.style.color=\'#ef4444\';this.style.borderColor=\'#ef4444\';this.style.background=\'rgba(239,68,68,0.08)\'" '
        'onmouseout="this.style.color=\'#94a3b8\';this.style.borderColor=\'#2a3444\';this.style.background=\'#1c2330\'">'
        '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
        'Limpiar todo</a>'
        '</div></form></div>'

        # KPIs
        '<div class="section-label">Indicadores Clave</div>'
        '<div class="kpi-grid">'
        + _kpi("Atenciones",f"{total_atenciones:,}",
               '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>')
        + _kpi("Pacientes \u00danicos",f"{u_pac:,}",
               '<circle cx="9" cy="7" r="3"/><circle cx="16" cy="8" r="2.5"/><path d="M2 20c0-3.3 3.1-6 7-6s7 2.7 7 6"/><path d="M20 20c0-2.2-1.8-4-4-4"/>')
        + _kpi("Nuevos",f"{n_pac:,}",
               '<circle cx="12" cy="6" r="3.5"/><path d="M5 20c0-3.9 3.1-7 7-7s7 3.1 7 7"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="16" y1="11" x2="22" y2="11"/>')
        + _kpi("Continuadores",f"{cont_pac:,}",
               '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>')
        + _kpi("% Captaci\u00f3n",f"{pct_cap:.2f}",
               '<path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/>')
        + '</div>'

        # Gráficos — marcadores que se reemplazan luego
        '<div class="section-label">An\u00e1lisis Operativo</div>'
        '<div class="charts-grid">'
        '<div class="chart-card"><div class="chart-title"><span class="chart-accent"></span>Top Actividades</div>'
        '<div class="chart-body">__CHART1__</div></div>'
        '<div class="chart-card"><div class="chart-title"><span class="chart-accent"></span>Diagn\u00f3sticos</div>'
        '<div class="chart-body">__CHART2__</div></div>'
        '<div class="chart-card"><div class="chart-title"><span class="chart-accent"></span>Atenciones \u00d7 IPRESS</div>'
        '<div class="chart-body">__CHART3__</div></div>'
        '<div class="chart-card"><div class="chart-title"><span class="chart-accent"></span>Tipo de Seguro</div>'
        '<div class="chart-body">__CHART4__</div></div>'
        '</div>'

        # Tablas
        '<div class="section-label" id="tablas">Detalle de Registros</div>'
        f'<form method="GET" action="/tablero-his#tablas" style="margin-bottom:14px;">{hidden}'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:end;margin-bottom:12px;">'
        f'<div><div class="filter-label">Filtrar por personal</div>'
        f'<select name="personal" onchange="this.form.submit()" style="width:100%;border:1.5px solid #2a3444;border-radius:10px;padding:10px 12px;font-family:inherit;font-size:13px;color:#e2e8f0;background:#1c2330;outline:none;">'
        + _sel_personal_opts
        + '</select></div>'
        '<div><div class="filter-label">Buscar por DNI</div>'
        '<div style="display:flex;gap:8px;">'
        f'<input type="text" name="dni" placeholder="Ej: 12345678" value="{p_dni}" maxlength="8"'
        ' oninput="this.value=this.value.replace(/[^0-9]/g,\'\')" style="flex:1;">'
        '<button type="submit" class="btn btn-sm" style="white-space:nowrap;flex-shrink:0;">Buscar</button>'
        + (f'<a href="/tablero-his?{qs}" style="display:flex;align-items:center;padding:0 12px;font-size:13px;color:#64748b;text-decoration:none;border:1.5px solid #2a3444;border-radius:10px;flex-shrink:0;">×</a>' if sel_ap or p_dni else '')
        + '</div></div></div></form>'
        f'{badge_personal}'
        '<div class="tables-grid">'
        '<div><div class="table-title"><span class="table-accent"></span>Personal de Salud</div>'
        f'{html_t_personal}</div>'
        '<div>'
        f'<div class="table-title"><span class="table-accent"></span>{titulo_pac}{badge_pac}</div>'
        f'{html_t_pac}</div></div>'

        '<div class="footer">C\u00e9sar E. Malca Cabanillas \u00b7 Red de Salud San Pablo \u2014 2026</div>'
        '</div>'
        f'<script>{JS}</script>'
        '</body></html>'
    )

    # ── Inyectar Plotly HTML con replace (seguro, sin f-string) ──
    html = html.replace("__CHART1__", html_c1 or EMPTY)
    html = html.replace("__CHART2__", html_c2 or EMPTY)
    html = html.replace("__CHART3__", html_c3 or EMPTY)
    html = html.replace("__CHART4__", html_c4 or EMPTY)

    return html
