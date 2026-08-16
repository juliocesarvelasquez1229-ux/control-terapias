import streamlit as st
import pandas as pd
import datetime
import json
import requests
import io
import os
import warnings
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Silenciar avisos de obsolescencia de librerías para mantener la terminal limpia
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Gestión de Terapias y Liquidación Cambiaria",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="auto"
)

# --- ESTILOS CSS PERSONALIZADOS (ALTO CONTRASTE Y RESPONSIVO PARA MÓVILES) ---
st.markdown("""
<style>
/* Espaciado general y contenedor */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2.5rem !important;
}

/* Tarjetas de métricas modernas con efecto visual */
div[data-testid="stMetric"], [data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%) !important;
    padding: 14px 18px !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255, 255, 255, 0.14) !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.25) !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    overflow: visible !important;
}

div[data-testid="stMetric"]:hover {
    border-color: rgba(96, 165, 250, 0.45) !important;
}

/* TÍTULOS DE LAS MÉTRICAS - ALTO CONTRASTE Y SIEMPRE VISIBLES */
div[data-testid="stMetricLabel"],
div[data-testid="stMetricLabel"] *,
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] * {
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    color: #93c5fd !important; /* Azul claro celeste de alto contraste */
    opacity: 1 !important;
    visibility: visible !important;
    white-space: normal !important;
    word-break: break-word !important;
    line-height: 1.3 !important;
    display: block !important;
}

/* VALORES NUMÉRICOS DE LAS MÉTRICAS */
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] *,
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] * {
    font-size: 1.55rem !important;
    font-weight: 800 !important;
    color: #ffffff !important;
    line-height: 1.25 !important;
}

/* DELTA / ETIQUETA SECUNDARIA */
div[data-testid="stMetricDelta"],
[data-testid="stMetricDelta"] * {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
}

/* Botones principales */
.stButton > button, .stFormSubmitButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease-in-out !important;
}

/* Adaptabilidad para Dispositivos Móviles (pantallas <= 768px) */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 1rem !important;
    }
    
    /* Columnas apiladas fluidas en celular */
    div[data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
        margin-bottom: 0.5rem;
    }
    
    div[data-testid="stMetric"], [data-testid="stMetric"] {
        padding: 12px 16px !important;
        margin-bottom: 8px !important;
        min-height: 80px !important;
    }
    
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] * {
        font-size: 0.92rem !important;
        color: #93c5fd !important;
    }
    
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] * {
        font-size: 1.38rem !important;
    }
    
    .stButton > button, .stFormSubmitButton > button {
        min-height: 44px !important;
        font-size: 0.95rem !important;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important;
        flex-wrap: wrap !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-size: 0.85rem !important;
        padding: 6px 10px !important;
    }
}
</style>
""", unsafe_allow_html=True)

# --- PROTECCIÓN CON CONTRASEÑA / PIN DE ACCESO ---
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "terapias2026")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<div style='text-align: center; margin-top: 2rem;'><h1>🩺 Control de Terapias</h1><p style='color: #94a3b8;'>Sistema de Gestión de Terapias y Liquidación Cambiaria Oficial</p></div>", unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("form_login"):
            st.subheader("🔐 Iniciar Sesión")
            clave_ingresada = st.text_input("Contraseña de Acceso", type="password", placeholder="Ingresa tu clave...")
            btn_login = st.form_submit_button("🚀 Entrar al Sistema", width="stretch")
            
            if btn_login:
                if clave_ingresada == APP_PASSWORD:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta. Por favor intenta de nuevo.")
    st.stop()

# URL COMPLETA DE TU GOOGLE SHEET
SHEET_URL = "https://docs.google.com/spreadsheets/d/1qWyr5yV6KJDO_zz3w0bWuo-oT5ltdcUkNVx1KNPn9dE/edit?usp=sharing"

# --- CONEXIÓN SEGURA Y EFICIENTE A GOOGLE SHEETS (SOPORTE NUBE Y LOCAL) ---
@st.cache_resource
def obtener_libro_google_sheets():
    """Conecta una sola vez y cachea la sesión (soporta Streamlit Cloud Secrets y credenciales.json local)."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # 1. Intentar desde st.secrets (Streamlit Cloud)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        # 2. Fallback local (credenciales.json)
        elif os.path.exists("credenciales.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
        else:
            st.error("No se encontraron credenciales de Google Sheets ni en st.secrets ni en credenciales.json.")
            return None
            
        client = gspread.authorize(creds)
        return client.open_by_url(SHEET_URL)
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

def obtener_hoja(pestana):
    libro = obtener_libro_google_sheets()
    if libro:
        return libro.worksheet(pestana)
    return None

def encontrar_fila_por_id(hoja, target_id):
    """Encuentra el número de fila exacto en Google Sheets buscando en la columna ID."""
    try:
        col_ids = hoja.col_values(1)
        for idx, val in enumerate(col_ids, start=1):
            if str(val).strip() == str(target_id).strip():
                return idx
        return None
    except Exception:
        return None

@st.cache_data(ttl=120, show_spinner=False)
def cargar_datos(pestana):
    try:
        hoja = obtener_hoja(pestana)
        if not hoja:
            return pd.DataFrame()
        datos = hoja.get_all_records()
        return pd.DataFrame(datos)
    except Exception as e:
        st.error(f"Error al leer la pestaña {pestana}: {e}")
        return pd.DataFrame()

# --- OPERACIONES CRUD: SESIONES ---
def guardar_sesion(fecha, paciente, estatus, tarifa, obs):
    hoja = obtener_hoja("Sesiones")
    datos = hoja.get_all_records()
    nuevo_id = 1 if not datos else max([int(r.get('id', 0)) for r in datos if str(r.get('id', '')).isdigit()] or [0]) + 1
    hoja.append_row([nuevo_id, str(fecha), paciente, estatus, float(tarifa), str(obs or "")])
    st.cache_data.clear()

def actualizar_sesion(id_registro, fecha, paciente, estatus, tarifa, obs):
    hoja = obtener_hoja("Sesiones")
    fila = encontrar_fila_por_id(hoja, id_registro)
    if fila:
        hoja.update(values=[[id_registro, str(fecha), paciente, estatus, float(tarifa), str(obs or "")]], range_name=f"A{fila}:F{fila}")
        st.cache_data.clear()
        return True
    return False

def eliminar_sesion(id_registro):
    hoja = obtener_hoja("Sesiones")
    fila = encontrar_fila_por_id(hoja, id_registro)
    if fila:
        hoja.delete_rows(fila)
        st.cache_data.clear()
        return True
    return False

# --- OPERACIONES CRUD: PAGOS ---
def guardar_pago(num_pago, fecha, paciente, monto_ves, tasa_bcv, monto_usd, sesiones, concepto, obs):
    hoja = obtener_hoja("Pagos")
    datos = hoja.get_all_records()
    nuevo_id = 1 if not datos else max([int(r.get('id', 0)) for r in datos if str(r.get('id', '')).isdigit()] or [0]) + 1
    hoja.append_row([nuevo_id, str(num_pago), str(fecha), paciente, float(monto_ves), float(tasa_bcv), float(monto_usd), float(sesiones), str(concepto or ""), str(obs or "")])
    st.cache_data.clear()

def actualizar_pago(id_registro, num_pago, fecha, paciente, monto_ves, tasa_bcv, monto_usd, sesiones, concepto, obs):
    hoja = obtener_hoja("Pagos")
    fila = encontrar_fila_por_id(hoja, id_registro)
    if fila:
        hoja.update(values=[[id_registro, str(num_pago), str(fecha), paciente, float(monto_ves), float(tasa_bcv), float(monto_usd), float(sesiones), str(concepto or ""), str(obs or "")]], range_name=f"A{fila}:J{fila}")
        st.cache_data.clear()
        return True
    return False

def eliminar_pago(id_registro):
    hoja = obtener_hoja("Pagos")
    fila = encontrar_fila_por_id(hoja, id_registro)
    if fila:
        hoja.delete_rows(fila)
        st.cache_data.clear()
        return True
    return False

# --- OPERACIONES CRUD: FACTURAS ---
def guardar_factura(num_factura, fecha_emision, mes_servicio, tasa_bcv, num_terapias, monto_ves, obs):
    hoja = obtener_hoja("Facturas")
    datos = hoja.get_all_records()
    nuevo_id = 1 if not datos else max([int(r.get('id', 0)) for r in datos if str(r.get('id', '')).isdigit()] or [0]) + 1
    hoja.append_row([nuevo_id, str(num_factura), str(fecha_emision), str(mes_servicio), float(tasa_bcv), int(num_terapias), float(monto_ves), str(obs or "")])
    st.cache_data.clear()

def actualizar_factura(id_registro, num_factura, fecha_emision, mes_servicio, tasa_bcv, num_terapias, monto_ves, obs):
    hoja = obtener_hoja("Facturas")
    fila = encontrar_fila_por_id(hoja, id_registro)
    if fila:
        hoja.update(values=[[id_registro, str(num_factura), str(fecha_emision), str(mes_servicio), float(tasa_bcv), int(num_terapias), float(monto_ves), str(obs or "")]], range_name=f"A{fila}:H{fila}")
        st.cache_data.clear()
        return True
    return False

def eliminar_factura(id_registro):
    hoja = obtener_hoja("Facturas")
    fila = encontrar_fila_por_id(hoja, id_registro)
    if fila:
        hoja.delete_rows(fila)
        st.cache_data.clear()
        return True
    return False

# --- CONSULTA DE TASA OFICIAL BCV ---
@st.cache_data(ttl=3600, show_spinner=False)
def obtener_tasa_bcv_en_linea():
    try:
        url = "https://ve.dolarapi.com/v1/dolares/oficial"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        return float(data.get("promedio", 0.0))
    except Exception:
        return None

def formatear_fecha_ddmmyyyy(val):
    try:
        if pd.isna(val) or val == "":
            return ""
        return pd.to_datetime(val).strftime("%d/%m/%Y")
    except Exception:
        return str(val)

# --- MENÚ LATERAL ---
st.sidebar.title("🩺 Control de Terapias")
st.sidebar.caption("🟢 Base de Datos Conectada (Google Sheets)")

if st.sidebar.button("🔄 Recargar Datos", width="stretch"):
    st.cache_data.clear()
    st.rerun()

menu = st.sidebar.radio("Módulos del Sistema:", [
    "📈 Dashboard Ejecutivo",
    "📅 Registro de Asistencias",
    "💵 Pagos y Liquidación BCV",
    "🧾 Facturación Emitida",
    "📥 Descargar Respaldo Excel"
])

# Botón de cerrar sesión
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Cerrar Sesión", width="stretch"):
    st.session_state.autenticado = False
    st.rerun()

# ====================================================
# MÓDULO 1: DASHBOARD EJECUTIVO
# ====================================================
if menu == "📈 Dashboard Ejecutivo":
    st.title("📊 Panel de Control y Estado de Cuenta")
    
    df_ses = cargar_datos("Sesiones")
    df_pag = cargar_datos("Pagos")
    
    if not df_ses.empty and not df_pag.empty:
        # Total asistencias realizadas (Asistió o Inasistencia cobrable)
        total_ses = len(df_ses[df_ses["estatus"].astype(str).str.contains("Asistió|Inasistencia", case=False, na=False)])
        
        # Suma de sesiones cubiertas (las evaluaciones tienen 0.0 sesiones)
        sesiones_liquidadas = float(df_pag["sesiones_cubiertas"].sum()) if "sesiones_cubiertas" in df_pag.columns else 0.0
        total_usd = float(df_pag["monto_usd"].sum()) if "monto_usd" in df_pag.columns else 0.0
        saldo = max(0.0, total_ses - sesiones_liquidadas)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Sesiones Realizadas", f"{total_ses} terapias")
        col2.metric("Sesiones Liquidadas", f"{sesiones_liquidadas:.0f} terapias")
        col3.metric("Saldo Pendiente", f"{saldo:.0f} sesiones", delta="Al día" if saldo <= 0.1 else f"{saldo:.0f} por cobrar")
        col4.metric("Total Recaudado (USD)", f"${total_usd:,.2f}")
        
        st.markdown("---")
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.subheader("📅 Últimas Sesiones Registradas")
            df_s_view = df_ses.tail(6).copy()
            df_s_view["fecha"] = df_s_view["fecha"].apply(formatear_fecha_ddmmyyyy)
            cols_show_s = [c for c in ["fecha", "paciente", "estatus", "tarifa_usd", "observaciones"] if c in df_s_view.columns]
            st.dataframe(df_s_view[cols_show_s], width="stretch", hide_index=True)
                
        with col_b:
            st.subheader("💵 Últimos Pagos Conciliados")
            df_p_view = df_pag.tail(5).copy()
            df_p_view["fecha_pago"] = df_p_view["fecha_pago"].apply(formatear_fecha_ddmmyyyy)
            cols_show_p = [c for c in ["fecha_pago", "num_pago", "monto_ves", "tasa_bcv", "monto_usd", "sesiones_cubiertas"] if c in df_p_view.columns]
            st.dataframe(df_p_view[cols_show_p], width="stretch", hide_index=True)
    else:
        st.info("Cargando datos o no se encontraron registros...")

# ====================================================
# MÓDULO 2: REGISTRO DE ASISTENCIAS
# ====================================================
elif menu == "📅 Registro de Asistencias":
    st.title("📅 Histórico y Control de Asistencias")
    
    tab_nuevo, tab_gestionar = st.tabs(["➕ Registrar Nueva Sesión", "✏️ Modificar o Eliminar Sesión"])
    
    with tab_nuevo:
        with st.form("form_nueva_sesion", clear_on_submit=True):
            c1, c2 = st.columns(2)
            fecha = c1.date_input("Fecha de la Terapia", datetime.date.today(), format="DD/MM/YYYY")
            paciente = c2.text_input("Paciente", value="Paciente 1")
            estatus = c1.selectbox("Estatus de la Sesión", [
                "Asistió",
                "Inasistencia cobrable (Compromiso agendado)",
                "Cancelada con anticipación (No cobrable)"
            ])
            tarifa = c2.number_input("Valor de la Sesión ($)", value=25.0, step=1.0)
            observaciones = st.text_input("Observaciones / Notas")
            
            btn_guardar = st.form_submit_button("💾 Guardar Asistencia", width="stretch")
            if btn_guardar:
                monto_real = tarifa if "No cobrable" not in estatus else 0.0
                guardar_sesion(fecha, paciente, estatus, monto_real, observaciones)
                st.success(f"✅ Sesión registrada para el {fecha.strftime('%d/%m/%Y')}.")
                st.rerun()

    with tab_gestionar:
        df_all_ses = cargar_datos("Sesiones")
        
        if not df_all_ses.empty:
            df_all_ses_sorted = df_all_ses.sort_values(by="id", ascending=False)
            dict_opciones = {}
            for _, r in df_all_ses_sorted.iterrows():
                f_v = formatear_fecha_ddmmyyyy(r['fecha'])
                etiqueta = f"ID {r['id']} | Fecha: {f_v} | {r['estatus']} ({r.get('observaciones', '') or 'Sin notas'})"
                dict_opciones[etiqueta] = r['id']
                
            sel_etiqueta = st.selectbox("Seleccione la sesión a gestionar:", list(dict_opciones.keys()))
            id_sel = dict_opciones[sel_etiqueta]
            reg = df_all_ses[df_all_ses["id"] == id_sel].iloc[0]
            
            try:
                fecha_reg = pd.to_datetime(reg["fecha"]).date()
            except Exception:
                fecha_reg = datetime.date.today()
                
            with st.form("form_edicion_sesion"):
                col_e1, col_e2 = st.columns(2)
                n_fecha = col_e1.date_input("Fecha", fecha_reg, format="DD/MM/YYYY")
                n_paciente = col_e2.text_input("Paciente", value=str(reg["paciente"]))
                
                opciones_est = ["Asistió", "Inasistencia cobrable", "Cancelada con anticipación (No cobrable)"]
                idx_est = 0
                if "Inasistencia" in str(reg["estatus"]): idx_est = 1
                elif "Cancelada" in str(reg["estatus"]): idx_est = 2
                
                n_estatus = col_e1.selectbox("Estatus", opciones_est, index=idx_est)
                n_tarifa = col_e2.number_input("Tarifa ($)", value=float(reg["tarifa_usd"]))
                n_obs = st.text_input("Observaciones", value=str(reg.get("observaciones", "") or ""))
                
                c_b1, c_b2 = st.columns(2)
                btn_act = c_b1.form_submit_button("🔄 Actualizar Sesión", width="stretch")
                btn_del = c_b2.form_submit_button("🗑️ Eliminar Registro", width="stretch")
                
                if btn_act:
                    actualizar_sesion(id_sel, n_fecha, n_paciente, n_estatus, n_tarifa, n_obs)
                    st.success(f"✅ Sesión ID {id_sel} actualizada correctamente.")
                    st.rerun()
                    
                if btn_del:
                    eliminar_sesion(id_sel)
                    st.warning(f"🗑️ Sesión ID {id_sel} eliminada permanentemente.")
                    st.rerun()
        else:
            st.info("No hay sesiones registradas para gestionar.")

    st.markdown("---")
    st.markdown("### 📋 Histórico Completo de Sesiones")
    df_ver = cargar_datos("Sesiones")
    if not df_ver.empty:
        df_show = df_ver.copy()
        df_show["fecha"] = df_show["fecha"].apply(formatear_fecha_ddmmyyyy)
        st.dataframe(df_show, width="stretch", height=450, hide_index=True)

# ====================================================
# MÓDULO 3: PAGOS Y LIQUIDACIÓN BCV
# ====================================================
elif menu == "💵 Pagos y Liquidación BCV":
    st.title("💵 Pagos y Conversión Cambiaria Oficial BCV")
    
    # Resumen superior métrico de pagos
    df_p_summary = cargar_datos("Pagos")
    if not df_p_summary.empty:
        tot_pag_ves = float(df_p_summary["monto_ves"].sum()) if "monto_ves" in df_p_summary.columns else 0.0
        tot_pag_usd = float(df_p_summary["monto_usd"].sum()) if "monto_usd" in df_p_summary.columns else 0.0
        tot_ses_cub = float(df_p_summary["sesiones_cubiertas"].sum()) if "sesiones_cubiertas" in df_p_summary.columns else 0.0
        num_pagos = len(df_p_summary)
        
        cp1, cp2, cp3, cp4 = st.columns(4)
        cp1.metric("Total Recaudado (VES)", f"Bs. {tot_pag_ves:,.2f}")
        cp2.metric("Total Recaudado (USD)", f"${tot_pag_usd:,.2f}")
        cp3.metric("Terapias Amortizadas", f"{tot_ses_cub:.0f} terapias")
        cp4.metric("Pagos Recibidos", f"{num_pagos} pagos")
        st.markdown("---")
    
    if "tasa_sugerida" not in st.session_state:
        st.session_state.tasa_sugerida = 771.07

    col_btn, col_info = st.columns([1, 3])
    if col_btn.button("🔄 Consultar Tasa BCV", width="stretch"):
        tasa_api = obtener_tasa_bcv_en_linea()
        if tasa_api:
            st.session_state.tasa_sugerida = tasa_api
            st.toast(f"Tasa BCV actualizada: Bs. {tasa_api:,.2f}", icon="✅")
        else:
            st.toast("No se pudo conectar a la API del BCV. Se mantiene la tasa referencial.", icon="ℹ️")
            
    col_info.caption(f"Tasa de referencia actual: **Bs. {st.session_state.tasa_sugerida:,.2f}**")

    tab_nuevo_pago, tab_gestionar_pago = st.tabs(["➕ Registrar Nuevo Pago", "✏️ Modificar o Eliminar Pago"])

    with tab_nuevo_pago:
        with st.form("form_nuevo_pago", clear_on_submit=True):
            col1, col2 = st.columns(2)
            f_pago = col1.date_input("Fecha del Pago", datetime.date.today(), format="DD/MM/YYYY")
            pac_pago = col2.text_input("Paciente", value="Paciente 1")
            
            tipo_pago = col1.selectbox("Tipo de Pago", [
                "Pago de Terapias Regulares",
                "Evaluación Inicial / Concepto Especial (0 terapias asociadas)"
            ])
            
            m_ves = col2.number_input("Monto en Bolívares (VES)", min_value=0.0, step=1000.0, format="%.2f")
            t_bcv = col1.number_input("Tasa BCV del Día de Pago", min_value=0.01, value=float(st.session_state.tasa_sugerida), step=1.0, format="%.4f")
            
            c_unit = col2.number_input("Precio Referencial por Terapia ($)", value=25.0, step=1.0)
            n_recibo = col1.text_input("N° Referencia / Recibo", value=f"PAG-{datetime.date.today().strftime('%d%m')}")
            
            concepto_def = "Pago de terapias" if "Regulares" in tipo_pago else "Evaluación Inicial"
            c_concepto = col2.text_input("Concepto", value=concepto_def)
            c_obs = st.text_input("Observaciones (Ej: Terapias 17 al 32 o Detalle del pago)")
            
            if st.form_submit_button("🧮 Registrar y Guardar Pago", width="stretch"):
                if t_bcv > 0 and m_ves > 0:
                    usd_rec = m_ves / t_bcv
                    # Si es evaluación inicial, 0 sesiones cubiertas
                    ses_cub = 0.0 if "Evaluación" in tipo_pago else (usd_rec / c_unit)
                    guardar_pago(n_recibo, f_pago, pac_pago, m_ves, t_bcv, usd_rec, ses_cub, c_concepto, c_obs)
                    st.success(f"✅ Pago Registrado: ${usd_rec:,.2f} USD -> Amortiza {ses_cub:.2f} terapias.")
                    st.rerun()
                else:
                    st.error("Por favor ingresa un monto en Bolívares válido mayor a cero.")

    with tab_gestionar_pago:
        df_all_pagos = cargar_datos("Pagos")
        if not df_all_pagos.empty:
            df_pagos_sorted = df_all_pagos.sort_values(by="id", ascending=False)
            dict_pagos_opc = {}
            for _, r in df_pagos_sorted.iterrows():
                f_p_txt = formatear_fecha_ddmmyyyy(r['fecha_pago'])
                m_ves_txt = f"{float(r.get('monto_ves', 0)):,.2f}"
                m_usd_txt = f"{float(r.get('monto_usd', 0)):,.2f}"
                ses_txt = f"{float(r.get('sesiones_cubiertas', 0)):.0f} terapias"
                etiqueta = f"ID {r['id']} | Ref: {r.get('num_pago', 'S/N')} | {f_p_txt} | Bs. {m_ves_txt} (${m_usd_txt} USD) | Cubre: {ses_txt} | {r.get('concepto', '')}"
                dict_pagos_opc[etiqueta] = r['id']
                
            sel_pago_etiq = st.selectbox("Seleccione el pago a gestionar:", list(dict_pagos_opc.keys()))
            id_pago_sel = dict_pagos_opc[sel_pago_etiq]
            reg_pago = df_all_pagos[df_all_pagos["id"] == id_pago_sel].iloc[0]
            
            try:
                fecha_pago_reg = pd.to_datetime(reg_pago["fecha_pago"]).date()
            except Exception:
                fecha_pago_reg = datetime.date.today()
                
            with st.form("form_edicion_pago"):
                cp1, cp2 = st.columns(2)
                ep_fecha = cp1.date_input("Fecha del Pago", fecha_pago_reg, format="DD/MM/YYYY")
                ep_paciente = cp2.text_input("Paciente", value=str(reg_pago.get("paciente", "Paciente 1")))
                
                ep_m_ves = cp1.number_input("Monto en Bolívares (VES)", min_value=0.0, value=float(reg_pago.get("monto_ves", 0.0)), step=1000.0, format="%.2f")
                ep_t_bcv = cp2.number_input("Tasa BCV", min_value=0.01, value=float(reg_pago.get("tasa_bcv", 1.0)), step=1.0, format="%.4f")
                
                ep_ses_cubiertas = cp1.number_input("Sesiones / Terapias Cubiertas (Colocar 0 si fue Evaluación)", min_value=0.0, value=float(reg_pago.get("sesiones_cubiertas", 0.0)), step=1.0)
                ep_recibo = cp2.text_input("N° Referencia / Recibo", value=str(reg_pago.get("num_pago", "")))
                
                ep_concepto = cp1.text_input("Concepto", value=str(reg_pago.get("concepto", "")))
                ep_obs = cp2.text_input("Observaciones", value=str(reg_pago.get("observaciones", "") or ""))
                
                # Cálculo de USD resultante
                ep_usd_rec = (ep_m_ves / ep_t_bcv) if ep_t_bcv > 0 else float(reg_pago.get("monto_usd", 0.0))
                st.caption(f"💡 **Monto en Dólares equivalente:** ${ep_usd_rec:,.2f} USD | **Terapias amortizadas:** {ep_ses_cubiertas:.1f}")
                
                btn_col1, btn_col2 = st.columns(2)
                btn_act_pago = btn_col1.form_submit_button("🔄 Actualizar Pago", width="stretch")
                btn_del_pago = btn_col2.form_submit_button("🗑️ Eliminar Pago", width="stretch")
                
                if btn_act_pago:
                    if ep_t_bcv > 0 and ep_m_ves > 0:
                        actualizar_pago(id_pago_sel, ep_recibo, ep_fecha, ep_paciente, ep_m_ves, ep_t_bcv, ep_usd_rec, ep_ses_cubiertas, ep_concepto, ep_obs)
                        st.success(f"✅ Pago ID {id_pago_sel} actualizado correctamente.")
                        st.rerun()
                    else:
                        st.error("El monto y la tasa deben ser mayores a cero.")
                        
                if btn_del_pago:
                    eliminar_pago(id_pago_sel)
                    st.warning(f"🗑️ Pago ID {id_pago_sel} eliminado permanentemente.")
                    st.rerun()
        else:
            st.info("No hay pagos registrados para gestionar.")

    st.markdown("---")
    st.markdown("### 📋 Histórico de Pagos Recibidos")
    df_p_view = cargar_datos("Pagos")
    if not df_p_view.empty:
        df_show = df_p_view.copy()
        df_show["fecha_pago"] = df_show["fecha_pago"].apply(formatear_fecha_ddmmyyyy)
        st.dataframe(df_show, width="stretch", hide_index=True)

# ====================================================
# MÓDULO 4: FACTURACIÓN EMITIDA
# ====================================================
elif menu == "🧾 Facturación Emitida":
    st.title("🧾 Control de Facturas Emitidas")
    
    df_f_view = cargar_datos("Facturas")
    
    if not df_f_view.empty:
        tot_fact_ves = float(df_f_view["monto_ves"].sum()) if "monto_ves" in df_f_view.columns else 0.0
        tot_terapias_fact = int(df_f_view["num_terapias"].sum()) if "num_terapias" in df_f_view.columns else 0
        num_facturas = len(df_f_view)
        
        cf1, cf2, cf3 = st.columns(3)
        cf1.metric("Total Facturado (VES)", f"Bs. {tot_fact_ves:,.2f}")
        cf2.metric("Terapias Facturadas", f"{tot_terapias_fact} sesiones")
        cf3.metric("Facturas Emitidas", f"{num_facturas} facturas")
        st.markdown("---")

    tab_nueva_fac, tab_gestionar_fac = st.tabs(["➕ Registrar Nueva Factura", "✏️ Modificar o Eliminar Factura"])

    with tab_nueva_fac:
        with st.form("form_nueva_factura", clear_on_submit=True):
            f_col1, f_col2 = st.columns(2)
            n_fac_num = f_col1.text_input("N° de Factura", value=f"FAC-{datetime.date.today().strftime('%Y-%m')}")
            n_fac_fecha = f_col2.date_input("Fecha de Emisión", datetime.date.today(), format="DD/MM/YYYY")
            
            meses_nombres = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
            mes_defecto = f"{meses_nombres[datetime.date.today().month - 1]} {datetime.date.today().year}"
            n_fac_mes = f_col1.text_input("Mes del Servicio", value=mes_defecto)
            
            tasa_ref = float(st.session_state.get("tasa_sugerida", 771.07))
            n_fac_tasa = f_col2.number_input("Tasa BCV Facturada", min_value=0.01, value=tasa_ref, step=1.0, format="%.4f")
            
            n_fac_terapias = f_col1.number_input("N° de Terapias Facturadas", min_value=1, value=10, step=1)
            tarifa_base_usd = 25.0
            monto_sugerido_ves = float(n_fac_terapias * tarifa_base_usd * n_fac_tasa)
            
            n_fac_monto_ves = f_col2.number_input("Monto Facturado en Bolívares (VES)", min_value=0.0, value=monto_sugerido_ves, step=1000.0, format="%.2f")
            n_fac_obs = st.text_input("Observaciones / Descripción", value=f"Factura {mes_defecto.capitalize()}")
            
            if st.form_submit_button("💾 Guardar Factura Emitida", width="stretch"):
                if n_fac_monto_ves > 0 and n_fac_num.strip():
                    guardar_factura(n_fac_num, n_fac_fecha, n_fac_mes, n_fac_tasa, n_fac_terapias, n_fac_monto_ves, n_fac_obs)
                    st.success(f"✅ Factura {n_fac_num} registrada exitosamente.")
                    st.rerun()
                else:
                    st.error("Por favor completa el número de factura y un monto válido.")

    with tab_gestionar_fac:
        if not df_f_view.empty:
            df_fac_sorted = df_f_view.sort_values(by="id", ascending=False)
            dict_fac_opc = {}
            for _, r in df_fac_sorted.iterrows():
                f_em_txt = formatear_fecha_ddmmyyyy(r['fecha_emision'])
                m_v_txt = f"{float(r.get('monto_ves', 0)):,.2f}"
                etiqueta = f"ID {r['id']} | Factura: {r.get('num_factura', 'S/N')} | {f_em_txt} | {r.get('mes_servicio', '')} | Bs. {m_v_txt}"
                dict_fac_opc[etiqueta] = r['id']
                
            sel_fac_etiq = st.selectbox("Seleccione la factura a gestionar:", list(dict_fac_opc.keys()))
            id_fac_sel = dict_fac_opc[sel_fac_etiq]
            reg_fac = df_f_view[df_f_view["id"] == id_fac_sel].iloc[0]
            
            try:
                fecha_fac_reg = pd.to_datetime(reg_fac["fecha_emision"]).date()
            except Exception:
                fecha_fac_reg = datetime.date.today()
                
            with st.form("form_edicion_factura"):
                ef_col1, ef_col2 = st.columns(2)
                ef_num = ef_col1.text_input("N° de Factura", value=str(reg_fac.get("num_factura", "")))
                ef_fecha = ef_col2.date_input("Fecha de Emisión", fecha_fac_reg, format="DD/MM/YYYY")
                
                ef_mes = ef_col1.text_input("Mes del Servicio", value=str(reg_fac.get("mes_servicio", "")))
                ef_tasa = ef_col2.number_input("Tasa BCV", min_value=0.01, value=float(reg_fac.get("tasa_bcv", 1.0)), step=1.0, format="%.4f")
                
                ef_terapias = ef_col1.number_input("N° de Terapias", min_value=1, value=int(reg_fac.get("num_terapias", 1)), step=1)
                ef_monto_ves = ef_col2.number_input("Monto Facturado (VES)", min_value=0.0, value=float(reg_fac.get("monto_ves", 0.0)), step=1000.0, format="%.2f")
                
                ef_obs = st.text_input("Observaciones", value=str(reg_fac.get("observaciones", "") or ""))
                
                btn_f_col1, btn_f_col2 = st.columns(2)
                btn_act_fac = btn_f_col1.form_submit_button("🔄 Actualizar Factura", width="stretch")
                btn_del_fac = btn_f_col2.form_submit_button("🗑️ Eliminar Factura", width="stretch")
                
                if btn_act_fac:
                    actualizar_factura(id_fac_sel, ef_num, ef_fecha, ef_mes, ef_tasa, ef_terapias, ef_monto_ves, ef_obs)
                    st.success(f"✅ Factura ID {id_fac_sel} actualizada exitosamente.")
                    st.rerun()
                    
                if btn_del_fac:
                    eliminar_factura(id_fac_sel)
                    st.warning(f"🗑️ Factura ID {id_fac_sel} eliminada permanentemente.")
                    st.rerun()
        else:
            st.info("No hay facturas registradas para gestionar.")

    st.markdown("---")
    st.markdown("### 📋 Histórico Completo de Facturas Emitidas")
    df_f_show = cargar_datos("Facturas")
    if not df_f_show.empty:
        df_show_fac = df_f_show.copy()
        if "fecha_emision" in df_show_fac.columns:
            df_show_fac["fecha_emision"] = df_show_fac["fecha_emision"].apply(formatear_fecha_ddmmyyyy)
        st.dataframe(df_show_fac, width="stretch", height=400, hide_index=True)

# ====================================================
# MÓDULO 5: CONCILIACIÓN Y RESPALDO
# ====================================================
elif menu == "📥 Descargar Respaldo Excel":
    st.title("📥 Descargar Base de Datos Completa")
    st.caption("Genera una copia de seguridad en formato Excel con todas las pestañas actualizadas de Google Sheets.")
    
    df_s = cargar_datos("Sesiones")
    df_f = cargar_datos("Facturas")
    df_p = cargar_datos("Pagos")
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_s.to_excel(writer, sheet_name='Sesiones', index=False)
        df_f.to_excel(writer, sheet_name='Facturas', index=False)
        df_p.to_excel(writer, sheet_name='Pagos', index=False)
        
    st.download_button(
        label="📥 Descargar Base de Datos Completa (.xlsx)",
        data=output.getvalue(),
        file_name=f"Control_Terapias_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch"
    )
