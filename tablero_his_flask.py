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
from urllib.parse import urlencode

tablero_his_bp = Blueprint("tablero_his", __name__)

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_PARQUET = os.path.join(BASE_DIR, "data", "reporte.parquet")
_DF_CACHE_HIS = None

MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
         7:"Julio",8:"Agosto",9:"Setiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
MESES_INV = {v:k for k,v in MESES.items()}
MAPA_DIAG = {"D":"Definitivo","P":"Presuntivo","R":"Repetitivo",
             "S":"Sintomático","E":"Enfermedad crónica"}
DAZUL = ["#1C398E","#1e40af","#1d4ed8","#2563eb","#3b82f6","#60a5fa"]
DGRIS = ["#334155","#475569","#64748b","#94a3b8","#cbd5e1","#e2e8f0"]

# ─── CSS / HTML ESTÁTICO ─────────────────────────────────────────────────────
CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:#f4f6fb;font-family:'Inter',sans-serif;}
.topbar{background:#1C398E;display:flex;align-items:center;justify-content:space-between;
  padding:0 28px;height:56px;position:sticky;top:0;z-index:100;
  box-shadow:0 2px 12px rgba(28,57,142,0.18);}
.topbar-left{display:flex;align-items:center;gap:14px;}
.topbar-logo{height:36px;width:36px;border-radius:8px;object-fit:contain;background:#fff;padding:3px;}
.topbar-title{font-size:13px;font-weight:800;color:#fff;letter-spacing:0.06em;text-transform:uppercase;line-height:1.2;}
.topbar-sub{font-size:10px;color:rgba(255,255,255,0.65);font-weight:500;letter-spacing:0.04em;}
.topbar-badge{background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);
  border-radius:20px;padding:4px 14px;font-size:11px;color:rgba(255,255,255,0.85);font-weight:600;}
.container{padding:1.5rem 2rem;}
.section-label{font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:0.15em;margin:24px 0 14px;display:flex;align-items:center;gap:10px;}
.section-label::after{content:'';flex:1;height:1px;background:#e2e8f0;}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;
  padding:18px 20px;box-shadow:0 1px 6px rgba(0,0,0,0.05);margin-bottom:20px;}
.filters-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;}
.filters-grid-cal{display:grid;grid-template-columns:1fr 1fr 2fr;gap:16px;margin-top:14px;}
.filter-label{font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:0.1em;margin-bottom:5px;}
.filter-label.active{color:#1C398E;}
/* selects normales (tabla personal) */
select:not([multiple]){width:100%;border:1.5px solid #c5d3ea;border-radius:8px;
  padding:9px 10px;font-family:inherit;font-size:13px;color:#334155;
  background:#fff;outline:none;}
select:focus{border-color:#1C398E;box-shadow:0 0 0 3px rgba(28,57,142,0.1);}
/* multiselect oculto - usado solo para enviar valores */
select[multiple].hidden-select{display:none;}

/* ── Dropdown personalizado ── */
.dd-wrap{position:relative;width:100%;}
.dd-trigger{
  width:100%;border:1.5px solid #c5d3ea;border-radius:8px;
  padding:9px 12px 9px 12px;font-family:inherit;font-size:13px;color:#334155;
  background:#fff;cursor:pointer;display:flex;align-items:center;
  justify-content:space-between;gap:8px;user-select:none;
  transition:border-color .18s,box-shadow .18s;
}
.dd-trigger:hover{border-color:#a0b8d8;}
.dd-trigger.open{border-color:#1C398E;box-shadow:0 0 0 3px rgba(28,57,142,0.1);}
.dd-trigger-text{flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;}
.dd-trigger-text.placeholder{color:#94a3b8;}
.dd-badge{background:#1C398E;color:#fff;border-radius:10px;
  font-size:10px;font-weight:700;padding:1px 7px;flex-shrink:0;}
.dd-arrow{flex-shrink:0;transition:transform .2s;}
.dd-trigger.open .dd-arrow{transform:rotate(180deg);}
.dd-panel{
  display:none;position:absolute;top:calc(100% + 4px);left:0;right:0;
  background:#fff;border:1.5px solid #c5d3ea;border-radius:10px;
  box-shadow:0 8px 24px rgba(28,57,142,0.13);z-index:200;
  max-height:240px;overflow:hidden;flex-direction:column;
}
.dd-panel.open{display:flex;}
.dd-search{
  padding:8px 10px;border-bottom:1px solid #f1f5f9;
}
.dd-search input{
  width:100%;border:1.5px solid #e2e8f0;border-radius:6px;
  padding:6px 10px;font-size:12px;font-family:inherit;color:#334155;outline:none;
}
.dd-search input:focus{border-color:#1C398E;}
.dd-list{overflow-y:auto;max-height:180px;padding:4px 0;}
.dd-item{
  display:flex;align-items:center;gap:10px;padding:7px 12px;
  cursor:pointer;font-size:13px;color:#334155;transition:background .12s;
}
.dd-item:hover{background:#f0f4ff;}
.dd-item.selected{background:#e8eef8;color:#1C398E;font-weight:600;}
.dd-item input[type=checkbox]{
  width:15px;height:15px;accent-color:#1C398E;flex-shrink:0;cursor:pointer;
}
.dd-empty{padding:16px;text-align:center;color:#94a3b8;font-size:12px;}
.dd-footer{
  padding:6px 10px;border-top:1px solid #f1f5f9;
  display:flex;justify-content:flex-end;gap:8px;
}
.dd-btn-clear{
  font-size:11px;color:#94a3b8;cursor:pointer;padding:3px 8px;border-radius:5px;
  border:1px solid #e2e8f0;background:#f8fafc;transition:all .15s;
}
.dd-btn-clear:hover{color:#dc2626;border-color:#fca5a5;background:#fff5f5;}

input[type=date]{width:100%;border:1.5px solid #c5d3ea;border-radius:8px;
  padding:9px 12px;font-family:inherit;font-size:13px;color:#334155;
  background:#fff;outline:none;}
input[type=date]:disabled{background:#f8fafc;color:#cbd5e1;cursor:not-allowed;border-color:#e2e8f0;}
input[type=date]:focus{border-color:#1C398E;}
.cal-msg{background:#f5f8ff;border:1.5px dashed #94a3b8;border-radius:10px;
  padding:11px 18px;font-size:12px;color:#4a6090;font-weight:500;display:flex;align-items:center;}
.btn{background:#1C398E;color:#fff;border:none;border-radius:8px;
  padding:10px 24px;font-size:13px;font-weight:700;cursor:pointer;
  letter-spacing:0.04em;transition:background 0.18s;margin-top:14px;}
.btn:hover{background:#16307a;}
.btn-sm{margin-top:0;padding:9px 18px;}
.kpi-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px;}
.kpi-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;
  padding:16px 18px;box-shadow:0 1px 6px rgba(0,0,0,0.05);position:relative;}
.kpi-card::before{content:'';position:absolute;top:0;left:0;right:0;
  height:3px;background:#1C398E;border-radius:12px 12px 0 0;}
.kpi-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;}
.kpi-icon{width:34px;height:34px;border-radius:8px;display:flex;align-items:center;
  justify-content:center;background:#e8eef8;}
.kpi-dot{width:6px;height:6px;border-radius:50%;background:#1C398E;margin-top:4px;}
.kpi-value{font-size:28px;font-weight:800;color:#0f172a;line-height:1;
  letter-spacing:-1px;margin-bottom:5px;}
.kpi-label{font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.12em;}
.charts-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:8px;}
.chart-card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;
  overflow:hidden;box-shadow:0 1px 8px rgba(0,0,0,0.06);}
.chart-title{padding:12px 14px 10px;background:#fff;border-bottom:1px solid #eef2fb;
  font-size:11px;font-weight:700;color:#334155;text-transform:uppercase;
  letter-spacing:0.1em;display:flex;align-items:center;gap:8px;}
.chart-accent{display:inline-block;width:3px;height:13px;background:#1C398E;border-radius:2px;}
.chart-body{background:#f8fafc;padding:4px 6px 6px;}
.tables-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:8px;}
.table-title{font-size:12px;font-weight:700;color:#475569;text-transform:uppercase;
  letter-spacing:0.1em;margin-bottom:10px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.table-accent{display:inline-block;width:3px;height:13px;background:#1C398E;
  border-radius:2px;flex-shrink:0;}
.pac-badge{display:inline-flex;align-items:center;border-radius:20px;
  padding:1px 10px;font-size:11px;font-weight:700;}
.table-filters{display:flex;gap:10px;margin-bottom:12px;align-items:flex-end;flex-wrap:wrap;}
input[type=text]{border:1.5px solid #c5d3ea;border-radius:8px;
  padding:9px 12px;font-family:inherit;font-size:13px;color:#334155;
  background:#fff;outline:none;width:100%;}
input[type=text]:focus{border-color:#1C398E;}

.footer{margin-top:40px;padding:20px 0;border-top:1px solid #f1f5f9;
  text-align:center;font-size:11px;color:#94a3b8;}
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

    function getSelected() {
      return Array.from(hidden.selectedOptions).map(function(o){return o.value;});
    }
    function updateTrigger() {
      var sel = getSelected();
      if (sel.length === 0) {
        txtEl.textContent = 'Todos';
        txtEl.classList.add('placeholder');
        badge.style.display = 'none';
      } else {
        txtEl.textContent = sel.join(', ');
        txtEl.classList.remove('placeholder');
        badge.textContent = sel.length;
        badge.style.display = 'inline-block';
      }
    }
    function renderItems(filter) {
      filter = (filter||'').toLowerCase();
      list.innerHTML = '';
      var opts = Array.from(hidden.options);
      var visible = opts.filter(function(o){
        return !filter || o.value.toLowerCase().includes(filter);
      });
      if (visible.length===0) {
        list.innerHTML = '<div class="dd-empty">Sin resultados</div>'; return;
      }
      visible.forEach(function(opt) {
        var sel = opt.selected;
        var item = document.createElement('div');
        item.className = 'dd-item' + (sel?' selected':'');
        item.innerHTML = '<input type="checkbox"' + (sel?' checked':'') + '><span>' + opt.value + '</span>';
        item.querySelector('input').addEventListener('change', function(e) {
          opt.selected = e.target.checked;
          item.classList.toggle('selected', e.target.checked);
          updateTrigger();
        });
        list.appendChild(item);
      });
    }
    function openPanel() {
      document.querySelectorAll('.dd-panel.open').forEach(function(p){
        if(p!==panel){p.classList.remove('open');p.closest('.dd-wrap').querySelector('.dd-trigger').classList.remove('open');}
      });
      trigger.classList.add('open');
      panel.classList.add('open');
      if(search){search.value='';search.focus();}
      renderItems('');
    }
    function closePanel(){trigger.classList.remove('open');panel.classList.remove('open');}

    trigger.addEventListener('click', function(e){
      e.stopPropagation();
      panel.classList.contains('open') ? closePanel() : openPanel();
    });
    if(search) search.addEventListener('input',function(){renderItems(this.value);});
    if(btnClear) btnClear.addEventListener('click',function(e){
      e.stopPropagation();
      Array.from(hidden.options).forEach(function(o){o.selected=false;});
      renderItems(search?search.value:'');
      updateTrigger();
    });
    updateTrigger();
  });
  document.addEventListener('click', function(){
    document.querySelectorAll('.dd-panel.open').forEach(function(p){
      p.classList.remove('open');
      p.closest('.dd-wrap').querySelector('.dd-trigger').classList.remove('open');
    });
  });
}
document.addEventListener('DOMContentLoaded', initDropdowns);
"""

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def _logo_b64():
    for ext in ["png","jpg","jpeg"]:
        p = os.path.join(BASE_DIR, f"logo.{ext}")
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

def tabla_html(df_pd, num_cols=None, fecha_cols=None):
    num_cols   = num_cols   or []
    fecha_cols = fecha_cols or []
    ths = '<th style="width:38px;text-align:center;color:#c5d3ea;">#</th>'
    for c in df_pd.columns:
        al = "right" if c in num_cols else "left"
        ths += f'<th style="text-align:{al};">{c}</th>'
    rows = ""
    for i, (_, row) in enumerate(df_pd.iterrows(), 1):
        celdas = f'<td style="text-align:center;color:#94a3b8;font-size:11px;">{i}</td>'
        for col in df_pd.columns:
            val = row[col]; val = "" if pd.isna(val) else str(val)
            if col in num_cols:
                st = "text-align:right;color:#1C398E;font-weight:700;"
            elif col in fecha_cols:
                st = "color:#94a3b8;font-size:12px;"
            else:
                st = ""
            celdas += f'<td style="{st}">{val}</td>'
        rows += f"<tr>{celdas}</tr>"
    return (
        '<div style="overflow-x:auto;max-height:400px;overflow-y:auto;'
        'border-radius:10px;border:1px solid #e2e8f0;">'
        '<table style="width:100%;border-collapse:collapse;font-family:Inter,sans-serif;font-size:13px;">'
        f'<thead style="position:sticky;top:0;">'
        f'<tr style="background:#1C398E;color:#fff;">{ths}</tr></thead>'
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
        font=dict(family="Inter,sans-serif", color="#334155", size=10),
        height=300, margin=dict(l=65,r=65,t=65,b=65), showlegend=False,
        polar=dict(
            bgcolor="rgba(248,250,252,0.6)",
            domain=dict(x=[0.0,1.0],y=[0.0,1.0]),
            angularaxis=dict(
                tickfont=dict(size=8.5, color="#475569", family="Inter"),
                linecolor="rgba(28,57,142,0.15)",
                gridcolor="rgba(28,57,142,0.08)",
                direction="clockwise",
            ),
            radialaxis=dict(
                visible=True, range=[0, 120],
                showticklabels=False,
                gridcolor="rgba(28,57,142,0.08)",
                linecolor="rgba(28,57,142,0.10)",
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
        textfont=dict(color="#1e2f55",size=10,family="Inter"),
        customdata=list(zip(etiquetas_raw,vals)),
        hovertemplate="<b>%{customdata[0]}</b><br>Total: %{customdata[1]:,}<extra></extra>",
        cliponaxis=False,
    ))
    mv = max(vals) if vals else 1
    fig.update_xaxes(range=[0, mv*1.28])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter,sans-serif", color="#334155", size=10),
        height=300, margin=dict(l=8,r=50,t=8,b=8), showlegend=False,
        xaxis=dict(showgrid=True,gridcolor="#f1f5f9",zeroline=False,
                   tickfont=dict(color="#64748b",size=9),linecolor="#e2e8f0"),
        yaxis=dict(showgrid=False,zeroline=False,
                   tickfont=dict(color="#334155",size=10),
                   linecolor="#e2e8f0",automargin=True)
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
        f'stroke="#1C398E" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f'{svg_path}</svg></div>'
        '<div class="kpi-dot"></div></div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-label">{label}</div>'
        '</div>'
    )
@tablero_his_bp.route("/tablero-his")
def tablero_his():
    p_mes      = request.args.getlist("mes") or ["Enero"]
    p_ipress   = request.args.getlist("ipress")
    p_item     = request.args.getlist("item")
    p_edad     = request.args.getlist("edad")
    p_desde    = request.args.get("desde","")
    p_hasta    = request.args.get("hasta","")
    p_personal = request.args.get("personal","")
    p_dni      = "".join(c for c in request.args.get("dni","") if c.isdigit())

    global _DF_CACHE_HIS
    if _DF_CACHE_HIS is None:
        try:
            COLS_HIS = [
                "Mes", "Nombre_Establecimiento", "Codigo_Item", "Descripcion_Item",
                "Edad_Reg", "Tipo_Diagnostico", "Descripcion_Financiador",
                "Numero_Documento_Paciente", "Id_Condicion_Servicio",
                "Apellido_Paterno_Personal", "Nombres_Personal",
                "Nombres_Paciente", "Apellido_Paterno_Paciente",
                "Fecha_Ultima_Regla", "Fecha_Atencion",
            ]
            todas = pl.read_parquet(ARCHIVO_PARQUET, n_rows=1).columns
            cols_leer = [c for c in todas if c.strip() in COLS_HIS]
            _DF_CACHE_HIS = pl.read_parquet(ARCHIVO_PARQUET, columns=cols_leer if cols_leer else None)
        except Exception as e:
            return f"<h3 style='padding:40px;font-family:monospace'>Error: {e}</h3>", 500
    df_raw = _DF_CACHE_HIS

    try:
        mtime = os.path.getmtime(ARCHIVO_PARQUET)
        fecha_excel = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
    except:
        fecha_excel = "N/D"

    COL_FECHA = next(
        (c for c in df_raw.columns if "fecha" in c.lower() and "regla" not in c.lower()), None
    )
    anio_datos = 2026
    try:
        if "Anio" in df_raw.columns:
            anios = sorted([int(a) for a in df_raw["Anio"].unique().drop_nulls().to_list()])
            if anios: anio_datos = anios[0]
    except: pass

    # Opciones
    meses_nums  = sorted(df_raw["Mes"].unique().drop_nulls().to_list())
    meses_noms  = [MESES.get(int(m), str(m)) for m in meses_nums]
    ipress_opts = sorted(df_raw["Nombre_Establecimiento"].unique().drop_nulls().to_list())
    item_opts   = sorted(df_raw["Codigo_Item"].unique().drop_nulls().to_list())
    edad_opts   = sorted([str(x) for x in df_raw["Edad_Reg"].unique().drop_nulls().to_list()])

    # ── Filtros ──
    df_f = df_raw.clone()
    if p_ipress: df_f = df_f.filter(pl.col("Nombre_Establecimiento").is_in(p_ipress))
    if p_item:   df_f = df_f.filter(pl.col("Codigo_Item").is_in(p_item))
    if p_edad:   df_f = df_f.filter(pl.col("Edad_Reg").cast(pl.Utf8).is_in(p_edad))

    if p_mes:
        mapa_num = {
            "Enero":["1","01","1.0"],"Febrero":["2","02","2.0"],
            "Marzo":["3","03","3.0"],"Abril":["4","04","4.0"],
            "Mayo":["5","05","5.0"],"Junio":["6","06","6.0"],
            "Julio":["7","07","7.0"],"Agosto":["8","08","8.0"],
            "Setiembre":["9","09","9.0"],"Octubre":["10","10.0"],
            "Noviembre":["11","11.0"],"Diciembre":["12","12.0"]
        }
        lista = []
        for m in p_mes:
            lista.append(m)
            lista.extend(mapa_num.get(m,[]))
        df_f = (df_f
                .with_columns(pl.col("Mes").cast(pl.Utf8).str.strip_chars().alias("_m"))
                .filter(pl.col("_m").is_in(lista))
                .drop("_m"))

    # Calendario
    calendario_activo = len(p_mes) == 1
    min_fecha_str = max_fecha_str = ""

    if calendario_activo:
        primer_mes_n = MESES_INV.get(p_mes[0], 1)
        if COL_FECHA:
            try:
                _dm = df_raw.filter(
                    pl.col("Mes").cast(pl.Utf8).str.strip_chars().is_in(
                        [str(primer_mes_n),
                         f"0{primer_mes_n}" if primer_mes_n<10 else str(primer_mes_n),
                         f"{primer_mes_n}.0"]
                    )
                ).with_columns(pl.col(COL_FECHA).cast(pl.Utf8).str.slice(0,10).alias("_fs"))
                for _fmt in ["%Y-%m-%d","%d/%m/%Y","%d-%m-%Y"]:
                    try:
                        _p = _dm.with_columns(
                            pl.col("_fs").str.strptime(pl.Date,_fmt,strict=False).alias("_fd")
                        ).filter(pl.col("_fd").is_not_null())
                        if _p.height>0:
                            min_fecha_str = str(_p["_fd"].min())
                            max_fecha_str = str(_p["_fd"].max())
                            break
                    except: continue
            except: pass
        if not min_fecha_str:
            min_fecha_str = f"{anio_datos}-{primer_mes_n:02d}-01"
            max_fecha_str = f"{anio_datos}-{primer_mes_n:02d}-{_cal.monthrange(anio_datos,primer_mes_n)[1]:02d}"
        if not p_desde: p_desde = min_fecha_str
        if not p_hasta: p_hasta = max_fecha_str

        if COL_FECHA and (p_desde or p_hasta):
            try:
                fd = datetime.date.fromisoformat(p_desde) if p_desde else None
                fh = datetime.date.fromisoformat(p_hasta) if p_hasta else None
            except: fd = fh = None
            if fd or fh:
                df_tmp = df_f.with_columns(pl.col(COL_FECHA).cast(pl.Utf8).str.slice(0,10).alias("_fs"))
                df_cf = None
                for fmt in ["%Y-%m-%d","%d/%m/%Y","%d-%m-%Y"]:
                    try:
                        _t = df_tmp.with_columns(pl.col("_fs").str.strptime(pl.Date,fmt,strict=False).alias("_fd"))
                        if _t.filter(pl.col("_fd").is_not_null()).height>0: df_cf=_t; break
                    except: continue
                if df_cf is not None:
                    if fd: df_cf = df_cf.filter(pl.col("_fd") >= pl.lit(fd))
                    if fh: df_cf = df_cf.filter(pl.col("_fd") <= pl.lit(fh))
                    df_f = df_cf.drop(["_fs","_fd"])
                else:
                    df_f = df_tmp.drop("_fs")

    # ── KPIs ──
    total_atenciones = df_f.height
    u_pac = n_pac = cont_pac = 0; pct_cap = 0.0
    if "Numero_Documento_Paciente" in df_f.columns and total_atenciones>0:
        dc = (df_f.filter(pl.col("Numero_Documento_Paciente").cast(pl.Utf8)
                          .str.strip_chars().str.contains(r"^[0-9]+$"))
              .with_columns(pl.col("Numero_Documento_Paciente").cast(pl.Utf8)
                            .str.strip_chars().alias("_dni")))
        u_pac    = dc["_dni"].n_unique()
        n_pac    = dc.filter(pl.col("Id_Condicion_Servicio").cast(pl.Utf8).str.to_uppercase()=="N")["_dni"].n_unique()
        cont_pac = dc.filter(pl.col("Id_Condicion_Servicio").cast(pl.Utf8).str.to_uppercase()=="C")["_dni"].n_unique()
        pct_cap  = (n_pac/u_pac) if u_pac>0 else 0.0

    # ── Gráficos — se generan como strings HTML completos ──
    html_c1=html_c2=html_c3=html_c4=""

    if "Descripcion_Item" in df_f.columns and total_atenciones>0:
        r = (df_f.group_by("Descripcion_Item").agg(pl.count().alias("N"))
             .sort("N",descending=True).head(5).to_pandas())
        if not r.empty:
            html_c1 = hacer_radar(r["Descripcion_Item"].tolist(), r["N"].tolist())

    if "Tipo_Diagnostico" in df_f.columns and total_atenciones>0:
        r = (df_f.group_by("Tipo_Diagnostico").agg(pl.count().alias("N"))
             .sort("N",descending=True).to_pandas())
        if not r.empty:
            r["Tipo_Diagnostico"] = r["Tipo_Diagnostico"].map(
                lambda x: MAPA_DIAG.get(str(x).strip().upper(), str(x).strip()))
            html_c2 = hacer_barras(r["Tipo_Diagnostico"].tolist(), r["N"].tolist(), DAZUL)

    if "Nombre_Establecimiento" in df_f.columns and total_atenciones>0:
        r = (df_f.group_by("Nombre_Establecimiento").agg(pl.count().alias("N"))
             .sort("N",descending=True).head(5).to_pandas())
        if not r.empty:
            html_c3 = hacer_barras(r["Nombre_Establecimiento"].tolist(), r["N"].tolist(), DAZUL)

    if "Descripcion_Financiador" in df_f.columns and total_atenciones>0:
        r = (df_f.group_by("Descripcion_Financiador").agg(pl.count().alias("N"))
             .sort("N",descending=True).head(6)
             .filter(pl.col("Descripcion_Financiador").is_not_null()).to_pandas())
        r = r[r["Descripcion_Financiador"].astype(str).str.strip()!="None"]
        if not r.empty:
            html_c4 = hacer_barras(r["Descripcion_Financiador"].tolist(), r["N"].tolist(), DGRIS)

    # ── Personal ──
    # El valor del select es el ÍNDICE numérico ("0", "1", ...) para evitar
    # problemas con apellidos compuestos como "DE LA CRUZ"
    cols_p = [c for c in ["Apellido_Paterno_Personal","Nombres_Personal"] if c in df_f.columns]
    html_t_personal = ""
    # Lista de (label, ap, nom) — índice 0 = "— Todos —"
    personal_data = [("— Todos —", "", "")]
    res_p = pd.DataFrame()
    if cols_p and total_atenciones>0:
        res_p = (df_f.group_by(cols_p).agg(pl.count().alias("Total_Atenciones"))
                 .sort("Total_Atenciones",descending=True).to_pandas())
        for _, row in res_p.iterrows():
            ap  = str(row.get("Apellido_Paterno_Personal","") or "").strip()
            nom = str(row.get("Nombres_Personal","") or "").strip()
            personal_data.append((f"{ap} {nom}".strip(), ap, nom))

    # p_personal es "APELLIDO||NOMBRE" — estable ante cambios de filtro
    sel_ap = sel_nom = sel_label = ""
    p_idx = 0
    if p_personal and "||" in p_personal:
        parts = p_personal.split("||", 1)
        sel_ap = parts[0].strip(); sel_nom = parts[1].strip()
        for i, (lbl, ap, nom) in enumerate(personal_data):
            if ap == sel_ap and nom == sel_nom:
                p_idx = i; sel_label = lbl; break
    if p_idx == 0:
        sel_label = "— Todos —"; sel_ap = ""; sel_nom = ""

    if not res_p.empty:
        if sel_ap:
            # Buscar la fila que coincide con el personal seleccionado
            mask = pd.Series([True]*len(res_p), index=res_p.index)
            if "Apellido_Paterno_Personal" in res_p.columns:
                mask = mask & (res_p["Apellido_Paterno_Personal"].astype(str).str.strip() == sel_ap)
            if "Nombres_Personal" in res_p.columns and sel_nom:
                mask = mask & (res_p["Nombres_Personal"].astype(str).str.strip() == sel_nom)
            res_p_disp = res_p[mask] if mask.any() else res_p.head(1)
        else:
            fila_tot = pd.DataFrame({"Apellido_Paterno_Personal":["TOTAL GENERAL"],
                                     "Nombres_Personal":[""],
                                     "Total_Atenciones":[int(res_p["Total_Atenciones"].sum())]})
            res_p_disp = pd.concat([res_p, fila_tot], ignore_index=True)
        html_t_personal = tabla_html(res_p_disp, num_cols=["Total_Atenciones"])

    # Opciones para el select — valor = índice numérico
    opciones_personal_sel = [(f'{ap}||{nom}' if ap else '', lbl) for lbl,ap,nom in personal_data]

    # ── Pacientes ──
    cols_pac = ["Numero_Documento_Paciente"]
    for c in ["Nombres_Paciente","Apellido_Paterno_Paciente","Fecha_Ultima_Regla"]:
        if c in df_f.columns: cols_pac.append(c)
    df_para_pac = df_f.clone()
    if sel_ap and cols_p:
        _f = pl.lit(True)
        if "Apellido_Paterno_Personal" in df_f.columns:
            _f = _f & (pl.col("Apellido_Paterno_Personal").cast(pl.Utf8).str.strip_chars()==sel_ap)
        if "Nombres_Personal" in df_f.columns and sel_nom:
            _f = _f & (pl.col("Nombres_Personal").cast(pl.Utf8).str.strip_chars()==sel_nom)
        df_para_pac = df_f.filter(_f)
    df_lista = (df_para_pac
                .filter(pl.col("Numero_Documento_Paciente").cast(pl.Utf8)
                        .str.strip_chars().str.contains(r"^[0-9]+$"))
                .select(cols_pac)
                .unique(subset=["Numero_Documento_Paciente"],keep="first")
                .to_pandas())
    if p_dni:
        df_lista = df_lista[df_lista["Numero_Documento_Paciente"].astype(str).str.contains(p_dni,na=False)]
    if "Fecha_Ultima_Regla" in df_lista.columns:
        df_lista["Fecha_Ultima_Regla"] = (pd.to_datetime(df_lista["Fecha_Ultima_Regla"],errors="coerce")
                                          .dt.strftime("%d-%m-%Y").fillna(""))
    n_pac_filt  = len(df_lista)
    html_t_pac  = tabla_html(df_lista, fecha_cols=["Fecha_Ultima_Regla"])

    # ── Construir piezas HTML (sin f-string para las que contienen Plotly) ──
    logo_b64  = _logo_b64()
    logo_tag  = (f'<img class="topbar-logo" src="data:image/png;base64,{logo_b64}">'
                 if logo_b64 else "")

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
                    '<div style="background:#e8eef8;border:1.5px solid #c5d3ea;border-radius:10px;'
                    'padding:11px 18px;font-size:13px;color:#334155;display:flex;align-items:center;gap:10px;">'
                    f'<span style="font-size:18px;">🗓️</span>'
                    f'<span>Filtrando del <b style="color:#1C398E;">{d_s}</b>'
                    f' al <b style="color:#1C398E;">{h_s}</b></span></div>'
                )
            except: cal_extra=""
        else: cal_extra=""
    else:
        cal_extra = f'<div class="cal-msg">⚠️ Selecciona <b>un solo mes</b> para el filtro de días (tienes {len(p_mes)})</div>'

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
        badge_personal = (f'<div style="display:inline-flex;align-items:center;gap:10px;background:#e8eef8;'
                          f'border:1px solid #c5d3ea;border-radius:20px;padding:6px 16px;margin-bottom:10px;'
                          f'font-family:Inter,sans-serif;font-size:13px;color:#334155;">'
                          f'👤 Mostrando pacientes de: <b style="color:#1C398E;">{sel_label}</b></div>')

    qs = urlencode([("mes",m) for m in p_mes]+[("ipress",i) for i in p_ipress]+
                   [("item",i) for i in p_item]+[("edad",e) for e in p_edad]+
                   ([("desde",p_desde)] if p_desde else [])+([("hasta",p_hasta)] if p_hasta else []))
    limpiar_tabla = (f'<a href="/tablero-his?{qs}" style="font-size:12px;color:#94a3b8;text-decoration:none;">✕ Limpiar</a>'
                     if p_idx > 0 or p_dni else "")

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
        '<div class="card"><form method="GET" action="/tablero-his">'
        '<div class="filters-grid">'
        '<div><div class="filter-label">Mes</div>' + build_dropdown("mes", meses_noms, p_mes, "Todos los meses") + '</div>'
        '<div><div class="filter-label">IPRESS</div>' + build_dropdown("ipress", ipress_opts, p_ipress, "Todas") + '</div>'
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
        '<button type="submit" class="btn">Aplicar filtros</button>'
        '<a href="/tablero-his" style="font-size:12px;color:#94a3b8;text-decoration:none;">\u2715 Limpiar todo</a>'
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
        f'<select name="personal" onchange="this.form.submit()" style="width:100%;border:1.5px solid #c5d3ea;border-radius:8px;padding:9px 10px;font-family:inherit;font-size:13px;color:#334155;background:#fff;outline:none;">'
        + _sel_personal_opts
        + '</select></div>'
        '<div><div class="filter-label">Buscar por DNI</div>'
        '<div style="display:flex;gap:8px;">'
        f'<input type="text" name="dni" placeholder="Ej: 12345678" value="{p_dni}" maxlength="8"'
        ' oninput="this.value=this.value.replace(/[^0-9]/g,\'\')" style="flex:1;">'
        '<button type="submit" class="btn btn-sm" style="white-space:nowrap;flex-shrink:0;">Buscar</button>'
        + (f'<a href="/tablero-his?{qs}" style="display:flex;align-items:center;padding:0 12px;font-size:13px;color:#94a3b8;text-decoration:none;border:1.5px solid #e2e8f0;border-radius:8px;flex-shrink:0;">×</a>' if sel_ap or p_dni else '')
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
