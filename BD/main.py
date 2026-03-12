import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import os, base64, time, tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from fpdf import FPDF

# ── PALETA ───────────────────────────────────────────────────────────────────
C = {
    "primary":       "#233dff",
    "primary_soft": "#eef0ff",
    "n900":          "#111827",
    "n600":          "#4b5563",
    "n400":          "#9ca3af",
    "n100":          "#f3f4f6",
    "bg":            "#f9fafb",
}
BANK_PALETTE = [
    "#233dff","#1a2eb8","#3d55ff","#0f1d7a",
    "#576dff","#1533cc","#7085ff","#2d47e6",
    "#8aaeff","#4169ff","#a8b8ff","#1e35d4",
    "#6b84ff","#3346cc","#95adff","#5570ff",
    "#c2d0ff","#4d66ff","#7a94ff","#6677ff",
]

st.set_page_config(page_title="INSAIT Pro", layout="wide", initial_sidebar_state="collapsed")

RUTA_INS_T = r"C:\Users\Hp\Desktop\Tesis\INS T"
RUTA_BD    = r"C:\Users\Hp\Desktop\Tesis\BD"
API_KEY    = "ea9b378f0cbb6fc8b27040141e054e22752373f2"

# ── PDF ───────────────────────────────────────────────────────────────────────
class ReportePDF(FPDF):
    def header(self):
        logo_path = os.path.join(RUTA_INS_T, "1.png")
        if os.path.exists(logo_path): self.image(logo_path, x=10, y=8, w=30)
        self.set_font('Arial','B',10); self.set_text_color(150,150,150)
        self.cell(0,10,f'Generado el: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}',0,1,'R')
        self.ln(10); self.set_font('Arial','B',16); self.set_text_color(35,61,255)
        self.cell(0,10,'REPORTE FINANCIERO',0,1,'C'); self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_font('Arial','I',8); self.set_text_color(128,128,128)
        self.cell(0,10,f'Página {self.page_no()}',0,0,'C')

def generar_pdf_profesional(df_filt, ratios_data, sel_bancos, sel_cuentas):
    pdf = ReportePDF(); pdf.set_auto_page_break(auto=True, margin=15); pdf.add_page()
    pdf.set_fill_color(35,61,255); pdf.set_text_color(255,255,255); pdf.set_font("Arial",'B',11)
    pdf.cell(0,10," 1. ANALISIS DE CUENTAS POR PERIODO (DATOS NOMINALES)",0,1,'L',True); pdf.ln(5)
    for banco in sel_bancos:
        df_banco = df_filt[df_filt["Banco"]==banco].sort_values(["Anho","Cuenta"])
        if df_banco.empty: continue
        pdf.set_text_color(35,61,255); pdf.set_font("Arial",'B',10)
        pdf.cell(0,8,f">> INSTITUCION: {banco}",0,1)
        pdf.set_fill_color(240,240,240); pdf.set_text_color(0,0,0); pdf.set_font("Arial",'B',9)
        pdf.cell(40,8,"Periodo",1,0,'C',True); pdf.cell(100,8,"Cuenta",1,0,'C',True)
        pdf.cell(50,8,"Valor (MM$)",1,1,'C',True); pdf.set_font("Arial",'',9)
        for _,row in df_banco.iterrows():
            pdf.cell(40,7,str(row['Anho']),1,0,'C'); pdf.cell(100,7,str(row['Cuenta']),1,0,'L')
            pdf.cell(50,7,f"{row['Valor']:,.0f}",1,1,'R')
        pdf.ln(5)
    pdf.add_page(); pdf.set_fill_color(35,61,255); pdf.set_text_color(255,255,255)
    pdf.set_font("Arial",'B',11)
    pdf.cell(0,10," 2. VISUALIZACION DE TENDENCIAS GRAFICAS",0,1,'L',True); pdf.ln(5)
    combos = [(b,ct) for b in sel_bancos for ct in sel_cuentas
              if not df_filt[(df_filt["Banco"]==b)&(df_filt["Cuenta"]==ct)].empty]
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx,(b,ct) in enumerate(combos):
            d_p = df_filt[(df_filt["Banco"]==b)&(df_filt["Cuenta"]==ct)].sort_values("Anho")
            fig_p = go.Figure()
            fig_p.add_trace(go.Scatter(x=d_p["Anho"],y=d_p["Valor"],fill='tozeroy',
                                       fillcolor='rgba(35,61,255,0.1)',
                                       line=dict(color=C["primary"],width=4),mode='lines+markers'))
            fig_p.update_layout(title=f"{b}: {ct}",template="plotly_white",width=700,height=400)
            img_p = os.path.join(tmpdir,f"c_{idx}.png"); fig_p.write_image(img_p,scale=2)
            if pdf.get_y()>200: pdf.add_page()
            pdf.image(img_p,x=20,w=170); pdf.ln(2)
    return pdf.output(dest='S').encode('latin-1')

# ── DATOS ─────────────────────────────────────────────────────────────────────
def b64(p):
    try:
        if os.path.exists(p):
            with open(p,"rb") as f: return base64.b64encode(f.read()).decode()
    except: pass
    return None

def _fetch(c, a):
    u = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/balances/{a}/12/instituciones/{c}?apikey={API_KEY}&formato=json"
    try:
        r = requests.get(u,timeout=12).json()
        return [{"Banco":c,"Anho":int(a),"Cuenta":i["DescripcionCuenta"].strip().upper(),
                 "Valor":float(i["MonedaTotal"].replace(",","."))/1e6}
                for i in r.get("CodigosBalances",[])]
    except: return []

@st.cache_data(show_spinner=False)
def cargar_bancos():
    m = {"001":"Banco de Chile","009":"Banco Internacional","012":"Banco Estado",
         "014":"Scotiabank Chile","016":"Bci","027":"Banco Do Brasil","028":"JP Morgan Chase",
         "031":"China Construction Bank","037":"Santander Chile","039":"Itaú Corpbanca",
         "040":"Banco Itaú","041":"BTG Pactual Chile","049":"Banco Security",
         "051":"Banco Falabella","053":"Banco BICE","055":"Banco Consorcio",
         "057":"Banco Ripley","067":"Banco ST"}
    rows = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futs = [ex.submit(_fetch,c,a) for c in m.keys() for a in range(2021,2026)]
        for f in as_completed(futs): rows.extend(f.result())
    df = pd.DataFrame(rows)
    if not df.empty: df["Banco"] = df["Banco"].map(m)
    return df

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "cargado" not in st.session_state:
    ph = st.empty()
    with ph.container():
        st.markdown(f'<div class="minimal-load"><div class="spinner"></div>'
                    f'<div style="font-weight:600;color:{C["primary"]};">INSAIT Pro</div></div>',
                    unsafe_allow_html=True)
    st.session_state["df_b"] = cargar_bancos()
    st.session_state["cargado"] = True
    time.sleep(1); ph.empty()

for k,v in [("all_b",False),("all_a",False),("all_c",False),("all_r",False)]:
    if k not in st.session_state: st.session_state[k] = v

df_b         = st.session_state["df_b"]
all_banks_s = sorted(df_b["Banco"].unique()) if not df_b.empty else []
BANK_COLOR  = {b: BANK_PALETTE[i % len(BANK_PALETTE)] for i,b in enumerate(all_banks_s)}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&display=swap');

/* ══════════════════════════════════════════════════════════════════
   OVERRIDE COMPLETO DE COLORES STREAMLIT/BASEWEB
   ══════════════════════════════════════════════════════════════════ */

/* 1. Variable CSS global (Streamlit la lee al inicio) */
:root {{
    --primary-color: {C["primary"]} !important;
}}

/* 2. Toggle track — todos los selectores posibles de BaseWeb */
[data-baseweb="checkbox"] [data-checked="true"],
[data-baseweb="toggle"] [data-checked="true"],
[data-testid="stToggle"] [aria-checked="true"],
[data-testid="stToggle"] input:checked + div,
[data-testid="stToggle"] > label > div:first-child[style],
[role="checkbox"][aria-checked="true"],
[role="switch"][aria-checked="true"] {{
    background-color: {C["primary"]} !important;
    border-color: {C["primary"]} !important;
}}

/* 3. TAB HIGHLIGHT — línea de color bajo el tab activo */
[data-baseweb="tab-highlight"],
div[data-baseweb="tab-highlight"],
[data-testid="stTabBar"] [data-baseweb="tab-highlight"] {{
    background-color: {C["primary"]} !important;
    background: {C["primary"]} !important;
}}
/* Tab border line */
[data-baseweb="tab-border"],
[data-testid="stTabBar"] [data-baseweb="tab-border"] {{
    background-color: transparent !important;
    background: transparent !important;
    display: none !important;
}}
/* Ocultar cualquier div de 3px o menos de alto que sea el underline */
div[data-testid="stTabBar"] > div > div[style*="height: 3px"],
div[data-testid="stTabBar"] > div > div[style*="height:3px"],
div[data-testid="stTabBar"] > div[style*="height: 3px"],
div[data-testid="stTabBar"] > div[style*="height:3px"] {{
    display: none !important;
}}

/* 4. Multiselect chips */
span[data-baseweb="tag"] {{
    background-color: {C["primary_soft"]} !important;
    border-color: {C["primary_soft"]} !important;
}}
span[data-baseweb="tag"] span {{ color: {C["primary"]} !important; }}
span[data-baseweb="tag"] svg {{ fill: {C["primary"]} !important; }}

/* 5. Dropdown */
[data-baseweb="menu"] li:hover,
[data-baseweb="menu"] [aria-selected="true"] {{
    background-color: {C["primary_soft"]} !important;
}}

/* ══════════════════════════════════════════════════════════════════
   LAYOUT Y TIPOGRAFÍA
   ══════════════════════════════════════════════════════════════════ */
html, body, .stApp {{
    background-color: {C["bg"]};
    font-family: 'DM Sans', sans-serif;
}}
label, p, div, span, .stMarkdown {{
    font-family: 'DM Sans', sans-serif !important;
}}
.main .block-container {{
    max-width: 760px !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    padding-top: 1.5rem !important;
    padding-bottom: 40px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}}

/* Logo */
.logo-container {{ display:flex; justify-content:center; padding:40px 0 28px 0; width:100%; }}
.logo-img {{ height:80px; filter:drop-shadow(0px 4px 12px rgba(35,61,255,0.10)); }}

/* ══════════════════════════════════════════════════════════════════
   BOTONES
   ══════════════════════════════════════════════════════════════════ */
.stButton > button,
.stDownloadButton > button {{
    background-color: {C["primary"]} !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 10px 20px !important;
    box-shadow: none !important;
}}
.stButton > button:hover,
.stDownloadButton > button:hover {{
    background-color: #1a2eb8 !important;
}}

/* ══════════════════════════════════════════════════════════════════
   TABS — pill compacto, sin scroll, sin línea naranja
   ══════════════════════════════════════════════════════════════════ */
div[data-testid="stTabs"] {{
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
}}

/* Contenedor de la barra */
div[data-testid="stTabBar"] {{
    background: white !important;
    border-radius: 14px !important;
    padding: 4px !important;
    box-shadow: 0 1px 12px rgba(35,61,255,0.09), 0 1px 3px rgba(0,0,0,0.04) !important;
    margin-bottom: 20px !important;
    border: none !important;
    overflow: hidden !important;
    /* Forzar que los hijos se distribuyan */
    display: grid !important;
    grid-template-columns: repeat(5, 1fr) !important;
    gap: 2px !important;
    width: 100% !important;
    box-sizing: border-box !important;
}}

/* Ocultar la línea indicadora de BaseWeb */
div[data-testid="stTabBar"] [data-baseweb="tab-highlight"],
div[data-testid="stTabBar"] [data-baseweb="tab-border"] {{
    display: none !important;
}}

/* Cada botón ocupa su celda del grid */
div[data-testid="stTabBar"] button[data-baseweb="tab"] {{
    background: transparent !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
    border-radius: 10px !important;
    padding: 9px 2px !important;
    width: 100% !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    color: {C["n400"]} !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    text-align: center !important;
    transition: all 0.15s ease !important;
    cursor: pointer !important;
}}
div[data-testid="stTabBar"] button[data-baseweb="tab"] p {{
    color: inherit !important;
    font-weight: inherit !important;
    font-size: 12.5px !important;
    margin: 0 !important;
}}
div[data-testid="stTabBar"] button[aria-selected="true"] {{
    background: {C["primary_soft"]} !important;
    color: {C["primary"]} !important;
    font-weight: 700 !important;
}}
div[data-testid="stTabBar"] button[aria-selected="true"] p {{
    color: {C["primary"]} !important;
    font-weight: 700 !important;
}}

/* Panel */
div[data-testid="stTabs"] [role="tabpanel"] {{
    padding-top: 4px !important;
    background: transparent !important;
}}

/* ══════════════════════════════════════════════════════════════════
   COMPONENTES VARIOS
   ══════════════════════════════════════════════════════════════════ */
div[data-testid="stToggle"] label span {{
    font-size: 13px !important;
    color: {C["n600"]} !important;
    font-family: 'DM Sans', sans-serif !important;
}}

/* Cards ratios */
.ratio-row {{ display:flex; gap:14px; overflow-x:auto; padding:10px 2px 28px; flex-wrap:nowrap; -webkit-overflow-scrolling:touch; }}
.ratio-card {{ min-width:210px; background:white; border-radius:14px; padding:22px 20px; border:1px solid {C["n100"]}; display:flex; flex-direction:column; gap:5px; box-shadow:0 1px 4px rgba(0,0,0,0.04); }}
.ratio-card.leader {{ border:1.5px solid {C["primary"]}; background:{C["primary_soft"]}; }}
.ratio-meta {{ font-size:10px; font-weight:600; color:{C["n600"]}; text-transform:uppercase; letter-spacing:1px; }}
.ratio-banco {{ font-size:13px; font-weight:600; color:{C["n900"]}; }}
.ratio-divider {{ height:1px; background:{C["n100"]}; margin:5px 0; }}
.ratio-num {{ font-size:30px; font-weight:700; letter-spacing:-0.8px; line-height:1.1; }}
.badge-lider {{ background:{C["primary"]}; color:white; font-size:9px; padding:2px 9px; border-radius:99px; font-weight:700; display:inline-flex; align-items:center; letter-spacing:0.5px; }}
.divider-min {{ height:1px; background:{C["n100"]}; margin:32px 0; border:none; }}
.section-label {{ font-size:13px; font-weight:500; color:{C["n600"]}; margin-bottom:4px; display:block; }}

/* ── TOOLTIP POPUP ───────────────────────────────────────────────── */
.ratio-title-row {{ display:flex; align-items:center; gap:8px; margin:8px 0 10px 0; }}
.ratio-title-text {{ font-weight:600; color:{C["n900"]}; font-size:15px; letter-spacing:-0.2px; }}
.info-popup-wrap {{ position:relative; display:inline-flex; align-items:center; }}
.info-btn {{
    display:inline-flex; align-items:center; justify-content:center;
    width:18px; height:18px; border-radius:50%;
    background:{C["n100"]}; color:{C["n600"]}; font-size:11px; font-weight:700;
    cursor:default; user-select:none; flex-shrink:0; transition:background 0.15s;
}}
.info-btn:hover {{ background:{C["primary_soft"]}; color:{C["primary"]}; }}
.info-popup {{
    display:none; position:absolute; left:26px; top:50%; transform:translateY(-50%);
    z-index:9999; background:white; border-radius:14px; padding:16px 18px; width:280px;
    box-shadow: 0 8px 32px rgba(35,61,255,0.13), 0 2px 8px rgba(0,0,0,0.07), inset 0 0 0 1px rgba(35,61,255,0.08);
    pointer-events:none;
}}
.info-popup-wrap:hover .info-popup {{ display:block; }}
.info-popup-title {{ font-size:13px; font-weight:700; color:{C["primary"]}; margin-bottom:6px; }}
.info-popup-desc {{ font-size:12px; color:{C["n600"]}; line-height:1.55; margin-bottom:10px; }}
.info-popup-example {{ background:{C["primary_soft"]}; border-radius:8px; padding:8px 10px; font-size:11px; color:{C["primary"]}; font-weight:500; line-height:1.5; }}

/* Carga */
.minimal-load {{ position:fixed; inset:0; background:white; z-index:99999; display:flex; flex-direction:column; align-items:center; justify-content:center; }}
.spinner {{ width:28px; height:28px; border:2px solid {C["n100"]}; border-top:2px solid {C["primary"]}; border-radius:50%; animation:spin 0.85s linear infinite; margin-bottom:14px; }}
@keyframes spin {{ to {{ transform:rotate(360deg); }} }}
</style>
""", unsafe_allow_html=True)

# ── LOGO ──────────────────────────────────────────────────────────────────────
logo_raw = b64(os.path.join(RUTA_INS_T,"1.png"))
if logo_raw:
    st.markdown(f'<div class="logo-container"><img src="data:image/png;base64,{logo_raw}" class="logo-img"></div>',
                unsafe_allow_html=True)

# ── TABS IN-APP ───────────────────────────────────────────────────────────────
tab_inicio, tab_banco, tab_empresa, tab_mi_empresa, tab_config = st.tabs([
    "Inicio", "Banco", "Empresa", "Mi Empresa", "Configuracion"
])

# ══════════════════════════════════════════════════════
#  INICIO
# ══════════════════════════════════════════════════════
with tab_inicio:
    st.markdown(f"""
    <div style="text-align:center;padding:48px 0 32px 0;">
        <div style="font-size:28px;font-weight:700;color:{C['n900']};letter-spacing:-0.5px;margin-bottom:10px;">
            Bienvenido a INSAIT Pro
        </div>
        <div style="font-size:15px;color:{C['n600']};max-width:420px;margin:0 auto;line-height:1.6;">
            Plataforma de análisis financiero bancario y empresarial.
            Selecciona una sección para comenzar.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  BANCO
# ══════════════════════════════════════════════════════
with tab_banco:
    b_l = sorted(df_b["Banco"].unique())

    # Bancos + toggle
    col1, col2 = st.columns([0.75, 0.25])
    with col1:
        st.markdown('<span class="section-label">Bancos</span>', unsafe_allow_html=True)
    with col2:
        tog_b = st.toggle("Todos", value=st.session_state["all_b"], key="tog_b")
    if tog_b != st.session_state["all_b"]:
        st.session_state["all_b"] = tog_b; st.rerun()

    sel_bancos = st.multiselect("Bancos", b_l,
                                default=b_l if st.session_state["all_b"] else [],
                                label_visibility="collapsed")

    # Periodos + toggle
    a_l = sorted(df_b["Anho"].unique(), reverse=True)
    col3, col4 = st.columns([0.75, 0.25])
    with col3:
        st.markdown('<span class="section-label">Periodos</span>', unsafe_allow_html=True)
    with col4:
        tog_a = st.toggle("Todos", value=st.session_state["all_a"], key="tog_a")
    if tog_a != st.session_state["all_a"]:
        st.session_state["all_a"] = tog_a; st.rerun()

    sel_años = st.multiselect("Periodos", a_l,
                              default=a_l if st.session_state["all_a"] else [],
                              label_visibility="collapsed")

    # Cuentas + toggle
    c_std = [
        "TOTAL ACTIVOS","TOTAL PASIVOS","PATRIMONIO",
        "UTILIDAD (PÉRDIDA) DEL EJERCICIO","COLOCACIONES NETAS",
        "DEPOSITOS Y OTRAS CAPTACIONES",
        "GASTOS OPERACIONALES","INGRESOS OPERACIONALES",
        "COLOCACIONES VENCIDAS","PROVISIONES",
    ]

    col5, col6 = st.columns([0.75, 0.25])
    with col5:
        st.markdown('<span class="section-label">Cuentas</span>', unsafe_allow_html=True)
    with col6:
        tog_c = st.toggle("Todos", value=st.session_state["all_c"], key="tog_c")
    if tog_c != st.session_state["all_c"]:
        st.session_state["all_c"] = tog_c; st.rerun()

    sel_cuentas = st.multiselect("Cuentas", c_std,
                                 default=c_std if st.session_state["all_c"] else [],
                                 label_visibility="collapsed")

    df_filt = df_b[
        (df_b["Banco"].isin(sel_bancos)) &
        (df_b["Cuenta"].isin(sel_cuentas)) &
        (df_b["Anho"].isin(sel_años))
    ]

    # Gráfico
    fig = go.Figure()
    if not df_filt.empty:
        # Toggle para tipo de vista
        col_v1, col_v2 = st.columns([0.75, 0.25])
        with col_v1:
            st.markdown('<span class="section-label">Visualización</span>', unsafe_allow_html=True)
        with col_v2:
            vista_lineas = st.toggle("Líneas", value=False, key="vista_toggle")
        v_t = "Líneas" if vista_lineas else "Barras"

        for b in sel_bancos:
            for cuenta in sel_cuentas:
                d = df_filt[(df_filt["Banco"]==b)&(df_filt["Cuenta"]==cuenta)].sort_values("Anho")
                if not d.empty:
                    bc = BANK_COLOR.get(b, C["primary"])
                    if v_t == "Barras":
                        fig.add_trace(go.Bar(x=d["Anho"],y=d["Valor"],name=b,
                                             marker_color=bc,marker_line_width=0))
                    else:
                        fig.add_trace(go.Scatter(x=d["Anho"],y=d["Valor"],name=b,
                                                 mode='lines+markers',
                                                 line=dict(color=bc,width=2.5),
                                                 marker=dict(color=bc,size=7)))
        tit = "Análisis de Datos"
    else:
        fig.add_trace(go.Scatter(
            x=[2021,2022,2023,2024,2025], y=[30,45,38,58,52],
            fill="tozeroy", fillcolor="rgba(35,61,255,0.07)",
            line=dict(color="rgba(35,61,255,0.22)",width=2,dash="dot"),
            mode="lines", hoverinfo="skip", showlegend=False
        ))
        fig.add_annotation(text="<b>Seleccione datos para visualizar el análisis</b>",
                           xref="paper",yref="paper",x=0.5,y=0.62,showarrow=False,
                           font=dict(size=15,color="rgba(35,61,255,0.50)",family="DM Sans"))
        fig.add_annotation(text="Elija un banco, periodo y cuenta para comenzar",
                           xref="paper",yref="paper",x=0.5,y=0.50,showarrow=False,
                           font=dict(size=12,color="rgba(75,85,99,0.45)",family="DM Sans"))
        tit = "Vista Previa"

    fig.update_layout(
        title=dict(text=tit,font=dict(size=13,color=C["n600"],family="DM Sans")),
        template="plotly_white", height=320,
        margin=dict(l=0,r=0,t=40,b=10),
        legend=dict(orientation="h",y=-0.35,font=dict(family="DM Sans",size=11)),
        barmode="group",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Indicadores
    if sel_bancos:
        st.markdown('<hr class="divider-min">', unsafe_allow_html=True)

        # ── Indicadores financieros (imagen: Financieros + Calidad Activos + Gestión Clientes)
        M_CONF = {
            # ── Financieros ──────────────────────────────────────────────
            "Liquidez Corriente": {
                "f": "ACTIVO / PASIVO",
                "n1": "TOTAL ACTIVOS", "n2": "TOTAL PASIVOS",
                "grupo": "Financieros",
                "desc": "Mide cuántos activos tiene el banco por cada peso de deuda. Valores mayores a 1 indican solidez.",
                "ejemplo": "Si el banco tiene $200 en activos y $100 en pasivos → Liquidez = 2.0 (cubre 2 veces sus deudas).",
            },
            "Solvencia": {
                "f": "PATRIMONIO / PASIVO",
                "n1": "PATRIMONIO", "n2": "TOTAL PASIVOS",
                "grupo": "Financieros",
                "desc": "Indica cuánto patrimonio propio respalda las deudas del banco. Mayor valor = más independencia financiera.",
                "ejemplo": "Patrimonio $50, Pasivos $200 → Solvencia = 0.25 (el 25% de las deudas están respaldadas con capital propio).",
            },
            "ROA": {
                "f": "UTILIDAD / ACTIVOS TOTALES",
                "n1": "UTILIDAD (PÉRDIDA) DEL EJERCICIO", "n2": "TOTAL ACTIVOS",
                "grupo": "Financieros",
                "desc": "Mide la rentabilidad del banco en relación a sus activos totales. Qué tan bien usa lo que tiene para ganar.",
                "ejemplo": "Utilidad $10, Activos $500 → ROA = 0.02 (gana 2 pesos por cada 100 en activos).",
            },
            "ROE": {
                "f": "UTILIDAD / PATRIMONIO",
                "n1": "UTILIDAD (PÉRDIDA) DEL EJERCICIO", "n2": "PATRIMONIO",
                "grupo": "Financieros",
                "desc": "Rentabilidad sobre el capital de los accionistas. Cuánto gana el banco por cada peso invertido por sus dueños.",
                "ejemplo": "Utilidad $10, Patrimonio $80 → ROE = 0.125 (12.5% de retorno para los accionistas).",
            },
            "Ratio de Eficiencia": {
                "f": "GASTOS OPER. / INGRESOS OPER.",
                "n1": "GASTOS OPERACIONALES", "n2": "INGRESOS OPERACIONALES",
                "grupo": "Financieros",
                "desc": "Cuánto gasta el banco por cada peso que ingresa. Menor ratio = banco más eficiente.",
                "ejemplo": "Gastos $60, Ingresos $100 → Eficiencia = 0.60 (gasta 60 centavos por cada peso que gana).",
            },
            # ── Calidad de Activos y Riesgos ─────────────────────────────
            "Índice de Morosidad": {
                "f": "COL. VENCIDAS / COL. TOTAL",
                "n1": "COLOCACIONES VENCIDAS", "n2": "COLOCACIONES NETAS",
                "grupo": "Calidad de Activos y Riesgos",
                "desc": "Porcentaje de créditos que no se están pagando a tiempo. Menor índice = mejor calidad crediticia.",
                "ejemplo": "Créditos vencidos $5, Total colocaciones $100 → Morosidad = 0.05 (5% de los créditos están impagos).",
            },
            "Índice de Riesgo": {
                "f": "PROVISIONES / COLOCACIONES",
                "n1": "PROVISIONES", "n2": "COLOCACIONES NETAS",
                "grupo": "Calidad de Activos y Riesgos",
                "desc": "Cuánto ha reservado el banco para cubrir posibles pérdidas de crédito. Mayor = más precavido.",
                "ejemplo": "Provisiones $8, Colocaciones $100 → Riesgo = 0.08 (reservó el 8% ante posibles impagos).",
            },
            "Ratio de Capital": {
                "f": "PASIVO / PATRIMONIO",
                "n1": "TOTAL PASIVOS", "n2": "PATRIMONIO",
                "grupo": "Calidad de Activos y Riesgos",
                "desc": "Mide el nivel de endeudamiento relativo al capital propio. Muy alto puede indicar mayor riesgo.",
                "ejemplo": "Pasivos $300, Patrimonio $100 → Ratio = 3.0 (el banco tiene 3 veces más deuda que capital propio).",
            },
            # ── Gestión Clientes ──────────────────────────────────────────
            "Participación de Mercado": {
                "f": "COL. BANCO / DEPÓSITOS",
                "n1": "COLOCACIONES NETAS", "n2": "DEPOSITOS Y OTRAS CAPTACIONES",
                "grupo": "Gestión Clientes",
                "desc": "Relación entre lo que el banco presta y lo que capta en depósitos. Indica cuánto del dinero captado se destina a créditos.",
                "ejemplo": "Colocaciones $80, Depósitos $100 → Ratio = 0.80 (presta el 80% de lo que capta en depósitos).",
            },
        }

        # Indicadores + toggle
        col7, col8 = st.columns([0.75, 0.25])
        with col7:
            st.markdown('<span class="section-label">Indicadores Financieros</span>', unsafe_allow_html=True)
        with col8:
            tog_r = st.toggle("Todos", value=st.session_state["all_r"], key="tog_r")
        if tog_r != st.session_state["all_r"]:
            st.session_state["all_r"] = tog_r; st.rerun()

        sel_ratios = st.multiselect("Indicadores Financieros:", list(M_CONF.keys()),
                                    default=list(M_CONF.keys()) if st.session_state["all_r"] else ["Liquidez Corriente"],
                                    label_visibility="collapsed")

        r_to_pdf = {}
        current_grupo = None
        for nom in sel_ratios:
            conf = M_CONF[nom]

            # Encabezado de grupo si cambia
            if conf.get("grupo") != current_grupo:
                current_grupo = conf.get("grupo")
                st.markdown(
                    f'<div style="font-size:11px;font-weight:700;color:{C["primary"]};'
                    f'text-transform:uppercase;letter-spacing:1.2px;'
                    f'margin:32px 0 6px 0;">{current_grupo}</div>',
                    unsafe_allow_html=True
                )

            desc    = conf.get("desc", "")
            ejemplo = conf.get("ejemplo", "")
            st.markdown(
                f'<div class="ratio-title-row">'
                f'<span class="ratio-title-text">{nom}</span>'
                f'<div class="info-popup-wrap"><span class="info-btn">?</span>'
                f'<div class="info-popup">'
                f'<div class="info-popup-title">{nom}</div>'
                f'<div class="info-popup-desc">{desc}</div>'
                f'<div class="info-popup-example">Ejemplo: {ejemplo}</div>'
                f'</div></div></div>',
                unsafe_allow_html=True
            )
            r_data = []
            a_ref = sel_años[0] if sel_años else 2024
            for b in sel_bancos:
                tmp    = df_b[(df_b["Banco"]==b)&(df_b["Anho"]==a_ref)]
                v1,v2  = tmp[tmp["Cuenta"]==conf["n1"]]["Valor"].sum(), tmp[tmp["Cuenta"]==conf["n2"]]["Valor"].sum()
                val    = v1/v2 if v2>0 else 0
                tmp_a  = df_b[(df_b["Banco"]==b)&(df_b["Anho"]==a_ref-1)]
                v1a,v2a= tmp_a[tmp_a["Cuenta"]==conf["n1"]]["Valor"].sum(), tmp_a[tmp_a["Cuenta"]==conf["n2"]]["Valor"].sum()
                val_ant= v1a/v2a if v2a>0 else 0
                var    = ((val-val_ant)/val_ant*100) if val_ant>0 else 0
                r_data.append({"b":b,"val":val,"var":var})

            target   = max([x["val"] for x in r_data]) if r_data else 0
            html_row = '<div class="ratio-row">'
            for res in r_data:
                is_l      = res["val"]==target and res["val"]>0
                icon      = "↑" if res["var"]>=0 else "↓"
                color_var = C["primary"] if res["var"]>=0 else "#576dff"
                bc         = BANK_COLOR.get(res["b"], C["primary"])
                html_row += (
                    f'<div class="ratio-card {"leader" if is_l else ""}">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:2px;">'
                    f'<div style="width:3px;height:34px;border-radius:2px;background:{bc};flex-shrink:0;"></div>'
                    f'<div><div class="ratio-meta">{conf["f"]}</div>'
                    f'<div style="display:flex;align-items:center;gap:5px;">'
                    f'<span class="ratio-banco">{res["b"]}</span>'
                    f'{" <span class=\'badge-lider\'>LÍDER</span>" if is_l else ""}'
                    f'</div></div></div>'
                    f'<div class="ratio-divider"></div>'
                    f'<span class="ratio-num" style="color:{bc};">{res["val"]:.3f}</span>'
                    f'<div style="font-size:12px;font-weight:600;margin-top:4px;color:{color_var};">'
                    f'{icon} {abs(res["var"]):.1f}% vs {a_ref-1}</div>'
                    f'</div>'
                )
            st.markdown(html_row+'</div>', unsafe_allow_html=True)
            r_to_pdf[nom] = r_data

        if st.button("Generar Reporte PDF", use_container_width=True):
            ov = st.empty()
            ov.markdown(f'<div class="minimal-load" style="background:rgba(255,255,255,0.88);">'
                        f'<div class="spinner"></div>'
                        f'<div style="color:{C["primary"]};font-weight:600;">Generando Reporte...</div></div>',
                        unsafe_allow_html=True)
            try:
                pdf_bytes = generar_pdf_profesional(df_filt,r_to_pdf,sel_bancos,sel_cuentas)
                time.sleep(1); ov.empty()
                st.download_button("Descargar Reporte PDF",data=pdf_bytes,
                                   file_name="Reporte_INSAIT.pdf",use_container_width=True)
            except Exception as e:
                ov.empty(); st.error(f"Error: {e}")

# ══════════════════════════════════════════════════════
#  EMPRESA
# ══════════════════════════════════════════════════════
with tab_empresa:
    st.info(f"Módulo de Empresas conectado a: {RUTA_BD}")

# ══════════════════════════════════════════════════════
#  MI EMPRESA
# ══════════════════════════════════════════════════════
with tab_mi_empresa:
    st.markdown(f'<span style="font-size:15px;color:{C["n600"]};">Módulo Mi Empresa — próximamente.</span>',
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  CONFIGURACION
# ══════════════════════════════════════════════════════
with tab_config:
    st.markdown(f'<span style="font-size:15px;color:{C["n600"]};">Configuracion — próximamente.</span>',
                unsafe_allow_html=True)