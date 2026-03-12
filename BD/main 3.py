import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import os, base64, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fpdf import FPDF

# ── 1. CONFIGURACIÓN Y PALETA (ESTRICTO AZUL) ──────────────────────────────
C = {
    "primary":      "#233dff", 
    "primary_soft": "#f0f3ff", 
    "n900":         "#111827", 
    "n600":         "#4b5563", 
    "n100":         "#f3f4f6", 
    "bg":           "#f9fafb",
    "chart":        ["#233dff", "#4d61ff", "#7a8aff", "#a7b3ff", "#d3dbff"]
}

st.set_page_config(page_title="INSAIT Pro", layout="centered", initial_sidebar_state="collapsed")

# ── 2. RUTAS ────────────────────────────────────────────────────────────────
RUTA_INS_T = r"C:\Users\Hp\Desktop\Tesis\INS T"
RUTA_BD    = r"C:\Users\Hp\Desktop\Tesis\BD"
API_KEY    = "ea9b378f0cbb6fc8b27040141e054e22752373f2"

# ── 3. LÓGICA DE PDF (GRÁFICO VERTICAL Y DISEÑO LIMPIO) ─────────────────────
class ReportePDF(FPDF):
    def header(self):
        logo_path = os.path.join(RUTA_INS_T, "1.png")
        if os.path.exists(logo_path):
            self.image(logo_path, x=85, y=10, w=40)
            self.ln(25)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(35, 61, 255)
        self.cell(0, 10, 'REPORTE FINANCIERO', 0, 1, 'C') # Sin palabra "Profesional"
        self.ln(5)

def generar_pdf(df_filt, ratios_data):
    pdf = ReportePDF()
    pdf.add_page()
    
    # Análisis Visual - Gráfico de Barras Verticales
    pdf.set_fill_color(35, 61, 255); pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, " ANALISIS DE CUENTAS (GRAFICO DE BARRAS)", 0, 1, 'L', True)
    pdf.ln(10)
    
    max_val = df_filt["Valor"].max() if not df_filt.empty else 1
    base_y = pdf.get_y() + 50
    x_offset = 20
    
    # Dibujar barras verticales por registro
    for i, row in df_filt.iterrows():
        h_bar = (row['Valor'] / max_val) * 40
        # Color dinámico de la paleta
        pdf.set_fill_color(35, 61, 255) if i % 2 == 0 else pdf.set_fill_color(77, 97, 255)
        pdf.rect(x_offset, base_y - h_bar, 12, h_bar, 'F')
        
        pdf.set_font("Arial", '', 6); pdf.set_text_color(100, 100, 100)
        pdf.set_xy(x_offset - 2, base_y + 2)
        pdf.cell(15, 5, f"{row['Anho']}", 0, 0, 'C')
        
        x_offset += 18
        if x_offset > 180: break # Evitar desborde
    
    pdf.set_xy(10, base_y + 15)
    pdf.set_font("Arial", 'B', 9); pdf.set_text_color(35, 61, 255)
    pdf.cell(0, 10, "DETALLE DE INDICADORES", 0, 1)
    
    pdf.set_text_color(50, 50, 50)
    for nom, data in ratios_data.items():
        pdf.set_font("Arial", 'B', 9); pdf.cell(0, 7, f"> {nom}", 0, 1)
        pdf.set_font("Arial", '', 8)
        for i in data:
            pdf.cell(0, 5, f" - {i['b']}: {i['val']:.3f} (Variacion: {i['var']:.1f}%)", 0, 1)
        pdf.ln(2)
    
    return pdf.output(dest='S').encode('latin-1')

# ── 4. CSS (RESTAURACIÓN IDÉNTICA A LA APP) ────────────────────────────────
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    :root {{ --primary-color: {C["primary"]} !important; }}
    html, body, .stApp {{ background-color: {C["bg"]}; font-family: 'Inter', sans-serif; }}
    
    .logo-container {{ display: flex; justify-content: center; padding: 45px 0 25px 0; width: 100%; }}
    .logo-img {{ height: 100px; filter: drop-shadow(0px 4px 10px rgba(35, 61, 255, 0.12)); }}

    /* INTERFAZ ESTRICTAMENTE AZUL */
    div[data-baseweb="checkbox"] div {{ background-color: {C["primary"]} !important; }}
    div[data-testid="stRadio"] label[data-baseweb="radio"] div[data-checked="true"] > div {{ background-color: {C["primary"]} !important; border-color: {C["primary"]} !important; }}
    .stTabs [data-baseweb="tab-highlight"] {{ background-color: {C["primary"]} !important; }}
    .stTabs [aria-selected="true"] {{ color: {C["primary"]} !important; }}

    /* TARJETAS DE RATIOS (CLON APP) */
    .ratio-row {{ display: flex; gap: 16px; overflow-x: auto; padding: 10px 5px 25px 5px; flex-wrap: nowrap; -webkit-overflow-scrolling: touch; }}
    .ratio-row::-webkit-scrollbar {{ display: none; }}
    
    .ratio-card {{ 
        min-width: 230px; background: white; border-radius: 12px; padding: 22px; 
        border: 1px solid {C["n100"]}; display: flex; flex-direction: column;
        transition: all 0.2s ease;
    }}
    .ratio-card.leader {{ border: 2.5px solid {C["primary"]}; background: {C["primary_soft"]}; }}
    
    /* Tipografía corregida Activo / Pasivo */
    .ratio-meta {{ 
        font-family: 'Inter', sans-serif; font-size: 11px; font-weight: 600; 
        color: {C["n600"]}; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; 
    }}
    
    .banco-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; width: 100%; }}
    .ratio-banco {{ font-family: 'Inter', sans-serif; font-size: 14px; font-weight: 700; color: {C["n900"]}; }}
    
    .ratio-num {{ font-size: 38px; font-weight: 700; color: {C["primary"]}; letter-spacing: -1.5px; line-height: 1; }}
    .badge-lider {{ 
        background: {C["primary"]}; color: white; font-size: 9px; padding: 2px 7px; 
        border-radius: 4px; font-weight: 800; text-transform: uppercase;
    }}

    .example-box {{ background: {C["primary_soft"]}; border-left: 4px solid {C["primary"]}; padding: 15px; border-radius: 8px; margin: 10px 0; }}

    /* PANTALLA CARGA MINIMALISTA */
    .minimal-load {{ position: fixed; inset: 0; background: white; z-index: 99999; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
    .spinner {{ width: 35px; height: 35px; border: 3px solid {C["n100"]}; border-top: 3px solid {C["primary"]}; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 20px; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
""", unsafe_allow_html=True)

# ── 5. LÓGICA DE DATOS ──
def b64(p):
    try:
        if os.path.exists(p):
            with open(p, "rb") as f: return base64.b64encode(f.read()).decode()
    except: pass
    return None

def _fetch(c, a):
    u = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/balances/{a}/12/instituciones/{c}?apikey={API_KEY}&formato=json"
    try:
        r = requests.get(u, timeout=12).json()
        return [{"Banco": c, "Anho": int(a), "Cuenta": i["DescripcionCuenta"].strip().upper(), "Valor": float(i["MonedaTotal"].replace(",","."))/1e6} for i in r.get("CodigosBalances", [])]
    except: return []

@st.cache_data(show_spinner=False)
def cargar_bancos():
    m = {"001":"Banco de Chile", "012":"Banco Estado", "037":"Santander", "051":"Falabella"}
    rows = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(_fetch, c, a) for c in m.keys() for a in range(2021, 2026)]
        for f in as_completed(futs): rows.extend(f.result())
    df = pd.DataFrame(rows)
    if not df.empty: df["Banco"] = df["Banco"].map(m)
    return df

# ── 6. PANTALLA DE CARGA ──
if "cargado" not in st.session_state:
    ph = st.empty()
    with ph.container():
        st.markdown(f'<div class="minimal-load"><div class="spinner"></div><div style="font-weight:600; font-family:Inter; color:{C["n900"]};">INSAIT Pro</div></div>', unsafe_allow_html=True)
    st.session_state["df_b"] = cargar_bancos()
    st.session_state["cargado"] = True
    time.sleep(1); ph.empty()

df_b = st.session_state["df_b"]
logo_raw = b64(os.path.join(RUTA_INS_T, "1.png"))
if logo_raw: st.markdown(f'<div class="logo-container"><img src="data:image/png;base64,{logo_raw}" class="logo-img"></div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["BANCOS", "EMPRESAS"])

with tab1:
    # FILTROS
    b_l = sorted(df_b["Banco"].unique())
    c1, c2 = st.columns([0.75, 0.25])
    with c2: s_b = st.checkbox("Todos", key="all_b")
    sel_bancos = st.multiselect("Bancos", b_l, default=b_l if s_b else [])

    a_l = sorted(df_b["Anho"].unique(), reverse=True)
    c3, c4 = st.columns([0.75, 0.25])
    with c4: s_a = st.checkbox("Todos", key="all_a")
    sel_años = st.multiselect("Periodos", a_l, default=a_l if s_a else [2024])

    if sel_bancos:
        c_std = ["TOTAL ACTIVOS", "TOTAL PASIVOS", "PATRIMONIO", "UTILIDAD (PÉRDIDA) DEL EJERCICIO"]
        sel_cuentas = st.multiselect("Cuentas", c_std, default=["TOTAL ACTIVOS"])
        df_filt = df_b[(df_b["Banco"].isin(sel_bancos)) & (df_b["Cuenta"].isin(sel_cuentas)) & (df_b["Anho"].isin(sel_años))]
        
        if not df_filt.empty:
            st.markdown(f'<div style="background:white; border-radius:16px; padding:20px; border:1px solid {C["n100"]}; border-top:4px solid {C["primary"]}; box-shadow:0 1px 3px rgba(0,0,0,0.05); margin-bottom:20px;"><div style="font-size:10px; font-weight:700; color:{C["n600"]}; text-transform:uppercase;">Cuentas Seleccionadas</div><div style="font-size:26px; font-weight:700; color:{C["n900"]};">${df_filt["Valor"].sum():,.0f} MM</div></div>', unsafe_allow_html=True)
            v_t = st.radio("Vista", ["Barras", "Líneas"], horizontal=True, label_visibility="collapsed")
            fig = go.Figure()
            for i, b in enumerate(sel_bancos):
                for j, cuenta in enumerate(sel_cuentas):
                    d = df_filt[(df_filt["Banco"] == b) & (df_filt["Cuenta"] == cuenta)].sort_values("Anho")
                    if not d.empty:
                        col = C["chart"][(i+j) % 5]
                        if v_t == "Barras": fig.add_trace(go.Bar(x=d["Anho"], y=d["Valor"], name=f"{b}", marker_color=col))
                        else: fig.add_trace(go.Scatter(x=d["Anho"], y=d["Valor"], name=f"{b}", mode='lines+markers', line=dict(color=col, width=3)))
            fig.update_layout(template="plotly_white", height=320, margin=dict(l=0,r=0,t=10,b=10), legend=dict(orientation="h", y=-0.35))
            st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        r_list = ["Liquidez Corriente", "Solvencia", "ROE", "NIM", "Eficiencia", "Riesgo", "Capital"]
        c5, c6 = st.columns([0.75, 0.25])
        with c6: s_r = st.checkbox("Todos", key="all_r")
        sel_ratios = st.multiselect("Indicadores:", r_list, default=r_list if s_r else ["Liquidez Corriente"])

        M_CONF = {
            "Liquidez Corriente": {"f": "ACTIVO / PASIVO", "n1": "TOTAL ACTIVOS", "n2": "TOTAL PASIVOS", "t": "max", "d": "Capacidad de cubrir deudas.", "ex": "1.121 (Chile) = 1.121 por cada 1 de deuda."},
            "Solvencia": {"f": "PATRIMONIO / PASIVO", "n1": "PATRIMONIO", "n2": "TOTAL PASIVOS", "t": "max", "d": "Respaldo patrimonial.", "ex": "12.1% de deuda cubierta por capital."},
            "ROE": {"f": "UTILIDAD / PATRIMONIO", "n1": "UTILIDAD (PÉRDIDA) DEL EJERCICIO", "n2": "PATRIMONIO", "t": "max", "d": "Rentabilidad accionaria.", "ex": "Gana $15 por cada $100 invertidos."},
            "NIM": {"f": "MARGEN / ACTIVOS", "n1": "INGRESOS POR INTERESES", "n2": "TOTAL ACTIVOS", "t": "max", "d": "Margen intereses.", "ex": "Rentabilidad de préstamos."},
            "Eficiencia": {"f": "GASTOS / INGRESOS", "n1": "GASTOS DE OPERACIÓN", "n2": "INGRESOS DE OPERACIÓN", "t": "min", "d": "Costo operativo.", "ex": "$0.45 de gasto por cada $1 ganado."},
            "Riesgo": {"f": "PROV / ACTIVOS", "n1": "PROVISIONES", "n2": "TOTAL ACTIVOS", "t": "min", "d": "Cobertura impagos.", "ex": "Resguardo ante préstamos incobrables."},
            "Capital": {"f": "PATRIMONIO / ACTIVOS", "n1": "PATRIMONIO", "n2": "TOTAL ACTIVOS", "t": "max", "d": "Solidez capital.", "ex": "Colchón de seguridad bancario."}
        }

        r_to_pdf = {}
        for nom in sel_ratios:
            conf = M_CONF[nom]; st.markdown(f'<span style="font-weight:700; color:{C["n900"]}; font-size:16px; margin:25px 0 10px 0; display:block;">{nom}</span>', unsafe_allow_html=True)
            r_data = []
            a_ref = sel_años[0] if sel_años else 2024
            for b in sel_bancos:
                def get_v(y):
                    tmp = df_b[(df_b["Banco"] == b) & (df_b["Anho"] == y)]
                    v1, v2 = tmp[tmp["Cuenta"] == conf["n1"]]["Valor"].sum(), tmp[tmp["Cuenta"] == conf["n2"]]["Valor"].sum()
                    return (v1 / v2 if v2 > 0 else 0), v1, v2
                val, v1, v2 = get_v(a_ref); val_ant, _, _ = get_v(a_ref - 1)
                var = ((val - val_ant) / val_ant * 100) if val_ant > 0 else 0
                r_data.append({"b": b, "val": val, "var": var, "v_ant": val_ant})
            
            r_to_pdf[nom] = r_data; target = (max([x["val"] for x in r_data]) if conf["t"] == "max" else min([x["val"] for x in r_data])) if r_data else 0
            html_row = '<div class="ratio-row">'
            for res in r_data:
                is_l = res["val"] == target and res["val"] > 0; icon = "↑" if res["var"] >= 0 else "↓"
                html_row += f'<div class="ratio-card {"leader" if is_l else ""}"><span class="ratio-meta">{conf["f"]}</span><div class="banco-header"><span class="ratio-banco">{res["b"]}</span>'
                if is_l: html_row += '<span class="badge-lider">LÍDER</span>'
                html_row += f'</div><span class="ratio-num">{res["val"]:.3f}</span><div style="font-size:14px; font-weight:700; margin-top:8px; color:{C["primary"]}">{icon} {abs(res["var"]):.1f}% vs {a_ref-1}</div></div>'
            st.markdown(html_row + '</div>', unsafe_allow_html=True)
            with st.expander(f"Info técnica y ejemplo de {nom}"):
                st.markdown(f"**Concepto:** {conf['d']}")
                st.markdown(f'<div class="example-box"><strong>Ejemplo:</strong> {conf["ex"]}</div>', unsafe_allow_html=True)
                for res in r_data: st.write(f"○ **{res['b']}**: {res['val']:.3f} ({a_ref}) vs {res['v_ant']:.3f} ({a_ref-1})")

        st.write("---")
        if st.button("📄 Generar Reporte PDF", use_container_width=True):
            ov = st.empty()
            with ov.container():
                st.markdown('<div class="minimal-load" style="background:rgba(255,255,255,0.8); backdrop-filter:blur(2px);"><div class="spinner"></div><div style="font-weight:600; font-family:Inter; color:#111827;">Generando Reporte...</div></div>', unsafe_allow_html=True)
                pdf_b = generar_pdf(df_filt, r_to_pdf); time.sleep(1.5)
            ov.empty()
            st.download_button("📥 Descargar Reporte PDF Ahora", data=pdf_b, file_name="Reporte_INSAIT.pdf", use_container_width=True)

with tab2:
    st.info(f"Módulo de Empresas conectado a: {RUTA_BD}")