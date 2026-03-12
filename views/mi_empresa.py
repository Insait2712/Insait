"""
views/mi_empresa.py
Sub-tabs: Dashboard · Ventas · Proyectos · Indicadores
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date
import io


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _section_label(texto, C):
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:{C["primary"]};'
        f'text-transform:uppercase;letter-spacing:1.2px;margin:20px 0 10px 0;">'
        f'{texto}</div>',
        unsafe_allow_html=True,
    )

def _divider():
    st.markdown(
        "<hr style='border:none;border-top:1.5px solid rgba(77,107,255,0.08);margin:4px 0 16px 0;'>",
        unsafe_allow_html=True,
    )

def _fmt_clp(n):
    return f"${n:,.0f}".replace(",", ".")

def _fmt_pct(n):
    return f"{n:+.1f}%"

def _kpi(col, label, valor, sub, color):
    """Render a single KPI card — same pattern used in Indicadores."""
    col.markdown(
        '<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);'
        'border-radius:18px;padding:16px;margin-bottom:10px;'
        'box-shadow:0 2px 8px rgba(77,107,255,0.05);">'
        f'<div style="font-size:9px;font-weight:700;color:#94a3b8;'
        f'text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">{label}</div>'
        f'<div style="font-size:20px;font-weight:800;color:{color};'
        f'letter-spacing:-0.5px;line-height:1;">{valor}</div>'
        f'<div style="font-size:10px;color:#94a3b8;margin-top:3px;">{sub}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ── DICCIONARIO DE INDICADORES ────────────────────────────────────────────────

INFO_INDICADORES = {
    "VAN": {
        "titulo": "Valor Actual Neto (VAN)",
        "formula": "VAN = Σ [ Fₜ / (1 + r)ᵗ ]   para t = 0, 1, ..., n",
        "descripcion": (
            "El <b>VAN</b> mide el valor presente de todos los flujos de caja futuros de un "
            "proyecto, descontados a la tasa de oportunidad del inversionista, "
            "menos la inversión inicial."
        ),
        "interpretacion": (
            "• <b>VAN &gt; 0</b>: El proyecto genera más valor del que cuesta → VIABLE.<br>"
            "• <b>VAN = 0</b>: Apenas cubre el costo de capital → INDIFERENTE.<br>"
            "• <b>VAN &lt; 0</b>: El proyecto destruye valor → NO VIABLE."
        ),
    },
    "TIR": {
        "titulo": "Tasa Interna de Retorno (TIR)",
        "formula": "0 = Σ [ Fₜ / (1 + TIR)ᵗ ]   →  despejar TIR",
        "descripcion": (
            "La <b>TIR</b> es la tasa de descuento que hace que el VAN sea exactamente cero. "
            "Es la rentabilidad intrínseca del proyecto."
        ),
        "interpretacion": (
            "• <b>TIR &gt; Tasa de descuento</b>: Rinde más que el costo de capital → VIABLE.<br>"
            "• <b>TIR &lt; Tasa de descuento</b>: No compensa el riesgo → NO VIABLE."
        ),
    },
    "Payback": {
        "titulo": "Período de Recuperación (Payback)",
        "formula": "PB = t*  tal que  Σ Fₜ ≥ |F₀|",
        "descripcion": "El <b>Payback</b> es el número de períodos para recuperar la inversión inicial.",
        "interpretacion": (
            "• Más corto = menor riesgo y mayor liquidez.<br>"
            "• Úsalo como complemento del VAN y la TIR."
        ),
    },
    "PE": {
        "titulo": "Punto de Equilibrio (Break-Even)",
        "formula": "PE = Costos Fijos / (Precio unitario − Costo variable unitario)",
        "descripcion": "Volumen mínimo de unidades para que ingresos igualen costos.",
        "interpretacion": (
            "• Menor PE = más fácil ser rentable.<br>"
            "• PE cercano a capacidad máxima = alto riesgo operativo."
        ),
    },
    "Liquidez": {
        "titulo": "Índice de Liquidez",
        "formula": "Liquidez = Activos Totales / Pasivos Totales",
        "descripcion": "Capacidad de cubrir obligaciones con activos disponibles.",
        "interpretacion": "• &gt;1.5: Buena. • 1.0–1.5: Ajustada. • &lt;1.0: Riesgo.",
    },
    "Endeudamiento": {
        "titulo": "Razón de Endeudamiento",
        "formula": "Endeudamiento = Pasivos Totales / Patrimonio",
        "descripcion": "Proporción del financiamiento que proviene de deuda.",
        "interpretacion": "• &lt;1.0: Financiado con recursos propios. • &gt;2.0: Apalancamiento elevado.",
    },
    "ROE": {
        "titulo": "Rentabilidad sobre Patrimonio (ROE)",
        "formula": "ROE = Utilidad Neta / Patrimonio × 100",
        "descripcion": "Pesos de utilidad por cada peso de capital de accionistas.",
        "interpretacion": "• &gt;15%: Alta. • 8–15%: Aceptable. • &lt;8%: Bajo costo de oportunidad.",
    },
    "ROA": {
        "titulo": "Rentabilidad sobre Activos (ROA)",
        "formula": "ROA = Utilidad Neta / Activos Totales × 100",
        "descripcion": "Eficiencia convirtiendo activos en utilidad.",
        "interpretacion": "• &gt;8%: Muy eficiente. • 4–8%: Razonable. • &lt;4%: Revisar costos.",
    },
    "Margen neto": {
        "titulo": "Margen Neto",
        "formula": "Margen neto = Utilidad Neta / Ventas × 100",
        "descripcion": "Porcentaje de cada peso vendido que se convierte en utilidad neta.",
        "interpretacion": "• Varía por sector. Compara contra promedio de tu industria.",
    },
    "Margen operac.": {
        "titulo": "Margen Operacional",
        "formula": "Margen op. = (Ventas − Costos Operacionales) / Ventas × 100",
        "descripcion": "Rentabilidad de la operación antes de intereses e impuestos.",
        "interpretacion": "• &gt;20%: Muy eficiente. • 10–20%: Sólido. • &lt;10%: Presión de costos.",
    },
    "Rot. de activos": {
        "titulo": "Rotación de Activos",
        "formula": "Rotación = Ventas / Activos Totales",
        "descripcion": "Pesos de ventas por cada peso invertido en activos.",
        "interpretacion": "• Alta rotación = uso eficiente. Tendencia creciente es positiva.",
    },
    "Apalancamiento": {
        "titulo": "Multiplicador de Capital",
        "formula": "Apalancamiento = Activos Totales / Patrimonio",
        "descripcion": "Activos por peso de patrimonio. Componente DuPont.",
        "interpretacion": "• 2–3: Normal. • &gt;4: Alto riesgo ante caídas de ingresos.",
    },
    "Cobertura deuda": {
        "titulo": "Cobertura de Intereses (estimada)",
        "formula": "Cobertura = (Utilidad + Intereses est.) / Intereses est.",
        "descripcion": "Veces que la utilidad cubre el pago de intereses.",
        "interpretacion": "• &gt;3: Holgura. • 1.5–3: Alerta. • &lt;1.5: Riesgo de incumplimiento.",
    },
}


# ── CÁLCULOS ──────────────────────────────────────────────────────────────────

def calcular_van(flujos, tasa):
    return sum(f / (1 + tasa) ** i for i, f in enumerate(flujos))

def calcular_tir(flujos, precision=1e-6):
    if flujos[0] >= 0:
        return None
    lo, hi = -0.9999, 10.0
    for _ in range(1000):
        mid = (lo + hi) / 2
        van = sum(flujos[i] / (1 + mid) ** i for i in range(len(flujos)))
        if abs(van) < precision:
            return mid
        if van > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < precision:
            return mid
    return None

def calcular_payback(flujos):
    acum = 0
    for i, f in enumerate(flujos):
        if i == 0:
            continue
        acum += f
        if acum >= abs(flujos[0]):
            return i
    return None

def proyeccion_lineal(valores, periodos):
    n = len(valores)
    if n < 2:
        return [valores[-1]] * periodos
    x = np.arange(n)
    y = np.array(valores, dtype=float)
    m, b = np.polyfit(x, y, 1)
    return [m * (n + i) + b for i in range(periodos)]

def proyeccion_promedio_movil(valores, ventana, periodos):
    if len(valores) < ventana:
        ventana = len(valores)
    base = sum(valores[-ventana:]) / ventana
    crecimiento = 0
    if len(valores) >= 2:
        crec_list = [(valores[i] - valores[i-1]) / abs(valores[i-1])
                     for i in range(1, len(valores)) if valores[i-1] != 0]
        crecimiento = sum(crec_list) / len(crec_list) if crec_list else 0
    return [base * (1 + crecimiento) ** (i + 1) for i in range(periodos)]


# ── ESTADO ────────────────────────────────────────────────────────────────────

def _init_state():
    defaults = {"me_ventas": [], "me_flujos": [], "me_balance": {}, "me_nombre": "Mi Empresa"}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
#  RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_mi_empresa(C, BANK_COLOR):
    _init_state()
    sub_tab = st.radio(
        "", ["📊 Dashboard", "📈 Ventas", "⚖️ Indicadores", "🏗️ Proyectos"],
        horizontal=True, label_visibility="collapsed", key="me_subtab",
    )
    _divider()
    if sub_tab == "📊 Dashboard":
        _render_dashboard(C)
    elif sub_tab == "📈 Ventas":
        _render_ventas(C)
    elif sub_tab == "🏗️ Proyectos":
        _render_proyectos(C)
    elif sub_tab == "⚖️ Indicadores":
        _render_indicadores(C)


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def _render_dashboard(C):
    ventas  = st.session_state["me_ventas"]
    balance = st.session_state["me_balance"]

    nombre = st.text_input(
        "Nombre", value=st.session_state["me_nombre"],
        key="me_nombre_input", label_visibility="collapsed", placeholder="Nombre de tu empresa",
    )
    st.session_state["me_nombre"] = nombre

    st.markdown(
        '<div style="padding:18px 20px;background:white;border-radius:20px;'
        'border:1.5px solid rgba(77,107,255,0.08);'
        'box-shadow:0 2px 10px rgba(77,107,255,0.05);margin-bottom:20px;">'
        f'<div style="font-size:10px;font-weight:700;color:{C["n400"]};'
        f'text-transform:uppercase;letter-spacing:1.4px;margin-bottom:4px;">RESUMEN EJECUTIVO</div>'
        f'<div style="font-size:19px;font-weight:800;color:{C["n900"]};letter-spacing:-0.4px;">'
        f'{nombre} 📋</div>'
        f'<div style="font-size:11px;color:{C["n400"]};margin-top:3px;">'
        f'{date.today().strftime("%d de %B, %Y")}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    _section_label("KPIs principales", C)

    if len(ventas) >= 1:
        ultimo   = ventas[-1]
        v_actual = ultimo.get("ventas", 0)
        c_actual = ultimo.get("costos", 0)
        margen   = ((v_actual - c_actual) / v_actual * 100) if v_actual > 0 else 0
        resultado = v_actual - c_actual

        col1, col2 = st.columns(2)
        _kpi(col1, "VENTAS",       _fmt_clp(v_actual),    ultimo.get("periodo", "—"), C["primary"])
        _kpi(col1, "MARGEN BRUTO", f"{margen:.1f}%",       "Ventas − Costos",          "#06b6a0")
        _kpi(col2, "COSTOS",       _fmt_clp(c_actual),    ultimo.get("periodo", "—"), "#e63946")
        _kpi(col2, "RESULTADO",    _fmt_clp(resultado),   "Ventas − Costos",
             C["primary"] if resultado >= 0 else "#e63946")
    else:
        st.markdown(
            f'<div style="background:#f8faff;border:1.5px solid rgba(77,107,255,0.10);'
            f'border-radius:16px;padding:20px;text-align:center;color:{C["n400"]};'
            f'font-size:12px;margin-bottom:16px;">'
            f'Ingresa datos en la pestaña <b>📈 Ventas</b> para ver tus KPIs aquí.</div>',
            unsafe_allow_html=True,
        )

    if balance:
        _section_label("Indicadores de balance", C)
        a  = balance.get("activos", 0)
        p  = balance.get("pasivos", 0)
        pt = balance.get("patrimonio", 0)
        u  = balance.get("utilidad", 0)
        liq = a / p if p > 0 else 0
        roe = (u / pt * 100) if pt > 0 else 0
        end = p / pt if pt > 0 else 0
        roa = (u / a * 100) if a > 0 else 0

        col3, col4 = st.columns(2)
        _kpi(col3, "LIQUIDEZ",      f"{liq:.2f}x", "Activos / Pasivos",    "#06b6a0" if liq >= 1 else "#e63946")
        _kpi(col3, "ROE",           f"{roe:.1f}%", "Utilidad / Patrimonio", C["primary"])
        _kpi(col4, "ENDEUDAMIENTO", f"{end:.2f}x", "Pasivos / Patrimonio",  "#F5A800" if end <= 2 else "#e63946")
        _kpi(col4, "ROA",           f"{roa:.1f}%", "Utilidad / Activos",   C["primary"])

    if len(ventas) >= 2:
        _section_label("Tendencia de ventas", C)
        df_v = pd.DataFrame(ventas)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_v["periodo"], y=df_v["ventas"],
            fill="tozeroy", fillcolor="rgba(77,107,255,0.07)",
            line=dict(color=C["primary"], width=2.5),
            mode="lines+markers", marker=dict(color=C["primary"], size=6), name="Ventas",
        ))
        if "costos" in df_v.columns:
            fig.add_trace(go.Scatter(
                x=df_v["periodo"], y=df_v["costos"],
                line=dict(color="#e63946", width=2, dash="dot"), mode="lines", name="Costos",
            ))
        fig.update_layout(template="plotly_white", height=220,
                          margin=dict(l=0, r=0, t=10, b=10),
                          legend=dict(orientation="h", y=-0.4,
                                      font=dict(family="Plus Jakarta Sans", size=11)))
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  VENTAS
# ══════════════════════════════════════════════════════════════════════════════

def _render_ventas(C):
    _section_label("Ingresar datos", C)
    metodo = st.radio("", ["Manual", "Subir Excel/CSV"],
                      horizontal=True, label_visibility="collapsed", key="me_ventas_metodo")
    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

    if metodo == "Subir Excel/CSV":
        uploaded = st.file_uploader(
            "Sube tu archivo (columnas: periodo, ventas, costos)",
            type=["xlsx", "csv"], key="me_ventas_upload", label_visibility="collapsed",
        )
        if uploaded:
            try:
                df_up = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
                df_up.columns = [c.lower().strip() for c in df_up.columns]
                if {"periodo", "ventas", "costos"}.issubset(set(df_up.columns)):
                    st.session_state["me_ventas"] = df_up[["periodo","ventas","costos"]].to_dict("records")
                    st.success(f"✓ {len(df_up)} períodos cargados.")
                else:
                    st.error("El archivo debe tener columnas: periodo, ventas, costos.")
            except Exception as e:
                st.error(f"Error: {e}")
        df_template = pd.DataFrame({
            "periodo": ["Ene-2024","Feb-2024","Mar-2024"],
            "ventas":  [10000000, 12000000, 11500000],
            "costos":  [7000000,  8400000,  8050000],
        })
        buf = io.BytesIO()
        df_template.to_excel(buf, index=False); buf.seek(0)
        st.download_button("⬇ Descargar plantilla Excel", data=buf,
                           file_name="plantilla_ventas.xlsx", use_container_width=True)
    else:
        col_p, col_v, col_c = st.columns(3)
        with col_p:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Período</span>', unsafe_allow_html=True)
            periodo = st.text_input("Período", placeholder="Ene-2024", key="me_inp_periodo", label_visibility="collapsed")
        with col_v:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Ventas ($)</span>', unsafe_allow_html=True)
            ventas_inp = st.number_input("Ventas", min_value=0, value=0, step=100000, key="me_inp_ventas", label_visibility="collapsed")
        with col_c:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Costos ($)</span>', unsafe_allow_html=True)
            costos_inp = st.number_input("Costos", min_value=0, value=0, step=100000, key="me_inp_costos", label_visibility="collapsed")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("＋ Agregar período", use_container_width=True, key="me_btn_add"):
                if periodo:
                    st.session_state["me_ventas"].append({"periodo": periodo, "ventas": ventas_inp, "costos": costos_inp})
                    st.rerun()
        with col_b2:
            if st.button("🗑 Limpiar todo", use_container_width=True, key="me_btn_clear"):
                st.session_state["me_ventas"] = []
                st.rerun()

    ventas = st.session_state["me_ventas"]
    if not ventas:
        st.markdown(f'<div style="font-size:12px;color:{C["n400"]};text-align:center;padding:24px;">Aún no hay datos.</div>', unsafe_allow_html=True)
        return

    df_v = pd.DataFrame(ventas)
    _section_label("Historial", C)
    df_v["Margen"] = ((df_v["ventas"] - df_v["costos"]) / df_v["ventas"] * 100).round(1).astype(str) + "%"
    df_v["Variación"] = "—"
    for i in range(1, len(df_v)):
        v_ant = df_v.iloc[i-1]["ventas"]
        if v_ant > 0:
            var = (df_v.iloc[i]["ventas"] - v_ant) / v_ant * 100
            df_v.at[i, "Variación"] = f"{var:+.1f}%"

    html_tabla = '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:12px;">'
    html_tabla += f'<tr style="border-bottom:1.5px solid rgba(77,107,255,0.10);">'
    for col in ["Período","Ventas","Costos","Margen","Variación"]:
        html_tabla += f'<th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};text-transform:uppercase;">{col}</th>'
    html_tabla += '</tr>'
    for _, row in df_v.iterrows():
        var_color = C["primary"]
        if row["Variación"] != "—":
            try:
                var_color = "#06d6a0" if float(row["Variación"].replace("%","").replace("+","")) >= 0 else "#e63946"
            except:
                pass
        html_tabla += (
            f'<tr style="border-bottom:1px solid rgba(77,107,255,0.06);">'
            f'<td style="padding:7px 8px;font-weight:600;color:{C["n900"]};">{row["periodo"]}</td>'
            f'<td style="padding:7px 8px;color:{C["n900"]};">{_fmt_clp(row["ventas"])}</td>'
            f'<td style="padding:7px 8px;color:{C["n600"]};">{_fmt_clp(row["costos"])}</td>'
            f'<td style="padding:7px 8px;font-weight:600;color:#06b6a0;">{row["Margen"]}</td>'
            f'<td style="padding:7px 8px;font-weight:700;color:{var_color};">{row["Variación"]}</td>'
            f'</tr>'
        )
    html_tabla += '</table></div>'
    st.markdown(html_tabla, unsafe_allow_html=True)

    _section_label("Evolución ventas vs costos", C)
    fig_vc = go.Figure()
    fig_vc.add_trace(go.Bar(x=df_v["periodo"], y=df_v["ventas"], name="Ventas",
                            marker_color=C["primary"], marker_line_width=0))
    fig_vc.add_trace(go.Bar(x=df_v["periodo"], y=df_v["costos"], name="Costos",
                            marker_color="#e63946", marker_line_width=0))
    fig_vc.update_layout(template="plotly_white", height=260, barmode="group",
                         margin=dict(l=0, r=0, t=10, b=10),
                         legend=dict(orientation="h", y=-0.4, font=dict(size=11)))
    st.plotly_chart(fig_vc, use_container_width=True)

    _section_label("Proyección", C)
    col_met, col_per = st.columns(2)
    with col_met:
        metodo_proy = st.selectbox("Método", ["Tendencia lineal", "Promedio móvil"],
                                   key="me_proy_met", label_visibility="collapsed")
    with col_per:
        n_periodos = st.slider("Períodos a proyectar", 1, 12, 6, key="me_proy_n")

    valores_v = [r["ventas"] for r in ventas]
    valores_c = [r["costos"] for r in ventas]
    if metodo_proy == "Tendencia lineal":
        proy_v = proyeccion_lineal(valores_v, n_periodos)
        proy_c = proyeccion_lineal(valores_c, n_periodos)
    else:
        proy_v = proyeccion_promedio_movil(valores_v, 3, n_periodos)
        proy_c = proyeccion_promedio_movil(valores_c, 3, n_periodos)

    labels_hist = [r["periodo"] for r in ventas]
    labels_proy = [f"P+{i+1}" for i in range(n_periodos)]

    fig_proy = go.Figure()
    fig_proy.add_trace(go.Scatter(x=labels_hist, y=valores_v, mode="lines+markers",
                                  line=dict(color=C["primary"], width=2.5), marker=dict(size=6), name="Ventas reales"))
    fig_proy.add_trace(go.Scatter(x=labels_proy, y=proy_v, mode="lines+markers",
                                  line=dict(color=C["primary"], width=2, dash="dot"),
                                  marker=dict(size=5, symbol="circle-open"), name="Proyección ventas"))
    fig_proy.add_trace(go.Scatter(x=labels_hist, y=valores_c, mode="lines",
                                  line=dict(color="#e63946", width=2), name="Costos reales"))
    fig_proy.add_trace(go.Scatter(x=labels_proy, y=proy_c, mode="lines",
                                  line=dict(color="#e63946", width=2, dash="dot"), name="Proyección costos"))
    fig_proy.update_layout(template="plotly_white", height=280, margin=dict(l=0, r=0, t=10, b=10),
                           legend=dict(orientation="h", y=-0.45, font=dict(size=11)))
    st.plotly_chart(fig_proy, use_container_width=True)

    html_tp = (
        '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:12px;">'
        f'<tr style="border-bottom:1.5px solid rgba(77,107,255,0.10);">'
        f'<th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};">Período</th>'
        f'<th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};">Ventas proy.</th>'
        f'<th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};">Costos proy.</th>'
        f'<th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};">Margen est.</th>'
        '</tr>'
    )
    for i in range(n_periodos):
        v = proy_v[i]; c = proy_c[i]
        mg = (v - c) / v * 100 if v > 0 else 0
        html_tp += (
            f'<tr style="border-bottom:1px solid rgba(77,107,255,0.06);">'
            f'<td style="padding:7px 8px;font-weight:600;color:{C["n900"]};">{labels_proy[i]}</td>'
            f'<td style="padding:7px 8px;color:{C["primary"]};font-weight:700;">{_fmt_clp(v)}</td>'
            f'<td style="padding:7px 8px;color:{C["n600"]};">{_fmt_clp(c)}</td>'
            f'<td style="padding:7px 8px;font-weight:600;color:#06b6a0;">{mg:.1f}%</td>'
            '</tr>'
        )
    html_tp += '</table></div>'
    st.markdown(html_tp, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PROYECTOS
# ══════════════════════════════════════════════════════════════════════════════

def _render_proyectos(C):
    _section_label("Evaluar proyecto de inversión", C)

    col_inv, col_tasa = st.columns(2)
    with col_inv:
        st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Inversión inicial ($)</span>', unsafe_allow_html=True)
        inversion = st.number_input("Inversion", min_value=0, value=10_000_000, step=500_000, key="proy_inv", label_visibility="collapsed")
    with col_tasa:
        st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Tasa de descuento (%)</span>', unsafe_allow_html=True)
        tasa_desc = st.number_input("Tasa", min_value=0.0, value=12.0, step=0.5, key="proy_tasa", label_visibility="collapsed")

    st.markdown(f'<div style="font-size:11px;font-weight:600;color:{C["n600"]};margin:12px 0 6px;">Flujos de caja por período ($)</div>', unsafe_allow_html=True)
    n_flujos = st.slider("Numero de periodos", 1, 10, 5, key="proy_n_flujos")

    flujos_input = []
    cols_flujos = st.columns(min(n_flujos, 5))
    for i in range(n_flujos):
        with cols_flujos[i % 5]:
            st.markdown(f'<span style="font-size:10px;font-weight:600;color:{C["n400"]};">Periodo {i+1}</span>', unsafe_allow_html=True)
            f = st.number_input(f"F{i+1}", value=3_000_000, step=100_000, key=f"proy_f_{i}", label_visibility="collapsed")
            flujos_input.append(f)

    flujos_completos = [-inversion] + flujos_input
    tasa_dec = tasa_desc / 100
    van = calcular_van(flujos_completos, tasa_dec)
    tir = calcular_tir(flujos_completos)
    pb  = calcular_payback(flujos_completos)

    _section_label("Punto de equilibrio (opcional)", C)
    col_cf, col_pv = st.columns(2)
    with col_cf:
        st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Costos fijos / periodo ($)</span>', unsafe_allow_html=True)
        costos_fijos = st.number_input("CF", min_value=0, value=1_000_000, step=50_000, key="proy_cf", label_visibility="collapsed")
    with col_pv:
        st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Precio de venta unitario ($)</span>', unsafe_allow_html=True)
        precio_unit = st.number_input("PVU", min_value=1, value=50_000, step=1000, key="proy_pvu", label_visibility="collapsed")
    st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Costo variable unitario ($)</span>', unsafe_allow_html=True)
    costo_var = st.number_input("CVU", min_value=0, value=30_000, step=1000, key="proy_cvu", label_visibility="collapsed")
    margen_contrib = precio_unit - costo_var
    punto_eq = costos_fijos / margen_contrib if margen_contrib > 0 else None

    _section_label("Resultados del proyecto", C)

    if van > 0 and tir is not None and tir > tasa_dec:
        st.success("**VIABLE** — VAN positivo y TIR superior a la tasa de descuento.")
    elif van > 0 or (tir is not None and tir > tasa_dec):
        st.warning("**REVISAR** — Señales mixtas. Analiza las condiciones.")
    else:
        st.error("**NO VIABLE** — VAN negativo o TIR inferior a la tasa de descuento.")

    van_color = "#06d6a0" if van >= 0 else "#e63946"
    tir_color = "#06d6a0" if (tir is not None and tir > tasa_dec) else "#e63946"
    pb_txt = f"{pb} periodo(s)" if pb else "No se recupera"
    tir_txt = f"{tir*100:.2f}%" if tir is not None else "N/D"
    pe_txt = f"{punto_eq:,.0f} unidades" if punto_eq else "—"
    pe_sub = f"MC: {_fmt_clp(margen_contrib)}/u" if punto_eq else "Ingresa costos arriba"

    i_van = "Suma de flujos descontados menos la inversion inicial. VAN>0: el proyecto es viable. VAN<0: destruye valor."
    i_tir = "Tasa que hace el VAN igual a cero. TIR>tasa descuento: rentable. TIR<tasa: no compensa el riesgo."
    i_pb  = "Periodos necesarios para recuperar la inversion. Menor payback = menor riesgo."
    i_pe  = "Unidades minimas para cubrir costos fijos y variables. Formula: CF / (PVU - CVU)."

    CARDS = [
        ("VAN",       _fmt_clp(van), f"Tasa {tasa_desc}%",    van_color,    "Valor Actual Neto",       i_van),
        ("TIR",       tir_txt,       f"Desc. {tasa_desc}%",   tir_color,    "Tasa Interna de Retorno", i_tir),
        ("PAYBACK",   pb_txt,        "Recuperacion inversion", C["primary"], "Periodo de Recuperacion", i_pb),
        ("PUNTO EQ.", pe_txt,        pe_sub,                   "#F5A800",    "Punto de Equilibrio",     i_pe),
    ]

    st.markdown("""<style>
    button[data-testid="stPopoverButton"] {
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
        min-height: unset !important;
        height: auto !important;
        width: auto !important;
        box-shadow: none !important;
    }
    button[data-testid="stPopoverButton"] div { display: none !important; }
    button[data-testid="stPopoverButton"]::after {
        content: "ⓘ";
        font-size: 13px;
        color: #94a3b8;
        font-weight: 400;
        cursor: pointer;
    }
    button[data-testid="stPopoverButton"]:hover::after { color: #4d6bff; }
    div[data-testid="stPopoverBody"] {
        padding: 12px 14px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.10) !important;
        max-width: 260px !important;
    }
    div[data-testid="stPopoverBody"] p {
        font-size: 12px !important;
        color: #475569 !important;
        line-height: 1.5 !important;
        margin: 0 !important;
    }
    div[data-testid="stPopoverBody"] strong {
        font-size: 12px !important;
        color: #0f172a !important;
        display: block !important;
        margin-bottom: 4px !important;
    }
    </style>""", unsafe_allow_html=True)

    for row in range(0, 4, 2):
        cols = st.columns(2)
        for col_idx in range(2):
            lbl, valor, sub, color, titulo, info = CARDS[row + col_idx]
            with cols[col_idx]:
                st.markdown(
                    '<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);'
                    'border-radius:18px;padding:16px;margin-bottom:8px;'
                    'box-shadow:0 2px 8px rgba(77,107,255,0.05);">'
                    f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">'
                    f'<span style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;">{lbl}</span>'
                    f'</div>'
                    f'<div style="font-size:22px;font-weight:800;color:{color};letter-spacing:-0.5px;line-height:1;">{valor}</div>'
                    f'<div style="font-size:10px;color:#94a3b8;margin-top:4px;">{sub}</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                with st.popover("", use_container_width=False):
                    st.markdown(f"**{titulo}**\n\n{info}")

    _section_label("Flujo de caja acumulado", C)
    acumulado, acc = [], 0
    for f in flujos_completos:
        acc += f
        acumulado.append(acc)
    periodos_lbl = ["Inversion"] + [f"Periodo {i+1}" for i in range(n_flujos)]
    fig_flujo = go.Figure()
    fig_flujo.add_trace(go.Bar(
        x=periodos_lbl, y=acumulado,
        marker_color=[C["primary"] if v >= 0 else "#e63946" for v in acumulado],
        marker_line_width=0,
    ))
    fig_flujo.add_hline(y=0, line_color="rgba(77,107,255,0.3)", line_dash="dot")
    fig_flujo.update_layout(template="plotly_white", height=260, margin=dict(l=0,r=0,t=10,b=10), showlegend=False)
    st.plotly_chart(fig_flujo, use_container_width=True)


def _render_indicadores(C):
    _section_label("Datos de balance", C)
    metodo = st.radio("", ["Manual", "Subir Excel/CSV"],
                      horizontal=True, label_visibility="collapsed", key="me_ind_metodo")
    st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

    if metodo == "Subir Excel/CSV":
        uploaded = st.file_uploader(
            "Columnas: activos, pasivos, patrimonio, utilidad, ventas, costos_operacionales",
            type=["xlsx","csv"], key="me_bal_upload", label_visibility="collapsed"
        )
        if uploaded:
            try:
                df_up = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
                df_up.columns = [c.lower().strip().replace(" ","_") for c in df_up.columns]
                st.session_state["me_balance"] = df_up.iloc[0].to_dict()
                st.success("✓ Balance cargado.")
            except Exception as e:
                st.error(f"Error: {e}")
        df_tmpl = pd.DataFrame([{"activos":100_000_000,"pasivos":60_000_000,"patrimonio":40_000_000,
                                  "utilidad":8_000_000,"ventas":80_000_000,"costos_operacionales":55_000_000}])
        buf = io.BytesIO(); df_tmpl.to_excel(buf, index=False); buf.seek(0)
        st.download_button("⬇ Descargar plantilla balance", data=buf,
                           file_name="plantilla_balance.xlsx", use_container_width=True)
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Total Activos</span>', unsafe_allow_html=True)
            activos  = st.number_input("Activos",    value=st.session_state["me_balance"].get("activos",100_000_000),  step=1_000_000, key="me_activos",  label_visibility="collapsed")
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Patrimonio</span>', unsafe_allow_html=True)
            patrim   = st.number_input("Patrimonio", value=st.session_state["me_balance"].get("patrimonio",40_000_000), step=1_000_000, key="me_patrim",   label_visibility="collapsed")
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Ventas</span>', unsafe_allow_html=True)
            ventas_b = st.number_input("Ventas",     value=st.session_state["me_balance"].get("ventas",80_000_000),    step=1_000_000, key="me_ventasb",  label_visibility="collapsed")
        with c2:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Total Pasivos</span>', unsafe_allow_html=True)
            pasivos  = st.number_input("Pasivos",    value=st.session_state["me_balance"].get("pasivos",60_000_000),   step=1_000_000, key="me_pasivos",  label_visibility="collapsed")
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Utilidad del ejercicio</span>', unsafe_allow_html=True)
            utilidad = st.number_input("Utilidad",   value=st.session_state["me_balance"].get("utilidad",8_000_000),   step=500_000,   key="me_utilidad", label_visibility="collapsed")
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Costos operacionales</span>', unsafe_allow_html=True)
            costos_op = st.number_input("Costos op.", value=st.session_state["me_balance"].get("costos_operacionales",55_000_000), step=1_000_000, key="me_costosop", label_visibility="collapsed")
        st.session_state["me_balance"] = {
            "activos": activos, "pasivos": pasivos, "patrimonio": patrim,
            "utilidad": utilidad, "ventas": ventas_b, "costos_operacionales": costos_op,
        }

    bal = st.session_state["me_balance"]
    if not bal:
        return

    a  = bal.get("activos", 0)
    p  = bal.get("pasivos", 0)
    pt = bal.get("patrimonio", 0)
    u  = bal.get("utilidad", 0)
    v  = bal.get("ventas", 0)
    co = bal.get("costos_operacionales", 0)
    def _r(n, d): return n / d if d != 0 else 0

    INDICADORES = [
        ("Liquidez",        _r(a,p),            ".2f×", "Activos / Pasivos. >1 indica solvencia.",          "#06b6a0", 1.0,  True),
        ("Endeudamiento",   _r(p,pt),            ".2f×", "Pasivos / Patrimonio. <2 es manejable.",           "#F5A800", 2.0,  False),
        ("ROE",             _r(u,pt)*100,        ".1f%", "Utilidad / Patrimonio.",                           C["primary"], 10.0, True),
        ("ROA",             _r(u,a)*100,         ".1f%", "Utilidad / Activos totales.",                      C["primary"], 5.0,  True),
        ("Margen neto",     _r(u,v)*100,         ".1f%", "Utilidad / Ventas.",                               "#06b6a0", 8.0,  True),
        ("Margen operac.",  _r(v-co,v)*100,      ".1f%", "(Ventas − Costos op.) / Ventas.",                  "#06b6a0", 15.0, True),
        ("Rot. de activos", _r(v,a),             ".2f×", "Ventas / Activos.",                                C["primary"], 0.5, True),
        ("Apalancamiento",  _r(a,pt),            ".2f×", "Activos / Patrimonio.",                            "#F5A800", 3.0,  False),
        ("Cobertura deuda", _r(u+p*0.05,p*0.05), ".2f×", "Estimación cobertura de intereses.",              "#06b6a0", 1.5,  True),
    ]

    _section_label("Indicadores financieros", C)
    for grupo in [INDICADORES[i:i+2] for i in range(0, len(INDICADORES), 2)]:
        cols = st.columns(len(grupo))
        for col, ind in zip(cols, grupo):
            nombre_i, valor_i, fmt_i, desc_i, color_bueno, umbral, mayor = ind
            valor_str = f"{valor_i:{fmt_i[:-1]}}"
            card_color = color_bueno if (valor_i >= umbral if mayor else valor_i <= umbral) else "#e63946"
            col.markdown(
                '<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);'
                'border-radius:18px;padding:16px;margin-bottom:4px;'
                'box-shadow:0 2px 8px rgba(77,107,255,0.05);">'
                f'<div style="font-size:9px;font-weight:700;color:{C["n400"]};'
                f'text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">{nombre_i}</div>'
                f'<div style="font-size:22px;font-weight:800;color:{card_color};'
                f'letter-spacing:-0.5px;line-height:1;">{valor_str}</div>'
                f'<div style="font-size:10px;color:{C["n400"]};margin-top:4px;">{desc_i}</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        st.markdown("<div style='margin-bottom:4px;'></div>", unsafe_allow_html=True)

    _section_label("Perfil financiero (radar)", C)
    categorias = ["Liquidez", "Solvencia", "Rentab. (ROE)", "Eficiencia", "Margen"]
    valores_radar = [
        min(_r(a,p)/2, 1), max(1-_r(p,pt)/4, 0),
        min(max(_r(u,pt),0)/0.25, 1), min(_r(v,a)/1.5, 1),
        min(max(_r(u,v),0)/0.20, 1),
    ]
    valores_radar += [valores_radar[0]]
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=valores_radar, theta=categorias+[categorias[0]],
        fill="toself", fillcolor="rgba(77,107,255,0.12)",
        line=dict(color=C["primary"], width=2),
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0,1], tickfont=dict(size=9))),
        showlegend=False, height=280, margin=dict(l=20,r=20,t=20,b=20),
        template="plotly_white",
    )
    st.plotly_chart(fig_radar, use_container_width=True)