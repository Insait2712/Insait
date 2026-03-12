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


# ── HELPERS VISUALES (misma armonía que app.py) ───────────────────────────────

def _section_label(texto: str, C: dict):
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:{C["primary"]};'
        f'text-transform:uppercase;letter-spacing:1.2px;margin:20px 0 10px 0;">'
        f'{texto}</div>',
        unsafe_allow_html=True,
    )

def _card_kpi(label: str, valor: str, sub: str, color: str = "#4d6bff", delta: str = "", delta_pos: bool = True):
    delta_html = ""
    if delta:
        dc = "#06d6a0" if delta_pos else "#e63946"
        arrow = "↑" if delta_pos else "↓"
        delta_html = f'<div style="font-size:10px;font-weight:700;color:{dc};margin-top:3px;">{arrow} {delta}</div>'
    st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;
padding:16px 16px 14px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">{label}</div>
<div style="font-size:20px;font-weight:800;color:#0f172a;letter-spacing:-0.5px;line-height:1;">{valor}</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">{sub}</div>
{delta_html}</div>""", unsafe_allow_html=True)

def _divider():
    st.markdown("<hr style='border:none;border-top:1.5px solid rgba(77,107,255,0.08);margin:4px 0 16px 0;'>", unsafe_allow_html=True)

def _fmt_clp(n: float) -> str:
    return f"${n:,.0f}".replace(",", ".")

def _fmt_pct(n: float) -> str:
    return f"{n:+.1f}%"


# ── POPOVER INFORMATIVO (estilo plano, sin bordes redondeados) ────────────────

def _render_info_popover(key: str, titulo: str, formula_latex: str, descripcion: str,
                          interpretacion: str, C: dict):
    with st.expander(f"ⓘ  {titulo}", expanded=False):
        st.markdown(
            f'<div style="font-size:12px;font-weight:800;color:#0f172a;border-bottom:2px solid {C["primary"]};padding-bottom:6px;margin-bottom:12px;">{titulo}</div>'
            f'<div style="background:#f1f5f9;border-left:3px solid {C["primary"]};padding:10px 14px;margin-bottom:10px;">'
            f'<div style="font-size:9px;font-weight:700;color:{C["primary"]};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">FÓRMULA</div>'
            f'<div style="font-size:12px;font-weight:700;color:#1e293b;font-family:monospace;line-height:1.5;">{formula_latex}</div></div>'
            f'<div style="font-size:11px;color:#475569;line-height:1.6;margin-bottom:10px;">{descripcion}</div>'
            f'<div style="background:#f0f9ff;border-left:3px solid {C["primary"]};padding:10px 14px;">'
            f'<div style="font-size:9px;font-weight:700;color:{C["primary"]};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">CÓMO INTERPRETAR</div>'
            f'<div style="font-size:11px;color:#475569;line-height:1.6;">{interpretacion}</div></div>',
            unsafe_allow_html=True
        )


# ── DICCIONARIO DE INDICADORES — definiciones y fórmulas ─────────────────────

INFO_INDICADORES = {
    "VAN": {
        "titulo": "Valor Actual Neto (VAN)",
        "formula": "VAN = Σ [ Fₜ / (1 + r)ᵗ ]   para t = 0, 1, ..., n",
        "descripcion": (
            "El <b>VAN</b> mide el valor presente de todos los flujos de caja futuros de un "
            "proyecto, descontados a la tasa de oportunidad del inversionista (tasa de descuento), "
            "menos la inversión inicial. Expresa en pesos de hoy cuánto valor crea o destruye el proyecto. "
            "<br><br>"
            "<b>Fₜ</b> = Flujo de caja en el período t &nbsp;|&nbsp; "
            "<b>r</b> = Tasa de descuento &nbsp;|&nbsp; "
            "<b>n</b> = Número de períodos"
        ),
        "interpretacion": (
            "• <b>VAN &gt; 0</b>: El proyecto genera más valor del que cuesta financiarlo → VIABLE.<br>"
            "• <b>VAN = 0</b>: El proyecto apenas cubre el costo de capital → INDIFERENTE.<br>"
            "• <b>VAN &lt; 0</b>: El proyecto destruye valor → NO VIABLE."
        ),
    },
    "TIR": {
        "titulo": "Tasa Interna de Retorno (TIR)",
        "formula": "0 = Σ [ Fₜ / (1 + TIR)ᵗ ]   →  despejar TIR",
        "descripcion": (
            "La <b>TIR</b> es la tasa de descuento que hace que el VAN del proyecto sea exactamente cero. "
            "En otras palabras, es la rentabilidad intrínseca del proyecto, expresada como tasa porcentual anual. "
            "Se calcula numéricamente (no tiene fórmula algebraica cerrada) mediante métodos iterativos "
            "como bisección o Newton-Raphson.<br><br>"
            "Si hay cambios de signo múltiples en los flujos puede haber más de una TIR (problema de TIR múltiple)."
        ),
        "interpretacion": (
            "• <b>TIR &gt; Tasa de descuento</b>: El proyecto rinde más que el costo de capital → VIABLE.<br>"
            "• <b>TIR = Tasa de descuento</b>: Rentabilidad exactamente igual al costo → INDIFERENTE.<br>"
            "• <b>TIR &lt; Tasa de descuento</b>: No compensa el riesgo asumido → NO VIABLE."
        ),
    },
    "Payback": {
        "titulo": "Período de Recuperación (Payback)",
        "formula": "PB = t*  tal que  Σ Fₜ ≥ |F₀|   (t* = primer período)",
        "descripcion": (
            "El <b>Payback simple</b> es el número de períodos necesarios para recuperar la inversión inicial "
            "sumando los flujos de caja positivos de forma acumulada, <i>sin descontar</i>. "
            "Es una medida de liquidez y riesgo, no de rentabilidad.<br><br>"
            "El <b>Payback descontado</b> aplica el mismo criterio pero sobre los flujos ya traídos a valor "
            "presente, por lo que es más conservador y siempre mayor o igual al simple."
        ),
        "interpretacion": (
            "• Un payback más corto implica menor riesgo y mayor liquidez.<br>"
            "• No considera los flujos posteriores a la recuperación, por lo que puede favorecer proyectos "
            "  de corto plazo frente a otros más rentables a largo plazo.<br>"
            "• Úsalo como complemento del VAN y la TIR, no como criterio único."
        ),
    },
    "PE": {
        "titulo": "Punto de Equilibrio (Break-Even)",
        "formula": "PE = Costos Fijos / (Precio unitario − Costo variable unitario)",
        "descripcion": (
            "El <b>Punto de Equilibrio</b> indica el volumen mínimo de unidades que debe venderse para que "
            "los ingresos totales igualen a los costos totales, sin generar pérdida ni ganancia. "
            "Por encima de ese nivel el proyecto opera con utilidad; por debajo, con pérdida.<br><br>"
            "<b>Margen de contribución</b> = Precio unitario − Costo variable unitario: "
            "es la porción de cada venta que cubre los costos fijos."
        ),
        "interpretacion": (
            "• Mientras menor sea el PE, más fácil es que el proyecto sea rentable.<br>"
            "• Compara el PE con tu capacidad de producción o ventas esperadas.<br>"
            "• Un PE cercano a la capacidad máxima señala alta exposición al riesgo operativo."
        ),
    },
    "Liquidez": {
        "titulo": "Índice de Liquidez (Razón Corriente)",
        "formula": "Liquidez = Activos Totales / Pasivos Totales",
        "descripcion": (
            "Mide la capacidad de la empresa para cubrir sus obligaciones con sus activos disponibles. "
            "En un análisis más preciso se usa la <i>razón corriente</i> (activos corrientes / pasivos corrientes), "
            "aunque aquí se aplica sobre totales como aproximación de solvencia general."
        ),
        "interpretacion": (
            "• <b>&gt; 1.5</b>: Buena posición de liquidez.<br>"
            "• <b>1.0 – 1.5</b>: Ajustada, monitorear.<br>"
            "• <b>&lt; 1.0</b>: Riesgo de insolvencia a corto plazo."
        ),
    },
    "Endeudamiento": {
        "titulo": "Razón de Endeudamiento",
        "formula": "Endeudamiento = Pasivos Totales / Patrimonio",
        "descripcion": (
            "Indica qué proporción del financiamiento de la empresa proviene de deuda en relación "
            "con los recursos propios. También se conoce como <i>leverage</i> o apalancamiento financiero. "
            "Un valor alto implica mayor dependencia de acreedores y mayor riesgo financiero."
        ),
        "interpretacion": (
            "• <b>&lt; 1.0</b>: Empresa financiada principalmente con recursos propios.<br>"
            "• <b>1.0 – 2.0</b>: Nivel de deuda manejable en la mayoría de industrias.<br>"
            "• <b>&gt; 2.0</b>: Apalancamiento elevado, requiere análisis detallado de flujos."
        ),
    },
    "ROE": {
        "titulo": "Rentabilidad sobre el Patrimonio (ROE)",
        "formula": "ROE = Utilidad Neta / Patrimonio  × 100",
        "descripcion": (
            "El <b>ROE</b> (Return on Equity) mide cuántos pesos de utilidad genera la empresa por cada "
            "peso de capital aportado por los accionistas. Es el indicador de rentabilidad más relevante "
            "para los dueños o inversionistas del negocio."
        ),
        "interpretacion": (
            "• <b>&gt; 15%</b>: Rentabilidad alta para la mayoría de sectores.<br>"
            "• <b>8% – 15%</b>: Rentabilidad aceptable.<br>"
            "• <b>&lt; 8%</b>: Por debajo del costo de oportunidad típico del capital."
        ),
    },
    "ROA": {
        "titulo": "Rentabilidad sobre Activos (ROA)",
        "formula": "ROA = Utilidad Neta / Activos Totales  × 100",
        "descripcion": (
            "El <b>ROA</b> (Return on Assets) mide la eficiencia con que la empresa convierte sus activos "
            "en utilidad neta. A diferencia del ROE, no depende de la estructura de financiamiento "
            "(deuda vs. patrimonio), por lo que es útil para comparar empresas con distinto apalancamiento."
        ),
        "interpretacion": (
            "• <b>&gt; 8%</b>: Uso muy eficiente de los activos.<br>"
            "• <b>4% – 8%</b>: Eficiencia razonable.<br>"
            "• <b>&lt; 4%</b>: Los activos generan poca utilidad; revisar estructura de costos."
        ),
    },
    "Margen neto": {
        "titulo": "Margen Neto",
        "formula": "Margen neto = Utilidad Neta / Ventas  × 100",
        "descripcion": (
            "Indica qué porcentaje de cada peso vendido se convierte en utilidad neta después de "
            "descontar todos los costos, gastos e impuestos. Refleja la eficiencia global del negocio."
        ),
        "interpretacion": (
            "• Varía mucho por sector: retail suele ser 2–5%, tecnología puede superar 20%.<br>"
            "• Un margen creciente en el tiempo es señal de mejora operacional.<br>"
            "• Compara siempre contra el promedio de tu industria."
        ),
    },
    "Margen operac.": {
        "titulo": "Margen Operacional",
        "formula": "Margen op. = (Ventas − Costos Operacionales) / Ventas  × 100",
        "descripcion": (
            "Mide la rentabilidad de la operación principal del negocio, antes de intereses e impuestos. "
            "Excluye resultados no recurrentes y financieros, por lo que es un buen indicador de la "
            "eficiencia del modelo de negocio en sí mismo."
        ),
        "interpretacion": (
            "• <b>&gt; 20%</b>: Operación muy eficiente.<br>"
            "• <b>10% – 20%</b>: Desempeño operacional sólido.<br>"
            "• <b>&lt; 10%</b>: Presión de costos operativos; analizar estructura de gastos."
        ),
    },
    "Rot. de activos": {
        "titulo": "Rotación de Activos",
        "formula": "Rotación = Ventas / Activos Totales",
        "descripcion": (
            "Mide cuántos pesos de ventas genera la empresa por cada peso invertido en activos. "
            "Es un indicador de eficiencia en el uso de los recursos: una rotación alta implica que "
            "la empresa exprime bien sus activos para generar ingresos."
        ),
        "interpretacion": (
            "• Negocios de alto volumen y bajo margen (ej. supermercados) suelen tener rotaciones altas.<br>"
            "• Negocios de capital intensivo (ej. manufactura pesada) tienen rotaciones bajas pero márgenes mayores.<br>"
            "• La señal clave es la tendencia: una rotación creciente indica mejora en eficiencia."
        ),
    },
    "Apalancamiento": {
        "titulo": "Multiplicador de Capital (Apalancamiento)",
        "formula": "Apalancamiento = Activos Totales / Patrimonio",
        "descripcion": (
            "Indica cuántos pesos de activos respalda cada peso de patrimonio. "
            "Es el componente de estructura financiera del modelo DuPont: "
            "<b>ROE = Margen neto × Rotación de activos × Apalancamiento</b>. "
            "Un mayor apalancamiento amplifica tanto las ganancias como las pérdidas."
        ),
        "interpretacion": (
            "• <b>1.0</b>: Sin deuda, financiamiento 100% propio.<br>"
            "• <b>2.0 – 3.0</b>: Nivel usual en empresas sanas con deuda moderada.<br>"
            "• <b>&gt; 4.0</b>: Alto apalancamiento; aumenta riesgo ante caídas de ingresos."
        ),
    },
    "Cobertura deuda": {
        "titulo": "Cobertura de Intereses (estimada)",
        "formula": "Cobertura = (Utilidad + Intereses estimados) / Intereses estimados",
        "descripcion": (
            "Mide cuántas veces la utilidad operacional cubre el pago de intereses de la deuda. "
            "Aquí se estima el gasto financiero como el 5% del total de pasivos (aproximación). "
            "Para mayor precisión usa el estado de resultados real con el ítem de gastos financieros."
        ),
        "interpretacion": (
            "• <b>&gt; 3.0</b>: Holgura suficiente para servir la deuda sin tensión.<br>"
            "• <b>1.5 – 3.0</b>: Zona de alerta; ante una caída de ingresos puede haber presión.<br>"
            "• <b>&lt; 1.5</b>: Riesgo de incumplimiento financiero."
        ),
    },
}


# ── CÁLCULOS ──────────────────────────────────────────────────────────────────

def calcular_van(flujos: list, tasa: float) -> float:
    """VAN dado flujos = [flujo_0, flujo_1, ..., flujo_n] y tasa decimal."""
    return sum(f / (1 + tasa) ** i for i, f in enumerate(flujos))

def calcular_tir(flujos: list, precision: float = 1e-6) -> float | None:
    """TIR por bisección. Retorna None si no converge."""
    f = flujos
    if f[0] >= 0:
        return None
    lo, hi = -0.9999, 10.0
    for _ in range(1000):
        mid = (lo + hi) / 2
        van = sum(f[i] / (1 + mid) ** i for i in range(len(f)))
        if abs(van) < precision:
            return mid
        if van > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < precision:
            return mid
    return None

def calcular_payback(flujos: list) -> tuple:
    """Retorna payback_simple_años."""
    acum = 0
    pb_simple = None
    for i, f in enumerate(flujos):
        if i == 0:
            continue
        acum += f
        if acum >= abs(flujos[0]) and pb_simple is None:
            pb_simple = i
    return pb_simple

def proyeccion_lineal(valores: list, periodos: int) -> list:
    """Regresión lineal simple sobre valores históricos."""
    n = len(valores)
    if n < 2:
        return [valores[-1]] * periodos
    x = np.arange(n)
    y = np.array(valores, dtype=float)
    m, b = np.polyfit(x, y, 1)
    return [m * (n + i) + b for i in range(periodos)]

def proyeccion_promedio_movil(valores: list, ventana: int, periodos: int) -> list:
    if len(valores) < ventana:
        ventana = len(valores)
    base = sum(valores[-ventana:]) / ventana
    crecimiento = 0
    if len(valores) >= 2:
        crec_list = [(valores[i] - valores[i-1]) / abs(valores[i-1]) for i in range(1, len(valores)) if valores[i-1] != 0]
        crecimiento = sum(crec_list) / len(crec_list) if crec_list else 0
    return [base * (1 + crecimiento) ** (i + 1) for i in range(periodos)]


# ── ESTADO DE SESIÓN ──────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "me_ventas":     [],
        "me_flujos":     [],
        "me_balance":    {},
        "me_nombre":     "Mi Empresa",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
#  RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_mi_empresa(C: dict, BANK_COLOR: dict):
    _init_state()

    sub_tab = st.radio(
        "",
        ["📊 Dashboard", "📈 Ventas", "🏗️ Proyectos", "⚖️ Indicadores"],
        horizontal=True,
        label_visibility="collapsed",
        key="me_subtab",
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
#  SUB-TAB 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def _render_dashboard(C: dict):
    ventas  = st.session_state["me_ventas"]
    balance = st.session_state["me_balance"]

    nombre = st.text_input("Nombre de la empresa", value=st.session_state["me_nombre"],
                           key="me_nombre_input", label_visibility="collapsed",
                           placeholder="Nombre de tu empresa")
    st.session_state["me_nombre"] = nombre

    st.markdown(f"""
    <div style="padding:18px 20px;background:white;border-radius:20px;
                border:1.5px solid rgba(77,107,255,0.08);
                box-shadow:0 2px 10px rgba(77,107,255,0.05);margin-bottom:20px;">
      <div style="font-size:10px;font-weight:700;color:{C["n400"]};text-transform:uppercase;
                  letter-spacing:1.4px;margin-bottom:4px;">RESUMEN EJECUTIVO</div>
      <div style="font-size:19px;font-weight:800;color:{C["n900"]};letter-spacing:-0.4px;">
        {nombre} 📋</div>
      <div style="font-size:11px;color:{C["n400"]};margin-top:3px;">
        {date.today().strftime("%d de %B, %Y")}</div>
    </div>""", unsafe_allow_html=True)

    _section_label("KPIs principales", C)

    if len(ventas) >= 1:
        ultimo   = ventas[-1]
        v_actual = ultimo.get("ventas", 0)
        c_actual = ultimo.get("costos", 0)
        margen   = ((v_actual - c_actual) / v_actual * 100) if v_actual > 0 else 0

        delta_v = ""
        delta_pos = True
        if len(ventas) >= 2:
            v_ant = ventas[-2].get("ventas", 0)
            if v_ant > 0:
                var = (v_actual - v_ant) / v_ant * 100
                delta_v  = f"{abs(var):.1f}% vs período anterior"
                delta_pos = var >= 0

        resultado = v_actual - c_actual
        delta_arrow = "↑" if delta_pos else "↓"
        delta_dc = "#06d6a0" if delta_pos else "#e63946"
        delta_extra = f'<div style="font-size:10px;font-weight:700;color:{delta_dc};margin-top:3px;">{delta_arrow} {delta_v}</div>' if delta_v else ""

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">VENTAS</div>
<div style="font-size:20px;font-weight:800;color:{C["primary"]};letter-spacing:-0.5px;line-height:1;">{_fmt_clp(v_actual)}</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">{ultimo.get("periodo","—")}</div>
{delta_extra}</div>""", unsafe_allow_html=True)
            st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">MARGEN BRUTO</div>
<div style="font-size:20px;font-weight:800;color:#06b6a0;letter-spacing:-0.5px;line-height:1;">{margen:.1f}%</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">Ventas − Costos</div></div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">COSTOS</div>
<div style="font-size:20px;font-weight:800;color:#e63946;letter-spacing:-0.5px;line-height:1;">{_fmt_clp(c_actual)}</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">{ultimo.get("periodo","—")}</div></div>""", unsafe_allow_html=True)
            res_color = C["primary"] if resultado >= 0 else "#e63946"
            st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">RESULTADO</div>
<div style="font-size:20px;font-weight:800;color:{res_color};letter-spacing:-0.5px;line-height:1;">{_fmt_clp(resultado)}</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">Ventas − Costos</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:#f8faff;border:1.5px solid rgba(77,107,255,0.10);
                    border-radius:16px;padding:20px;text-align:center;color:{C["n400"]};
                    font-size:12px;margin-bottom:16px;">
          Ingresa datos en la pestaña <b>📈 Ventas</b> para ver tus KPIs aquí.
        </div>""", unsafe_allow_html=True)

    if balance:
        _section_label("Indicadores de balance", C)
        activos  = balance.get("activos", 0)
        pasivos  = balance.get("pasivos", 0)
        patrim   = balance.get("patrimonio", 0)
        utilidad = balance.get("utilidad", 0)

        col3, col4 = st.columns(2)
        with col3:
            liq = activos / pasivos if pasivos > 0 else 0
            liq_color = "#06b6a0" if liq >= 1 else "#e63946"
            st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">LIQUIDEZ</div>
<div style="font-size:20px;font-weight:800;color:{liq_color};letter-spacing:-0.5px;line-height:1;">{liq:.2f}x</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">Activos / Pasivos</div></div>""", unsafe_allow_html=True)
            roe = (utilidad / patrim * 100) if patrim > 0 else 0
            st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">ROE</div>
<div style="font-size:20px;font-weight:800;color:{C["primary"]};letter-spacing:-0.5px;line-height:1;">{roe:.1f}%</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">Utilidad / Patrimonio</div></div>""", unsafe_allow_html=True)
        with col4:
            end = pasivos / patrim if patrim > 0 else 0
            end_color = "#F5A800" if end <= 2 else "#e63946"
            st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">ENDEUDAMIENTO</div>
<div style="font-size:20px;font-weight:800;color:{end_color};letter-spacing:-0.5px;line-height:1;">{end:.2f}x</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">Pasivos / Patrimonio</div></div>""", unsafe_allow_html=True)
            roa = (utilidad / activos * 100) if activos > 0 else 0
            st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">ROA</div>
<div style="font-size:20px;font-weight:800;color:{C["primary"]};letter-spacing:-0.5px;line-height:1;">{roa:.1f}%</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">Utilidad / Activos</div></div>""", unsafe_allow_html=True)

    if len(ventas) >= 2:
        _section_label("Tendencia de ventas", C)
        df_v = pd.DataFrame(ventas)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_v["periodo"], y=df_v["ventas"],
            fill="tozeroy", fillcolor="rgba(77,107,255,0.07)",
            line=dict(color=C["primary"], width=2.5),
            mode="lines+markers", marker=dict(color=C["primary"], size=6),
            name="Ventas",
        ))
        if "costos" in df_v.columns:
            fig.add_trace(go.Scatter(
                x=df_v["periodo"], y=df_v["costos"],
                line=dict(color="#e63946", width=2, dash="dot"),
                mode="lines", name="Costos",
            ))
        fig.update_layout(template="plotly_white", height=220,
                          margin=dict(l=0, r=0, t=10, b=10),
                          legend=dict(orientation="h", y=-0.4,
                                      font=dict(family="Plus Jakarta Sans", size=11)))
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SUB-TAB 2 — VENTAS
# ══════════════════════════════════════════════════════════════════════════════

def _render_ventas(C: dict):

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
                if uploaded.name.endswith(".csv"):
                    df_up = pd.read_csv(uploaded)
                else:
                    df_up = pd.read_excel(uploaded)
                df_up.columns = [c.lower().strip() for c in df_up.columns]
                cols_req = {"periodo", "ventas", "costos"}
                if cols_req.issubset(set(df_up.columns)):
                    st.session_state["me_ventas"] = df_up[["periodo","ventas","costos"]].to_dict("records")
                    st.success(f"✓ {len(df_up)} períodos cargados.")
                else:
                    st.error(f"El archivo debe tener las columnas: {cols_req}. Encontradas: {set(df_up.columns)}")
            except Exception as e:
                st.error(f"Error al leer archivo: {e}")

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
        with st.container():
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

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("＋ Agregar período", use_container_width=True, key="me_btn_add"):
                    if periodo:
                        st.session_state["me_ventas"].append({
                            "periodo": periodo, "ventas": ventas_inp, "costos": costos_inp
                        })
                        st.rerun()
            with col_btn2:
                if st.button("🗑 Limpiar todo", use_container_width=True, key="me_btn_clear"):
                    st.session_state["me_ventas"] = []
                    st.rerun()

    ventas = st.session_state["me_ventas"]

    if not ventas:
        st.markdown(f'<div style="font-size:12px;color:{C["n400"]};text-align:center;padding:24px;">Aún no hay datos. Agrega períodos arriba.</div>', unsafe_allow_html=True)
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
        html_tabla += f'<th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};text-transform:uppercase;letter-spacing:0.8px;">{col}</th>'
    html_tabla += '</tr>'
    for _, row in df_v.iterrows():
        var_color = C["primary"]
        if row["Variación"] != "—":
            var_color = "#06d6a0" if float(row["Variación"].replace("%","").replace("+","")) >= 0 else "#e63946"
        html_tabla += f'''<tr style="border-bottom:1px solid rgba(77,107,255,0.06);">
          <td style="padding:7px 8px;font-weight:600;color:{C["n900"]};">{row["periodo"]}</td>
          <td style="padding:7px 8px;color:{C["n900"]};">{_fmt_clp(row["ventas"])}</td>
          <td style="padding:7px 8px;color:{C["n600"]};">{_fmt_clp(row["costos"])}</td>
          <td style="padding:7px 8px;font-weight:600;color:#06b6a0;">{row["Margen"]}</td>
          <td style="padding:7px 8px;font-weight:700;color:{var_color};">{row["Variación"]}</td>
        </tr>'''
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
                         legend=dict(orientation="h", y=-0.4,
                                     font=dict(family="Plus Jakarta Sans", size=11)))
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
                                  line=dict(color=C["primary"], width=2.5),
                                  marker=dict(size=6), name="Ventas reales"))
    fig_proy.add_trace(go.Scatter(x=labels_proy, y=proy_v, mode="lines+markers",
                                  line=dict(color=C["primary"], width=2, dash="dot"),
                                  marker=dict(size=5, symbol="circle-open"),
                                  name="Proyección ventas"))
    fig_proy.add_trace(go.Scatter(x=labels_hist, y=valores_c, mode="lines",
                                  line=dict(color="#e63946", width=2),
                                  name="Costos reales"))
    fig_proy.add_trace(go.Scatter(x=labels_proy, y=proy_c, mode="lines",
                                  line=dict(color="#e63946", width=2, dash="dot"),
                                  name="Proyección costos"))
    fig_proy.update_layout(template="plotly_white", height=280,
                           margin=dict(l=0, r=0, t=10, b=10),
                           legend=dict(orientation="h", y=-0.45,
                                       font=dict(family="Plus Jakarta Sans", size=11)))
    st.plotly_chart(fig_proy, use_container_width=True)

    html_tp = '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:12px;">'
    html_tp += f'<tr style="border-bottom:1.5px solid rgba(77,107,255,0.10);"><th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};text-transform:uppercase;letter-spacing:0.8px;">Período</th><th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};text-transform:uppercase;letter-spacing:0.8px;">Ventas proyectadas</th><th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};text-transform:uppercase;letter-spacing:0.8px;">Costos proyectados</th><th style="text-align:left;padding:6px 8px;font-size:10px;font-weight:700;color:{C["n400"]};text-transform:uppercase;letter-spacing:0.8px;">Margen est.</th></tr>'
    for i in range(n_periodos):
        v = proy_v[i]; c = proy_c[i]
        mg = (v - c) / v * 100 if v > 0 else 0
        html_tp += f'<tr style="border-bottom:1px solid rgba(77,107,255,0.06);"><td style="padding:7px 8px;font-weight:600;color:{C["n900"]};">{labels_proy[i]}</td><td style="padding:7px 8px;color:{C["primary"]};font-weight:700;">{_fmt_clp(v)}</td><td style="padding:7px 8px;color:{C["n600"]};">{_fmt_clp(c)}</td><td style="padding:7px 8px;font-weight:600;color:#06b6a0;">{mg:.1f}%</td></tr>'
    html_tp += '</table></div>'
    st.markdown(html_tp, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SUB-TAB 3 — PROYECTOS
# ══════════════════════════════════════════════════════════════════════════════

def _render_proyectos(C: dict):
    _section_label("Evaluar proyecto de inversión", C)

    with st.container():
        st.markdown(f'<div style="font-size:11px;font-weight:600;color:{C["n600"]};margin-bottom:8px;">Inversión inicial y flujos esperados</div>', unsafe_allow_html=True)

        col_inv, col_tasa = st.columns(2)
        with col_inv:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Inversión inicial ($)</span>', unsafe_allow_html=True)
            inversion = st.number_input("Inversión", min_value=0, value=10_000_000,
                                        step=500_000, key="proy_inv", label_visibility="collapsed")
        with col_tasa:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Tasa de descuento (%)</span>', unsafe_allow_html=True)
            tasa_desc = st.number_input("Tasa", min_value=0.0, value=12.0,
                                        step=0.5, key="proy_tasa", label_visibility="collapsed")

        st.markdown(f'<div style="font-size:11px;font-weight:600;color:{C["n600"]};margin:12px 0 6px;">Flujos de caja por período ($)</div>', unsafe_allow_html=True)
        n_flujos = st.slider("Número de períodos", 1, 10, 5, key="proy_n_flujos")

        flujos_input = []
        cols_flujos = st.columns(min(n_flujos, 5))
        for i in range(n_flujos):
            col_idx = i % 5
            with cols_flujos[col_idx]:
                st.markdown(f'<span style="font-size:10px;font-weight:600;color:{C["n400"]};">Período {i+1}</span>', unsafe_allow_html=True)
                f = st.number_input(f"F{i+1}", value=3_000_000, step=100_000,
                                    key=f"proy_f_{i}", label_visibility="collapsed")
                flujos_input.append(f)

    # ── Cálculos ──────────────────────────────────────────────────────────────
    flujos_completos = [-inversion] + flujos_input
    tasa_dec = tasa_desc / 100

    van   = calcular_van(flujos_completos, tasa_dec)
    tir   = calcular_tir(flujos_completos)
    pb    = calcular_payback(flujos_completos)

    # Punto de equilibrio
    st.markdown(f'<div style="font-size:11px;font-weight:600;color:{C["n600"]};margin:12px 0 6px;">Punto de equilibrio (opcional)</div>', unsafe_allow_html=True)
    with st.container():
        col_cf, col_mc = st.columns(2)
        with col_cf:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Costos fijos / período ($)</span>', unsafe_allow_html=True)
            costos_fijos = st.number_input("CF", min_value=0, value=1_000_000, step=50_000,
                                           key="proy_cf", label_visibility="collapsed")
        with col_mc:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Precio de venta unitario ($)</span>', unsafe_allow_html=True)
            precio_unit = st.number_input("PVU", min_value=1, value=50_000, step=1000,
                                          key="proy_pvu", label_visibility="collapsed")
        col_cv = st.columns(1)[0]
        with col_cv:
            st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Costo variable unitario ($)</span>', unsafe_allow_html=True)
            costo_var = st.number_input("CVU", min_value=0, value=30_000, step=1000,
                                        key="proy_cvu", label_visibility="collapsed")

    margen_contrib = precio_unit - costo_var
    punto_eq = costos_fijos / margen_contrib if margen_contrib > 0 else None

    # ── Resultados ────────────────────────────────────────────────────────────
    _section_label("Resultados del proyecto", C)

    # Semáforo de viabilidad
    if van > 0 and tir is not None and tir > tasa_dec:
        semaforo_color = "#06d6a0"
        semaforo_txt   = "VIABLE ✓"
        semaforo_desc  = "VAN positivo y TIR superior a la tasa de descuento."
    elif van > 0 or (tir is not None and tir > tasa_dec):
        semaforo_color = "#F5A800"
        semaforo_txt   = "REVISAR ⚠"
        semaforo_desc  = "Señales mixtas. Analiza las condiciones con más detalle."
    else:
        semaforo_color = "#e63946"
        semaforo_txt   = "NO VIABLE ✗"
        semaforo_desc  = "VAN negativo o TIR inferior a la tasa de descuento."

    st.markdown(f"""
    <div style="background:{semaforo_color}14;border:1.5px solid {semaforo_color}55;
                border-radius:16px;padding:16px 20px;margin-bottom:16px;
                display:flex;align-items:center;gap:14px;">
      <div style="font-size:28px;font-weight:900;color:{semaforo_color};letter-spacing:-1px;
                  min-width:80px;">{semaforo_txt}</div>
      <div style="font-size:11px;color:{C["n600"]};line-height:1.5;">{semaforo_desc}</div>
    </div>""", unsafe_allow_html=True)

    # ── Cards resultados ──────────────────────────────────────────────────────
    col_r1, col_r2 = st.columns(2)

    van_color = "#06d6a0" if van >= 0 else "#e63946"
    pb_txt = f"{pb} período(s)" if pb else "No se recupera"
    tir_pct = f"{tir*100:.2f}%" if tir is not None else "N/D"
    tir_color = "#06d6a0" if (tir is not None and tir > tasa_dec) else "#e63946"

    with col_r1:
        st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">VAN</div>
<div style="font-size:20px;font-weight:800;color:{van_color};letter-spacing:-0.5px;line-height:1;">{_fmt_clp(van)}</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">Tasa {tasa_desc}%</div>
</div>""", unsafe_allow_html=True)
        st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">PAYBACK</div>
<div style="font-size:20px;font-weight:800;color:{C["primary"]};letter-spacing:-0.5px;line-height:1;">{pb_txt}</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">Períodos para recuperar inversión</div>
</div>""", unsafe_allow_html=True)

    with col_r2:
        st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">TIR</div>
<div style="font-size:20px;font-weight:800;color:{tir_color};letter-spacing:-0.5px;line-height:1;">{tir_pct}</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">vs tasa descuento {tasa_desc}%</div>
</div>""", unsafe_allow_html=True)
        if punto_eq:
            st.markdown(f"""<div style="background:white;border:1.5px solid rgba(77,107,255,0.08);border-radius:18px;padding:16px;margin-bottom:10px;box-shadow:0 2px 8px rgba(77,107,255,0.05);">
<div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">PUNTO DE EQUILIBRIO</div>
<div style="font-size:20px;font-weight:800;color:#F5A800;letter-spacing:-0.5px;line-height:1;">{punto_eq:,.0f} unidades</div>
<div style="font-size:10px;color:#94a3b8;margin-top:3px;">Margen contribución: {_fmt_clp(margen_contrib)}/u</div>
</div>""", unsafe_allow_html=True)

    # ── Gráfico flujo acumulado ───────────────────────────────────────────────
    _section_label("Flujo de caja acumulado", C)
    acumulado = []
    acc = 0
    for f in flujos_completos:
        acc += f
        acumulado.append(acc)

    periodos_lbl = ["Inversión"] + [f"Período {i+1}" for i in range(n_flujos)]
    colores_bar  = [C["primary"] if v >= 0 else "#e63946" for v in acumulado]

    fig_flujo = go.Figure()
    fig_flujo.add_trace(go.Bar(x=periodos_lbl, y=acumulado, marker_color=colores_bar,
                               marker_line_width=0, name="Flujo acumulado"))
    fig_flujo.add_hline(y=0, line_color="rgba(77,107,255,0.3)", line_dash="dot")
    fig_flujo.update_layout(template="plotly_white", height=260,
                            margin=dict(l=0, r=0, t=10, b=10),
                            showlegend=False)
    st.plotly_chart(fig_flujo, use_container_width=True)

    # ── Gráfico punto de equilibrio ───────────────────────────────────────────
    if punto_eq and margen_contrib > 0:
        _section_label("Punto de equilibrio", C)
        unidades = np.linspace(0, punto_eq * 2, 100)
        ingresos_pe = unidades * precio_unit
        costos_pe   = costos_fijos + unidades * costo_var

        fig_pe = go.Figure()
        fig_pe.add_trace(go.Scatter(x=unidades, y=ingresos_pe, mode="lines",
                                    line=dict(color=C["primary"], width=2.5), name="Ingresos"))
        fig_pe.add_trace(go.Scatter(x=unidades, y=costos_pe, mode="lines",
                                    line=dict(color="#e63946", width=2.5), name="Costos totales"))
        fig_pe.add_vline(x=punto_eq, line_color="#F5A800", line_dash="dot",
                         annotation_text=f"PE: {punto_eq:,.0f} u.",
                         annotation_font_color="#F5A800")
        fig_pe.update_layout(template="plotly_white", height=240,
                             margin=dict(l=0, r=0, t=20, b=10),
                             legend=dict(orientation="h", y=-0.4,
                                         font=dict(family="Plus Jakarta Sans", size=11)))
        st.plotly_chart(fig_pe, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SUB-TAB 4 — INDICADORES
# ══════════════════════════════════════════════════════════════════════════════

def _render_indicadores(C: dict):
    _section_label("Datos de balance", C)

    metodo = st.radio("", ["Manual", "Subir Excel/CSV"],
                      horizontal=True, label_visibility="collapsed", key="me_ind_metodo")
    st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

    if metodo == "Subir Excel/CSV":
        uploaded = st.file_uploader(
            "Columnas requeridas: activos, pasivos, patrimonio, utilidad, ventas, costos_operacionales, ingresos_financieros",
            type=["xlsx","csv"], key="me_bal_upload", label_visibility="collapsed"
        )
        if uploaded:
            try:
                df_up = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
                df_up.columns = [c.lower().strip().replace(" ","_") for c in df_up.columns]
                fila = df_up.iloc[0].to_dict()
                st.session_state["me_balance"] = fila
                st.success("✓ Balance cargado.")
            except Exception as e:
                st.error(f"Error: {e}")

        df_tmpl = pd.DataFrame([{"activos":100_000_000,"pasivos":60_000_000,"patrimonio":40_000_000,"utilidad":8_000_000,"ventas":80_000_000,"costos_operacionales":55_000_000,"ingresos_financieros":3_000_000}])
        buf = io.BytesIO(); df_tmpl.to_excel(buf, index=False); buf.seek(0)
        st.download_button("⬇ Descargar plantilla balance", data=buf,
                           file_name="plantilla_balance.xlsx", use_container_width=True)
    else:
        with st.container():
            st.markdown(f'<div style="font-size:11px;font-weight:600;color:{C["n600"]};margin-bottom:8px;">Balance general ($)</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Total Activos</span>', unsafe_allow_html=True)
                activos = st.number_input("Activos", value=st.session_state["me_balance"].get("activos",100_000_000), step=1_000_000, key="me_activos", label_visibility="collapsed")
                st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Patrimonio</span>', unsafe_allow_html=True)
                patrim  = st.number_input("Patrimonio", value=st.session_state["me_balance"].get("patrimonio",40_000_000), step=1_000_000, key="me_patrim", label_visibility="collapsed")
                st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Ventas</span>', unsafe_allow_html=True)
                ventas_b = st.number_input("Ventas", value=st.session_state["me_balance"].get("ventas",80_000_000), step=1_000_000, key="me_ventasb", label_visibility="collapsed")
            with c2:
                st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Total Pasivos</span>', unsafe_allow_html=True)
                pasivos = st.number_input("Pasivos", value=st.session_state["me_balance"].get("pasivos",60_000_000), step=1_000_000, key="me_pasivos", label_visibility="collapsed")
                st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Utilidad del ejercicio</span>', unsafe_allow_html=True)
                utilidad = st.number_input("Utilidad", value=st.session_state["me_balance"].get("utilidad",8_000_000), step=500_000, key="me_utilidad", label_visibility="collapsed")
                st.markdown('<span style="font-size:11px;font-weight:600;color:#64748b;">Costos operacionales</span>', unsafe_allow_html=True)
                costos_op = st.number_input("Costos op.", value=st.session_state["me_balance"].get("costos_operacionales",55_000_000), step=1_000_000, key="me_costosop", label_visibility="collapsed")

            st.session_state["me_balance"] = {
                "activos": activos, "pasivos": pasivos, "patrimonio": patrim,
                "utilidad": utilidad, "ventas": ventas_b,
                "costos_operacionales": costos_op,
            }

    bal = st.session_state["me_balance"]
    if not bal:
        st.markdown(f'<div style="font-size:12px;color:{C["n400"]};text-align:center;padding:24px;">Ingresa los datos de balance para calcular los indicadores.</div>', unsafe_allow_html=True)
        return

    a  = bal.get("activos", 0)
    p  = bal.get("pasivos", 0)
    pt = bal.get("patrimonio", 0)
    u  = bal.get("utilidad", 0)
    v  = bal.get("ventas", 0)
    co = bal.get("costos_operacionales", 0)

    def _ratio(n, d): return n / d if d != 0 else 0

    INDICADORES = [
        # (nombre, valor, formato, descripción, color_bueno, umbral_bueno, mayor_es_mejor)
        ("Liquidez",         _ratio(a, p),           ".2f×", "Activos / Pasivos. >1 indica solvencia.",               "#06b6a0", 1.0,   True),
        ("Endeudamiento",    _ratio(p, pt),           ".2f×", "Pasivos / Patrimonio. <2 es manejable.",               "#F5A800", 2.0,   False),
        ("ROE",              _ratio(u, pt)*100,       ".1f%", "Utilidad / Patrimonio. Rentabilidad accionistas.",     C["primary"], 10.0, True),
        ("ROA",              _ratio(u, a)*100,        ".1f%", "Utilidad / Activos totales.",                          C["primary"], 5.0,  True),
        ("Margen neto",      _ratio(u, v)*100,        ".1f%", "Utilidad / Ventas.",                                   "#06b6a0", 8.0,   True),
        ("Margen operac.",   _ratio(v - co, v)*100,   ".1f%", "(Ventas − Costos op.) / Ventas.",                     "#06b6a0", 15.0,  True),
        ("Rot. de activos",  _ratio(v, a),            ".2f×", "Ventas / Activos. Eficiencia de uso de activos.",      C["primary"], 0.5,  True),
        ("Apalancamiento",   _ratio(a, pt),           ".2f×", "Activos / Patrimonio (multiplicador del capital).",    "#F5A800", 3.0,   False),
        ("Cobertura deuda",  _ratio(u + p * 0.05, p * 0.05), ".2f×", "Estimación cobertura de intereses.",           "#06b6a0", 1.5,   True),
    ]

    _section_label("Indicadores financieros", C)

    grupos = [INDICADORES[i:i+2] for i in range(0, len(INDICADORES), 2)]
    for grupo in grupos:
        cols = st.columns(len(grupo))
        for col, ind in zip(cols, grupo):
            nombre_i, valor_i, fmt_i, desc_i, color_bueno, umbral, mayor = ind

            if fmt_i.endswith("%"):
                valor_str = f"{valor_i:{fmt_i[:-1]}}"
            else:
                valor_str = f"{valor_i:{fmt_i[:-1]}}"

            if mayor:
                card_color = color_bueno if valor_i >= umbral else "#e63946"
            else:
                card_color = color_bueno if valor_i <= umbral else "#e63946"

            with col:
                # Card del indicador
                st.markdown(f"""
                <div style="background:white;border:1.5px solid rgba(77,107,255,0.08);
                            border-radius:18px;padding:16px;margin-bottom:4px;
                            box-shadow:0 2px 8px rgba(77,107,255,0.05);">
                  <div style="font-size:9px;font-weight:700;color:{C["n400"]};
                              text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px;">{nombre_i}</div>
                  <div style="font-size:22px;font-weight:800;color:{card_color};
                              letter-spacing:-0.5px;line-height:1;">{valor_str}</div>
                  <div style="font-size:10px;color:{C["n400"]};margin-top:4px;line-height:1.4;">{desc_i}</div>
                </div>""", unsafe_allow_html=True)

                # Botón popover de información para cada indicador
                if nombre_i in INFO_INDICADORES:
                    info = INFO_INDICADORES[nombre_i]
                    _render_info_popover(
                        f"ind_{nombre_i}", info["titulo"], info["formula"],
                        info["descripcion"], info["interpretacion"], C
                    )

        st.markdown("<div style='margin-bottom:4px;'></div>", unsafe_allow_html=True)

    # ── Gráfico radar ─────────────────────────────────────────────────────────
    _section_label("Perfil financiero (radar)", C)

    categorias = ["Liquidez", "Solvencia", "Rentab. (ROE)", "Eficiencia", "Margen"]
    liq_norm  = min(_ratio(a, p) / 2, 1)
    solv_norm = max(1 - _ratio(p, pt) / 4, 0)
    roe_norm  = min(max(_ratio(u, pt), 0) / 0.25, 1)
    efic_norm = min(_ratio(v, a) / 1.5, 1)
    marg_norm = min(max(_ratio(u, v), 0) / 0.20, 1)
    valores_radar = [liq_norm, solv_norm, roe_norm, efic_norm, marg_norm]
    valores_radar += [valores_radar[0]]
    cats_cierre  = categorias + [categorias[0]]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=valores_radar, theta=cats_cierre,
        fill="toself", fillcolor=f"rgba(77,107,255,0.12)",
        line=dict(color=C["primary"], width=2),
        name="Tu empresa",
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1], tickfont=dict(size=9))),
        showlegend=False, height=280, margin=dict(l=20, r=20, t=20, b=20),
        template="plotly_white",
    )
    st.plotly_chart(fig_radar, use_container_width=True)