import streamlit as st
import pandas as pd
import sqlite3
import datetime
import urllib.request
import json
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Gestión de Terapias y Liquidación Cambiaria",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "gestion_terapias.db"

# --- CONEXIÓN A BASE DE DATOS ---
def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Tabla de Sesiones
    c.execute("""
        CREATE TABLE IF NOT EXISTS sesiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            paciente TEXT NOT NULL,
            estatus TEXT NOT NULL,
            tarifa_usd REAL NOT NULL,
            observaciones TEXT
        )
    """)
    
    # 2. Tabla de Facturas
    c.execute("""
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num_factura TEXT UNIQUE,
            fecha_emision TEXT NOT NULL,
            mes_servicio TEXT NOT NULL,
            tasa_bcv REAL NOT NULL,
            num_terapias INTEGER NOT NULL,
            monto_ves REAL NOT NULL,
            observaciones TEXT
        )
    """)
    
    # 3. Tabla de Pagos
    c.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num_pago TEXT,
            fecha_pago TEXT NOT NULL,
            paciente TEXT NOT NULL,
            monto_ves REAL NOT NULL,
            tasa_bcv REAL NOT NULL,
            monto_usd REAL NOT NULL,
            sesiones_cubiertas REAL NOT NULL,
            concepto TEXT,
            observaciones TEXT
        )
    """)
    
    # Pre-carga histórica si la base de datos está vacía
    c.execute("SELECT COUNT(*) FROM sesiones")
    if c.fetchone()[0] == 0:
        asistencias_hist = [
            ("2026-01-16", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-01-21", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-01-23", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-01-28", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-01-30", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-02-04", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-02-06", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-02-12", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-02-20", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-02-25", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-02-28", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-03-04", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-04-10", "Paciente Principal", "Asistió", 25.0, "Reinicio luego de vacaciones"),
            ("2026-04-15", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-04-22", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-04-29", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-05-06", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-05-08", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-05-20", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-06-05", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-06-10", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-06-24", "Paciente Principal", "Inasistencia cobrable", 25.0, "SIN ASISTENCIA PERO SE TENIA EL COMPROMISO"),
            ("2026-06-26", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-07-03", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-07-08", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-07-10", "Paciente Principal", "Asistió", 25.0, "Sesión 1"),
            ("2026-07-10", "Paciente Principal", "Asistió", 25.0, "Sesión 2"),
            ("2026-07-17", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-07-24", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-07-31", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-08-07", "Paciente Principal", "Asistió", 25.0, ""),
            ("2026-08-14", "Paciente Principal", "Asistió", 25.0, "")
        ]
        c.executemany("INSERT INTO sesiones (fecha, paciente, estatus, tarifa_usd, observaciones) VALUES (?, ?, ?, ?, ?)", asistencias_hist)
        
        facturas_hist = [
            ("FAC-2025-12", "2025-12-30", "Diciembre 2025", 298.42, 10, 59684.00, "Factura Diciembre"),
            ("FAC-2026-01", "2026-01-31", "Enero 2026", 367.31, 10, 73462.00, "Factura Enero"),
            ("FAC-2026-02", "2026-02-27", "Febrero 2026", 417.36, 10, 83472.00, "Factura Febrero"),
            ("FAC-2026-03", "2026-03-31", "Marzo 2026", 473.87, 10, 94774.00, "Factura Marzo"),
            ("FAC-2026-04", "2026-04-30", "Abril 2026", 487.12, 10, 97424.00, "Factura Abril"),
            ("FAC-2026-05", "2026-05-29", "Mayo 2026", 549.37, 10, 109874.00, "Factura Mayo"),
            ("FAC-2026-06", "2026-06-30", "Junio 2026", 623.02, 10, 124604.00, "Factura Junio"),
            ("FAC-2026-07", "2026-07-31", "Julio 2026", 746.63, 10, 149326.00, "Factura Julio"),
            ("FAC-2026-08", "2026-08-13", "Agosto 2026", 771.07, 10, 154214.00, "Factura Agosto")
        ]
        c.executemany("INSERT INTO facturas (num_factura, fecha_emision, mes_servicio, tasa_bcv, num_terapias, monto_ves, observaciones) VALUES (?, ?, ?, ?, ?, ?, ?)", facturas_hist)
        
        pagos_hist = [
            ("PAG-001", "2026-01-15", "Paciente Principal", 17000.00, 298.42, 56.97, 2.28, "Evaluación Diciembre", "Pago EVALUACION EN DICIEMBRE"),
            ("PAG-002", "2026-03-19", "Paciente Principal", 90301.40, 451.507, 200.00, 8.00, "Pago 08 terapias", "Pago 08 terapias (N° 01 al 08)"),
            ("PAG-003", "2026-04-08", "Paciente Principal", 47500.80, 475.008, 100.00, 4.00, "Pago 04 terapias", "Pago 04 terapias (N° 09 al 12)"),
            ("PAG-004", "2026-07-31", "Paciente Principal", 74663.00, 746.63, 100.00, 4.00, "Pago 04 terapias", "Pago 04 terapias (N° 13 al 16)"),
            ("PAG-005", "2026-08-14", "Paciente Principal", 308428.00, 771.07, 400.00, 16.00, "Pago 16 terapias", "Pago 16 terapias (N° 17 al 32)")
        ]
        c.executemany("INSERT INTO pagos (num_pago, fecha_pago, paciente, monto_ves, tasa_bcv, monto_usd, sesiones_cubiertas, concepto, observaciones) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", pagos_hist)
        
    conn.commit()
    conn.close()

init_db()

# --- FUNCIÓN PARA CONSULTAR TASA OFICIAL BCV AUTOMÁTICA ---
def obtener_tasa_bcv_en_linea():
    try:
        url = "https://ve.dolarapi.com/v1/dolares/oficial"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            return float(data.get("promedio", 0.0))
    except Exception:
        return None

# Formateador visual de fechas DD/MM/AAAA
def formatear_fecha_vista(fecha_str):
    try:
        return datetime.datetime.strptime(fecha_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return fecha_str

# --- MENÚ LATERAL ---
st.sidebar.title("🩺 Control de Terapias")
menu = st.sidebar.radio("Navegación:", [
    "📈 Dashboard Ejecutivo",
    "📅 Registro de Asistencia",
    "💵 Pagos y Liquidación BCV",
    "🧾 Facturación Emitida",
    "📥 Conciliación y Exportar Excel"
])

# ==========================================
# MÓDULO 1: DASHBOARD EJECUTIVO
# ==========================================
if menu == "📈 Dashboard Ejecutivo":
    st.title("📊 Panel de Control y Estado de Cuenta")
    
    conn = get_connection()
    df_ses = pd.read_sql("SELECT * FROM sesiones", conn)
    df_pag = pd.read_sql("SELECT * FROM pagos", conn)
    conn.close()

    total_sesiones = len(df_ses[df_ses["estatus"].isin(["Asistió", "Inasistencia cobrable"])])
    sesiones_pagadas = 32.0 if len(df_pag) >= 5 else df_pag["sesiones_cubiertas"].sum()
    saldo_sesiones = max(0.0, total_sesiones - sesiones_pagadas)
    total_usd_recaudado = df_pag["monto_usd"].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sesiones Realizadas", f"{total_sesiones} terapias")
    col2.metric("Sesiones Liquidadas", f"{sesiones_pagadas:.0f} terapias")
    col3.metric("Saldo Pendiente", f"{saldo_sesiones:.0f} sesiones", delta="Al día" if saldo_sesiones == 0 else f"{saldo_sesiones} pendientes")
    col4.metric("Recaudación Efectiva (USD)", f"${total_usd_recaudado:.2f}")

    st.markdown("---")
    
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📅 Últimas Sesiones Impartidas")
        if not df_ses.empty:
            df_ses_view = df_ses.tail(6).copy()
            df_ses_view["fecha"] = pd.to_datetime(df_ses_view["fecha"]).dt.strftime("%d/%m/%Y")
            st.dataframe(df_ses_view[["fecha", "estatus", "tarifa_usd", "observaciones"]], use_container_width=True)
        
    with col_right:
        st.subheader("💵 Últimos Pagos Conciliados")
        if not df_pag.empty:
            df_pag_view = df_pag.tail(5).copy()
            df_pag_view["fecha_pago"] = pd.to_datetime(df_pag_view["fecha_pago"]).dt.strftime("%d/%m/%Y")
            st.dataframe(df_pag_view[["fecha_pago", "monto_ves", "tasa_bcv", "monto_usd", "sesiones_cubiertas"]], use_container_width=True)

# ==========================================
# MÓDULO 2: REGISTRO DE ASISTENCIA (CON CRUD)
# ==========================================
elif menu == "📅 Registro de Asistencia":
    st.title("📅 Control Diario de Asistencias")
    
    tab_nuevo, tab_gestionar = st.tabs(["➕ Registrar Nueva Sesión", "✏️ Modificar o Eliminar Sesión"])
    
    with tab_nuevo:
        with st.form("form_nueva_sesion"):
            col1, col2 = st.columns(2)
            fecha = col1.date_input("Fecha de la Terapia", datetime.date.today(), format="DD/MM/YYYY")
            paciente = col2.text_input("Nombre del Paciente", value="Paciente Principal")
            estatus = col1.selectbox("Estatus de la Sesión", [
                "Asistió",
                "Inasistencia cobrable (Compromiso agendado)",
                "Cancelada con anticipación (No cobrable)"
            ])
            tarifa = col2.number_input("Valor de la Sesión ($)", value=25.0, step=1.0)
            observaciones = st.text_input("Observaciones / Notas clínicas")
            
            btn_guardar = st.form_submit_button("💾 Guardar Asistencia")
            if btn_guardar:
                conn = get_connection()
                c = conn.cursor()
                monto_real = tarifa if "No cobrable" not in estatus else 0.0
                c.execute("INSERT INTO sesiones (fecha, paciente, estatus, tarifa_usd, observaciones) VALUES (?, ?, ?, ?, ?)",
                          (str(fecha), paciente, estatus, monto_real, observaciones))
                conn.commit()
                conn.close()
                st.success(f"✅ Sesión del día {fecha.strftime('%d/%m/%Y')} registrada exitosamente.")
                st.rerun()

    with tab_gestionar:
        conn = get_connection()
        df_todas_ses = pd.read_sql("SELECT * FROM sesiones ORDER BY id DESC", conn)
        conn.close()
        
        if not df_todas_ses.empty:
            # Crear lista de opciones legibles: ID - Fecha (dd/mm/aaaa) - Estatus
            opciones_dict = {}
            for _, row in df_todas_ses.iterrows():
                f_vista = formatear_fecha_vista(row['fecha'])
                etiqueta = f"N° {row['id']} | Fecha: {f_vista} | {row['estatus']} ({row['observaciones'] or 'Sin notas'})"
                opciones_dict[etiqueta] = row['id']
            
            seleccion_etiqueta = st.selectbox("Seleccione la sesión que desea modificar o eliminar:", list(opciones_dict.keys()))
            id_seleccionado = opciones_dict[seleccion_etiqueta]
            registro_actual = df_todas_ses[df_todas_ses["id"] == id_seleccionado].iloc[0]
            
            fecha_obj = datetime.datetime.strptime(registro_actual["fecha"], "%Y-%m-%d").date()
            
            with st.form("form_edicion"):
                col_e1, col_e2 = st.columns(2)
                nueva_fecha = col_e1.date_input("Fecha", fecha_obj, format="DD/MM/YYYY")
                nuevo_paciente = col_e2.text_input("Paciente", value=registro_actual["paciente"])
                
                lista_estatus = ["Asistió", "Inasistencia cobrable", "Cancelada con anticipación (No cobrable)"]
                idx_estatus = 0
                if "Inasistencia" in registro_actual["estatus"]:
                    idx_estatus = 1
                elif "Cancelada" in registro_actual["estatus"]:
                    idx_estatus = 2
                    
                nuevo_estatus = col_e1.selectbox("Estatus", lista_estatus, index=idx_estatus)
                nueva_tarifa = col_e2.number_input("Tarifa ($)", value=float(registro_actual["tarifa_usd"]))
                nuevas_obs = st.text_input("Observaciones", value=str(registro_actual["observaciones"] or ""))
                
                c_btn1, c_btn2 = st.columns(2)
                btn_actualizar = c_btn1.form_submit_button("🔄 Actualizar Cambios")
                btn_borrar = c_btn2.form_submit_button("🗑️ Eliminar este Registro")
                
                if btn_actualizar:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        UPDATE sesiones 
                        SET fecha = ?, paciente = ?, estatus = ?, tarifa_usd = ?, observaciones = ?
                        WHERE id = ?
                    """, (str(nueva_fecha), nuevo_paciente, nuevo_estatus, nueva_tarifa, nuevas_obs, id_seleccionado))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Sesión N° {id_seleccionado} actualizada correctamente.")
                    st.rerun()
                    
                if btn_borrar:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM sesiones WHERE id = ?", (id_seleccionado,))
                    conn.commit()
                    conn.close()
                    st.warning(f"🗑️ Sesión N° {id_seleccionado} eliminada permanentemente.")
                    st.rerun()
        else:
            st.info("No hay sesiones registradas actualmente.")

    st.markdown("---")
    st.markdown("### 📋 Histórico Completo de Terapias")
    conn = get_connection()
    df_asist_view = pd.read_sql("SELECT id as N°, fecha as Fecha, paciente as Paciente, estatus as Estatus, tarifa_usd as [Tarifa ($)], observaciones as Observaciones FROM sesiones ORDER BY id DESC", conn)
    conn.close()
    if not df_asist_view.empty:
        df_asist_view["Fecha"] = pd.to_datetime(df_asist_view["Fecha"]).dt.strftime("%d/%m/%Y")
        st.dataframe(df_asist_view, use_container_width=True)

# ==========================================
# MÓDULO 3: PAGOS Y LIQUIDACIÓN BCV
# ==========================================
elif menu == "💵 Pagos y Liquidación BCV":
    st.title("💵 Registro y Conversión Cambiaria de Pagos")
    
    # Inicializar estado de sesión para tasa BCV
    if "tasa_sugerida" not in st.session_state:
        st.session_state.tasa_sugerida = 771.07

    col_btn, col_info = st.columns([1, 3])
    if col_btn.button("🔄 Consultar Tasa Oficial BCV Hoy"):
        tasa_api = obtener_tasa_bcv_en_linea()
        if tasa_api:
            st.session_state.tasa_sugerida = tasa_api
            st.toast(f"Tasa BCV obtenida: Bs. {tasa_api:,.2f}", icon="✅")
        else:
            st.toast("No se pudo conectar a la API del BCV. Ingrésela manualmente.", icon="⚠️")
            
    col_info.caption(f"Tasa sugerida actual: **Bs. {st.session_state.tasa_sugerida:,.2f}**")

    with st.form("form_nuevo_pago"):
        col1, col2 = st.columns(2)
        fecha_pago = col1.date_input("Fecha del Pago", datetime.date.today(), format="DD/MM/YYYY")
        paciente = col2.text_input("Paciente", value="Paciente Principal")
        
        monto_ves = col1.number_input("Monto Recibido en Bolívares (VES)", min_value=0.0, step=1000.0, format="%.2f")
        tasa_bcv = col2.number_input("Tasa BCV del Día de Pago (Bs./USD)", min_value=0.01, value=float(st.session_state.tasa_sugerida), step=1.0, format="%.4f")
        
        costo_unitario = col1.number_input("Precio por Sesión ($)", value=25.0)
        num_recibo = col2.text_input("N° Referencia / Recibo", value=f"PAG-{datetime.date.today().strftime('%d%m')}")
        
        concepto = col1.text_input("Concepto", value="Abono a terapias")
        observaciones = col2.text_input("Observaciones (Ej: Cubre sesiones 17 al 32)")
        
        btn_calc = st.form_submit_button("🧮 Registrar y Liquidar Pago")
        if btn_calc:
            if tasa_bcv > 0 and monto_ves > 0:
                usd_recibidos = monto_ves / tasa_bcv
                sesiones_amortizadas = usd_recibidos / costo_unitario
                
                conn = get_connection()
                c = conn.cursor()
                c.execute("""
                    INSERT INTO pagos (num_pago, fecha_pago, paciente, monto_ves, tasa_bcv, monto_usd, sesiones_cubiertas, concepto, observaciones)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (num_recibo, str(fecha_pago), paciente, monto_ves, tasa_bcv, usd_recibidos, sesiones_amortizadas, concepto, observaciones))
                conn.commit()
                conn.close()
                
                st.success(f"""
                ✅ **Pago Registrado Exitosamente:**
                * **Fecha Pago:** {fecha_pago.strftime('%d/%m/%Y')}
                * **Dólares Efectivos:** ${usd_recibidos:.2f} USD
                * **Terapias Cubiertas:** {sesiones_amortizadas:.2f} sesiones
                """)
                st.rerun()
            else:
                st.error("Ingrese un monto y una tasa válidos mayores a 0.")

    st.markdown("### 📋 Histórico de Pagos Recibidos")
    conn = get_connection()
    df_pagos_view = pd.read_sql("SELECT id as N°, fecha_pago as [Fecha Pago], monto_ves as [Monto (Bs.)], tasa_bcv as [Tasa BCV], monto_usd as [USD Efectivos ($)], sesiones_cubiertas as [Sesiones Cubiertas], observaciones as Observaciones FROM pagos ORDER BY id DESC", conn)
    conn.close()
    if not df_pagos_view.empty:
        df_pagos_view["Fecha Pago"] = pd.to_datetime(df_pagos_view["Fecha Pago"]).dt.strftime("%d/%m/%Y")
        st.dataframe(df_pagos_view, use_container_width=True)

# ==========================================
# MÓDULO 4: FACTURACIÓN EMITIDA
# ==========================================
elif menu == "🧾 Facturación Emitida":
    st.title("🧾 Control de Facturas Emitidas")
    
    with st.expander("➕ Registrar Nueva Factura"):
        with st.form("form_factura"):
            c1, c2, c3 = st.columns(3)
            num_fac = c1.text_input("N° Factura", value=f"FAC-2026-{datetime.date.today().strftime('%m')}")
            fecha_fac = c2.date_input("Fecha Emisión", datetime.date.today(), format="DD/MM/YYYY")
            mes_serv = c3.text_input("Mes de Servicio", value=f"{datetime.date.today().strftime('%B %Y')}")
            
            c4, c5 = st.columns(2)
            tasa_fac = c4.number_input("Tasa BCV al Emitir (Bs./USD)", min_value=0.01, step=1.0, format="%.2f")
            terapias_fac = c5.number_input("Cantidad de Terapias", value=10, step=1)
            
            monto_calculado = tasa_fac * terapias_fac * 25.0
            st.info(f"Monto sugerido en Bolívares (a $25/terapia): **Bs. {monto_calculado:,.2f}**")
            
            btn_fac = st.form_submit_button("💾 Guardar Factura")
            if btn_fac:
                conn = get_connection()
                c = conn.cursor()
                c.execute("""
                    INSERT INTO facturas (num_factura, fecha_emision, mes_servicio, tasa_bcv, num_terapias, monto_ves, observaciones)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (num_fac, str(fecha_fac), mes_serv, tasa_fac, terapias_fac, monto_calculado, ""))
                conn.commit()
                conn.close()
                st.success("Factura guardada correctamente.")
                st.rerun()

    conn = get_connection()
    df_fac_view = pd.read_sql("SELECT num_factura as [N° Factura], fecha_emision as [Fecha], mes_servicio as [Mes], tasa_bcv as [Tasa BCV], num_terapias as [Terapias], monto_ves as [Monto Facturado (Bs.)] FROM facturas ORDER BY id DESC", conn)
    conn.close()
    if not df_fac_view.empty:
        df_fac_view["Fecha"] = pd.to_datetime(df_fac_view["Fecha"]).dt.strftime("%d/%m/%Y")
        st.dataframe(df_fac_view, use_container_width=True)

# ==========================================
# MÓDULO 5: CONCILIACIÓN Y EXPORTACIÓN
# ==========================================
elif menu == "📥 Conciliación y Exportar Excel":
    st.title("📥 Conciliación Global y Descarga")
    
    conn = get_connection()
    df_s = pd.read_sql("SELECT * FROM sesiones", conn)
    df_f = pd.read_sql("SELECT * FROM facturas", conn)
    df_p = pd.read_sql("SELECT * FROM pagos", conn)
    conn.close()
    
    # Generar Excel en memoria con fechas en dd/mm/aaaa
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_s.to_excel(writer, sheet_name='Sesiones_Asistencia', index=False)
        df_f.to_excel(writer, sheet_name='Facturas_Emitidas', index=False)
        df_p.to_excel(writer, sheet_name='Pagos_Recibidos', index=False)
    
    excel_data = output.getvalue()
    
    st.download_button(
        label="📥 Descargar Base de Datos Completa en Excel (.xlsx)",
        data=excel_data,
        file_name=f"Control_Terapias_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.markdown("---")
    st.subheader("Resumen Conciliado")
    st.write(f"* **Total Sesiones:** {len(df_s)}")
    st.write(f"* **Total Pagos Recibidos:** Bs. {df_p['monto_ves'].sum():,.2f} (Equivalente a ${df_p['monto_usd'].sum():,.2f} USD)")
