import json
import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st

@st.cache_resource
def init_firebase():
    # Evita re-inicializar si ya está
    if firebase_admin._apps:
        return firestore.client()

    firebase_secret = st.secrets.get("firebase", {}).get("service_account_key")
    if firebase_secret is None:
        st.error("❌ No se encontró 'firebase.service_account_key' en Streamlit Secrets. Añádelo en Settings -> Secrets.")
        st.stop()
        return None

    # Acepta dict (table) o string JSON
    if isinstance(firebase_secret, str):
        try:
            cred_json = json.loads(firebase_secret)
        except Exception:
            st.error("❌ El formato de firebase.service_account_key no parece JSON. Usa un table en Secrets (recomendado).")
            st.stop()
            return None
    else:
        cred_json = firebase_secret

    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)
    return firestore.client()
    ========================================================
# CONFIGURACIÓN DE LA APP (Streamlit)
# =========================================================================

st.set_page_config(
    page_title="App Cierre de Caja",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Paleta de colores y CSS
COLOR_TEXTO_PRINCIPAL = "#1A237E"  # Azul Marino Oscuro
COLOR_PRIMARIO_ACCENT = "#00897B"  # Teal
COLOR_FONDO_SECUNDARIO = "#F5F5F5"
COLOR_PESTANA_INACTIVA = "rgba(26, 35, 126, 0.5)"

st.markdown(f"""
    <style>
    .stTabs [data-testid="stComponent"]:first-child {{
        font-size: 30px !important;
        font-weight: bold;
    }}
    .stTabs [aria-selected='true'] {{
        color: {COLOR_TEXTO_PRINCIPAL} !important;
        border-bottom: 4px solid {COLOR_PRIMARIO_ACCENT} !important;
    }}
    .stTabs [aria-selected='false'] {{
        color: {COLOR_PESTANA_INACTIVA} !important;
    }}
    .stButton>button, .css-1cpxqw2, .st-bh, .st-bf, .st-bi, .st-bk {{
        background-color: {COLOR_PRIMARIO_ACCENT} !important;
        border-color: {COLOR_PRIMARIO_ACCENT} !important;
        color: white !important;
    }}
    .stApp > header, .stSidebar, .css-1y46j9p, .css-1cpxqw2, .stButton>button:hover {{
        background-color: {COLOR_FONDO_SECUNDARIO} !important;
    }}
    div, h1, h2, h3, h4, h5, h6, label {{
        color: {COLOR_TEXTO_PRINCIPAL};
    }}
    </style>
    """, unsafe_allow_html=True)

# Constantes
COLLECTION_NAME_USERS = "usuarios"
COLLECTION_NAME_CIERRES = "cierres_caja"
COLLECTION_NAME_TASAS = "tasas_cambio"
COLLECTION_NAME_TRANSACCIONES_CANCHAS = "transacciones_canchas"
CASH_DENOMINATIONS_BS = [10, 20, 50, 100, 200, 500]
CASH_DENOMINATIONS_USD = [1, 5, 10, 20, 50, 100]
AVAILABLE_CAJAS = ["Canchas Padel (Incluye Tienda)", "Cafe Bar"]
TIPOS_TRANSACCION_CANCHA = ["Alquiler Normal", "Crédito (por Suspensión)", "Cobro de Crédito Pendiente", "Pago Adelantado"]
AVAILABLE_CANCHAS = ["Cancha 1", "Cancha 2", "Cancha 3", "Cancha 4"]
METODOS_PAGO_CANCHAS = ["Punto de Venta/Débito (Bs)", "Pago Móvil (Bs)", "Efectivo (USD)", "Zelle (USD)", "Venmo (USD)"]
LOGO_PATH = 'logo.png'

# Inicializar Firebase y obtener cliente global
db = init_firebase()

# =========================================================================
# FUNCIONES DE AUTENTICACIÓN
# =========================================================================

def check_login(username, pin):
    """Verifica credenciales y carga el perfil del usuario."""
    if db is None:
        st.error("Error de conexión a la Base de Datos. No se puede iniciar sesión.")
        return False

    try:
        users_ref = db.collection(COLLECTION_NAME_USERS)
        query = users_ref.where('username', '==', username).where('pin', '==', pin).where('activo', '==', True).limit(1).get()

        if query:
            user_doc = query[0]
            user_data = user_doc.to_dict()
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.user_role = user_data.get('rol', 'cajera')
            st.session_state.user_name = user_data.get('nombre', '')
            st.session_state.user_apellido = user_data.get('apellido', '')
            st.success(f"Bienvenido/a, {st.session_state.user_name} ({st.session_state.user_role.capitalize()})")
            t.sleep(1)
            st.rerun()
            return True
        else:
            st.error("Credenciales inválidas o usuario inactivo.")
            return False
    except Exception as e:
        st.error(f"Error en la autenticación: {e}")
        return False

def logout():
    """Cierra la sesión del usuario y limpia session_state."""
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.session_state.user_apellido = None
    st.session_state.edit_user_doc_id = None
    st.session_state.edit_user_data = {}
    st.info("Sesión cerrada.")
    t.sleep(0.5)
    st.rerun()

# =========================================================================
# LÓGICA DE NEGOCIO (FUNCIONES DE TASAS, TRANSACCIONES, CIERRES Y REPORTES)
# =========================================================================

def get_latest_tasa(db):
    """Obtiene la última tasa de cambio registrada."""
    if db is None: return None
    try:
        tasa_ref = db.collection(COLLECTION_NAME_TASAS).order_by('fecha', direction=firestore.Query.DESCENDING).limit(1).get()
        if tasa_ref:
            return tasa_ref[0].to_dict()
        return None
    except Exception:
        return None

def save_tasa(db, tasa_bs, user):
    """Guarda una nueva tasa de cambio."""
    if db is None: return False, "DB no conectada."
    try:
        if tasa_bs <= 0:
            return False, "La tasa debe ser un valor positivo."

        data = {
            "fecha": datetime.now(),
            "tasa_bs": float(tasa_bs),
            "registrado_por": user
        }
        db.collection(COLLECTION_NAME_TASAS).add(data)
        return True, "Tasa de cambio registrada exitosamente."
    except Exception as e:
        return False, f"Error al guardar la tasa: {e}"

def save_cancha_transaction(db, data):
    """Guarda una transacción relacionada con canchas (alquiler, crédito, adelanto)."""
    if db is None: return False, "DB no conectada."
    try:
        data['fecha_registro'] = datetime.now()
        data['registrado_por'] = st.session_state.get('username')
        db.collection(COLLECTION_NAME_TRANSACCIONES_CANCHAS).add(data)
        return True, f"Transacción de {data.get('tipo_transaccion')} registrada exitosamente."
    except Exception as e:
        return False, f"Error al guardar la transacción de cancha: {e}"

def get_summary_cancha_transactions(db, start_time, end_time):
    """
    Calcula cobros de créditos y pagos adelantados (USD) en el rango dado.
    """
    if db is None: return {'cobros_creditos_usd': 0.0, 'pagos_adelantados_usd': 0.0}

    try:
        transactions_ref = db.collection(COLLECTION_NAME_TRANSACCIONES_CANCHAS) if False else db.collection(COLLECTION_NAME_TRANSACCIONES_CANCHAS)
        query = transactions_ref.where('fecha_registro', '>=', start_time).where('fecha_registro', '<=', end_time).stream()

        cobros_creditos_usd = 0.0
        pagos_adelantados_usd = 0.0

        for doc in query:
            data = doc.to_dict()
            monto_usd = data.get('monto_usd', 0.0)
            tipo = data.get('tipo_transaccion')

            if tipo == "Cobro de Crédito Pendiente":
                cobros_creditos_usd += monto_usd
            elif tipo in ["Crédito (por Suspensión)", "Pago Adelantado"]:
                pagos_adelantados_usd += monto_usd

        return {
            'cobros_creditos_usd': cobros_creditos_usd,
            'pagos_adelantados_usd': pagos_adelantados_usd
        }

    except Exception as e:
        st.error(f"Error al cargar el resumen de transacciones de cancha: {e}")
        return {'cobros_creditos_usd': 0.0, 'pagos_adelantados_usd': 0.0}

def load_cancha_transactions(db, start_date, end_date):
    """Carga todas las transacciones de canchas en un rango de fechas."""
    if db is None: return pd.DataFrame()
    try:
        end_datetime = datetime.combine(end_date, time.max)
        start_datetime = datetime.combine(start_date, time.min)

        transactions_ref = db.collection(COLLECTION_NAME_TRANSACCIONES_CANCHAS)
        query = transactions_ref.where('fecha_registro', '>=', start_datetime).where('fecha_registro', '<=', end_datetime)
        query = query.order_by('fecha_registro', direction=firestore.Query.DESCENDING).stream()

        data_list = []
        for doc in query:
            data = doc.to_dict()
            fecha = data.get('fecha_registro').strftime('%Y-%m-%d %H:%M') if data.get('fecha_registro') else 'N/A'
            monto_usd = data.get('monto_usd', 0.0)

            data_list.append({
                "Fecha/Hora": fecha,
                "Tipo": data.get('tipo_transaccion', 'N/A'),
                "Cancha": data.get('cancha_referencia', 'N/A'),
                "Cliente": data.get('cliente_nombre', 'N/A'),
                "Método Pago": data.get('metodo_pago', 'N/A'),
                "Monto (USD)": f"$ {monto_usd:,.2f}",
                "Monto_raw": monto_usd,
                "Registrado Por": data.get('registrado_por', 'N/A'),
                "Nota": data.get('nota', ''),
            })

        df = pd.DataFrame(data_list)
        return df

    except Exception as e:
        st.error(f"Error al cargar el reporte de canchas: {e}")
        return pd.DataFrame()

def calculate_cierre_totals(cierre_data):
    """
    Calcula los totales de efectivo en Bs, USD y el total general en Bs.
    """
    tasa = cierre_data['tasa_bs']

    # 1. Efectivo
    total_bs_cash = sum(cierre_data['efectivo_bs'].values())
    total_usd_cash = sum(cierre_data['efectivo_usd'].values())

    # 2. Pagos electrónicos (Bs)
    total_electronic_bs = cierre_data['pago_movil'] + cierre_data['transferencia_bs'] + cierre_data['otros_pagos_bs']

    # 3. Pagos electrónicos (USD)
    total_electronic_usd = cierre_data['zelle_usd'] + cierre_data['transferencia_usd'] + cierre_data['otros_pagos_usd']

    # 4. Montos de Conciliación (Créditos y Adelantados)
    cobros_creditos_usd = cierre_data.get('cobro_creditos_usd', 0.0)
    pagos_adelantados_usd = cierre_data.get('pagos_adelantados_usd', 0.0)

    # --- CÁLCULOS PRINCIPALES ---
    total_usd_bruto = total_usd_cash + total_electronic_usd
    total_recaudado_bs = total_bs_cash + total_electronic_bs + (total_usd_bruto * tasa)
    total_ajustes_usd = cobros_creditos_usd + pagos_adelantados_usd

    return {
        "total_bs_efectivo": total_bs_cash,
        "total_usd_efectivo": total_usd_cash,
        "total_usd_electronico": total_electronic_usd,
        "total_recaudado_bs": total_recaudado_bs,
        "ajustes_netos_usd": total_ajustes_usd,
        "diferencia_bs": 0.0,
        "ventas_total_bs": 0.0,
        "egresos_total_bs": 0.0,
    }

def save_cierre_caja(db, form_data):
    """Guarda un nuevo cierre de caja en Firestore."""
    if db is None: return False, "DB no conectada."
    try:
        totals = calculate_cierre_totals(form_data)

        cierre_data = {
            "fecha_cierre": datetime.now(),
            "caja_id": form_data['caja_id'],
            "username": st.session_state.username,
            "nombre_cajera": st.session_state.user_name + " " + st.session_state.user_apellido,
            "tasa_bs": form_data['tasa_bs'],
            "saldo_inicial_bs": float(form_data['saldo_inicial_bs']),
            "saldo_inicial_usd": float(form_data['saldo_inicial_usd']),

            "efectivo_bs": form_data['efectivo_bs'],
            "efectivo_usd": form_data['efectivo_usd'],

            "pago_movil": float(form_data['pago_movil']),
            "zelle_usd": float(form_data['zelle_usd']),
            "zelle_bs": 0.0,
            "transferencia_usd": float(form_data['transferencia_usd']),
            "transferencia_bs": float(form_data['transferencia_bs']),
            "otros_pagos_bs": float(form_data['otros_pagos_bs']),
            "otros_pagos_usd": float(form_data['otros_pagos_usd']),

            "cobro_creditos_usd": float(form_data.get('cobro_creditos_usd', 0.0)),
            "pagos_adelantados_usd": float(form_data.get('pagos_adelantados_usd', 0.0)),

            "ventas_total_bs": totals['ventas_total_bs'],
            "egresos_total_bs": totals['egresos_total_bs'],

            "notas": form_data.get('notas', ''),
            "notas_tienda": form_data.get('notas_tienda', ''),

            **totals
        }

        db.collection(COLLECTION_NAME_CIERRES).add(cierre_data)

        return True, f"Cierre de caja de '{form_data['caja_id']}' guardado exitosamente."
    except Exception as e:
        return False, f"Error al guardar el cierre de caja: {e}"

def get_daily_cierre_summary(db, target_date):
    """Calcula el total recaudado para cada caja en un día específico."""
    if db is None: return {caja: 0.0 for caja in AVAILABLE_CAJAS}

    start_time = datetime.combine(target_date, time.min)
    end_time = datetime.combine(target_date, time.max)

    daily_totals = {caja: 0.0 for caja in AVAILABLE_CAJAS}

    try:
        cierres_ref = db.collection(COLLECTION_NAME_CIERRES)
        query = cierres_ref.where('fecha_cierre', '>=', start_time).where('fecha_cierre', '<=', end_time).stream()

        for doc in query:
            data = doc.to_dict()
            caja_id = data.get('caja_id')
            total_recaudado = data.get('total_recaudado_bs', 0.0)
            if caja_id in daily_totals:
                daily_totals[caja_id] += total_recaudado

        return daily_totals

    except Exception as e:
        st.error(f"Error al cargar el resumen diario de cierres: {e}")
        return daily_totals

def load_cierres_report(db, start_date, end_date, selected_caja=None, username_filter=None):
    """Carga los cierres de caja en un rango de fechas, opcionalmente por caja y usuario."""
    if db is None: return pd.DataFrame()
    try:
        end_datetime = datetime.combine(end_date, time.max)
        start_datetime = datetime.combine(start_date, time.min)

        cierres_ref = db.collection(COLLECTION_NAME_CIERRES)
        query = cierres_ref.where('fecha_cierre', '>=', start_datetime).where('fecha_cierre', '<=', end_datetime)

        if selected_caja and selected_caja != "Todas las Cajas":
            query = query.where('caja_id', '==', selected_caja)

        if username_filter:
            query = query.where('username', '==', username_filter)

        query = query.order_by('fecha_cierre', direction=firestore.Query.DESCENDING).stream()

        data_list = []
        for doc in query:
            data = doc.to_dict()

            ventas = data.get('ventas_total_bs', 0)
            egresos = data.get('egresos_total_bs', 0)
            diferencia_bs = data.get('diferencia_bs', 0)
            cobro_creditos = data.get('cobro_creditos_usd', 0)
            pagos_adelantados = data.get('pagos_adelantados_usd', 0)

            data_list.append({
                "Fecha": data.get('fecha_cierre').strftime('%Y-%m-%d %H:%M'),
                "Caja": data.get('caja_id', 'N/A'),
                "Cajera": data.get('nombre_cajera', 'N/A'),
                "Tasa (Bs/USD)": f"{data.get('tasa_bs', 0):,.2f}",
                "Recaudado (Bs)": f"{data.get('total_recaudado_bs', 0):,.2f}",
                "Cobro Créditos (USD)": f"{cobro_creditos:,.2f}",
                "Pagos Adelantados (USD)": f"{pagos_adelantados:,.2f}",
                "Ventas Sistema (Bs)": f"{ventas:,.2f}",
                "Egresos Sistema (Bs)": f"{egresos:,.2f}",
                "Diferencia (Bs)": f"{diferencia_bs:,.2f}",
                "total_recaudado_bs_raw": data.get('total_recaudado_bs', 0),
                "ventas_total_bs_raw": ventas,
                "egresos_total_bs_raw": egresos,
                "diferencia_bs_raw": diferencia_bs,
            })

        df = pd.DataFrame(data_list)
        return df

    except Exception as e:
        st.error(f"Error al cargar el reporte: {e}. Por favor, verifica el índice compuesto en Firebase si aplica.")
        return pd.DataFrame()

def calculate_cajera_kpis(df_cierres):
    """Calcula KPIs de rendimiento por cajera basados en la diferencia de caja."""
    if df_cierres.empty:
        return pd.DataFrame()

    df_cierres['diferencia_bs_raw'] = pd.to_numeric(df_cierres['diferencia_bs_raw'], errors='coerce')
    df_cierres['total_recaudado_bs_raw'] = pd.to_numeric(df_cierres['total_recaudado_bs_raw'], errors='coerce')
    df_cierres['error_abs'] = df_cierres['diferencia_bs_raw'].abs()

    kpis = df_cierres.groupby('Cajera').agg(
        total_cierres=('Cajera', 'size'),
        total_recaudado=('total_recaudado_bs_raw', 'sum'),
        promedio_error_abs=('error_abs', 'mean'),
        promedio_diferencia=('diferencia_bs_raw', 'mean'),
        max_diferencia=('diferencia_bs_raw', 'max'),
        min_diferencia=('diferencia_bs_raw', 'min'),
    ).reset_index()

    kpis = kpis.rename(columns={'total_cierres': 'Total Cierres', 'total_recaudado': 'Total Recaudado (Bs)'})
    promedio_recaudado_por_cierre = kpis['Total Recaudado (Bs)'] / kpis['Total Cierres']
    kpis['% Error Promedio'] = (kpis['promedio_error_abs'] / promedio_recaudado_por_cierre).fillna(0) * 100

    return kpis

# =========================================================================
# CRUD USUARIOS
# =========================================================================

def create_or_update_user(db, user_data, doc_id=None):
    """Crea un nuevo usuario o actualiza uno existente."""
    if db is None: return False, "DB no conectada."
    try:
        if not user_data['username'] or not user_data['pin'] or not user_data['rol']:
            return False, "Error: Usuario, PIN y Rol son obligatorios."

        users_ref = db.collection(COLLECTION_NAME_USERS)

        if doc_id:
            users_ref.document(doc_id).update(user_data)
            return True, f"Usuario '{user_data['username']}' actualizado exitosamente."
        else:
            existing_user = users_ref.where('username', '==', user_data['username']).limit(1).get()
            if existing_user:
                return False, f"El nombre de usuario '{user_data['username']}' ya existe."

            users_ref.add(user_data)
            return True, f"Usuario '{user_data['username']}' creado exitosamente."

    except Exception as e:
        return False, f"Error al guardar el usuario: {e}"

def load_all_users(db):
    """Carga todos los usuarios para la tabla de administración."""
    if db is None: return pd.DataFrame()
    try:
        users_ref = db.collection(COLLECTION_NAME_USERS).stream()
        users_list = []
        for doc in users_ref:
            data = doc.to_dict()
            users_list.append({
                "doc_id": doc.id,
                "Nombre": f"{data.get('nombre', '')} {data.get('apellido', '')}",
                "Usuario": data.get('username', 'N/A'),
                "Rol": data.get('rol', 'N/A').capitalize(),
                "PIN": data.get('pin', '****'),
                "Activo": "Sí" if data.get('activo', False) else "No"
            })
        return pd.DataFrame(users_list)
    except Exception as e:
        st.error(f"Error al cargar usuarios: {e}")
        return pd.DataFrame()

def toggle_user_active_status(db, doc_id, current_status):
    """Cambia el estado activo de un usuario."""
    if db is None: return False, "DB no conectada."
    try:
        new_status = not current_status
        db.collection(COLLECTION_NAME_USERS).document(doc_id).update({'activo': new_status})
        return True, f"Usuario actualizado a {'ACTIVO' if new_status else 'INACTIVO'}."
    except Exception as e:
        return False, f"Error al cambiar estado: {e}"

def get_user_by_doc_id(db, doc_id):
    """Obtiene los datos de un usuario por su ID de documento."""
    if db is None: return None
    try:
        doc = db.collection(COLLECTION_NAME_USERS).document(doc_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception:
        return None

# =========================================================================
# INTERFACES (Streamlit)
# =========================================================================

def daily_summary_interface(db):
    st.subheader("Total Recaudado del Día (Cierres Registrados)")
    today = datetime.now().date()
    daily_totals = get_daily_cierre_summary(db, today)

    col_date, col_can, col_cafe = st.columns([1, 2, 2])

    col_date.metric("Fecha", today.strftime('%d-%m-%Y'))

    total_can = daily_totals.get('Canchas Padel (Incluye Tienda)', 0.0)
    total_cafe = daily_totals.get('Cafe Bar', 0.0)

    col_can.metric(
        "Ingreso Canchas/Tienda",
        f"Bs. {total_can:,.2f}",
        help="Suma de 'Total Recaudado (Bs)' de todos los cierres de Canchas hoy."
    )
    col_cafe.metric(
        "Ingreso Café Bar",
        f"Bs. {total_cafe:,.2f}",
        help="Suma de 'Total Recaudado (Bs)' de todos los cierres de Café Bar hoy."
    )

    total_general = total_can + total_cafe
    st.markdown(f"#### 🔎 Total General Recaudado Hoy: **Bs. {total_general:,.2f}**")
    st.markdown("---")

def cajera_cierre_history_interface(db):
    st.title(f"Historial de Cierres por Empleado")
    st.markdown("Aquí puedes revisar los **cierres de caja** registrados por un empleado específico.")
    st.markdown("---")

    col_d1, col_d2, col_u = st.columns(3)
    today = datetime.now().date()
    start_date = col_d1.date_input("Fecha de Inicio:", value=today - timedelta(days=7), key="cajera_start_date_admin")
    end_date = col_d2.date_input("Fecha Final:", value=today, key="cajera_end_date_admin")

    df_all_users = load_all_users(db)
    usernames = df_all_users['Usuario'].tolist() if not df_all_users.empty else []

    username_to_filter = col_u.selectbox(
        "Filtrar por Empleado (Username):",
        options=["Todos"] + usernames,
        index=0,
        key="admin_username_filter",
        help="Selecciona un usuario para ver solo sus cierres."
    )

    filter_user = username_to_filter if username_to_filter != "Todos" else None
    df_cierres = load_cierres_report(db, start_date, end_date, selected_caja=None, username_filter=filter_user)

    if not df_cierres.empty:
        total_recaudado = df_cierres['total_recaudado_bs_raw'].sum()
        st.metric("Total Recaudado en el Filtro (Bs)", f"Bs. {total_recaudado:,.2f}")
        st.markdown("---")

        report_cols = ["Fecha", "Caja", "Cajera", "Recaudado (Bs)",
                       "Cobro Créditos (USD)", "Pagos Adelantados (USD)",
                       "Ventas Sistema (Bs)", "Egresos Sistema (Bs)", "Diferencia (Bs)"]
        st.dataframe(df_cierres[report_cols], use_container_width=True, height=500)

        csv = df_cierres.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar Historial Filtrado en CSV",
            data=csv,
            file_name=f'historial_filtrado_{username_to_filter}_{start_date}_a_{end_date}.csv',
            mime='text/csv',
        )
    else:
        st.warning("No hay cierres de caja registrados en el período/filtro seleccionado.")

def canchas_interface(db):
    st.title("🎾 Gestión de Alquileres y Créditos de Canchas")
    st.markdown("---")

    st.subheader("1. Registro de Nueva Transacción")

    with st.form(key='cancha_transaction_form', clear_on_submit=True):

        col_tipo, col_cancha, col_cliente = st.columns(3)

        tipo_transaccion = col_tipo.selectbox(
            "Tipo de Transacción:",
            options=TIPOS_TRANSACCION_CANCHA,
            help="Selecciona el tipo de movimiento: Alquiler (Venta), Crédito (Susp. por Lluvia), Cobro de Crédito o Pago Adelantado."
        )

        cancha_name = col_cancha.selectbox(
            "Cancha Referencia:",
            options=["N/A"] + AVAILABLE_CANCHAS,
            index=0,
            help="Selecciona la cancha asociada. Usa N/A para transacciones de crédito/adelanto no vinculadas a una cancha específica."
        )

        cliente_name = col_cliente.text_input("Nombre del Cliente:", help="Obligatorio para Créditos/Adelantos.")

        st.markdown("---")

        col_monto, col_pago = st.columns(2)

        monto_usd = col_monto.number_input(
            "Monto Total de la Transacción (USD):",
            min_value=0.0, step=0.5, format="%.2f",
            help="Monto de la venta o monto del crédito/adelanto. (Si es Bs, convertir a USD)."
        )

        metodo_pago = col_pago.selectbox(
            "Método de Pago:",
            options=["N/A"] + METODOS_PAGO_CANCHAS,
            index=0,
            help="Método de pago usado en esta transacción. N/A si es un Crédito/Adelanto (no venta)."
        )

        nota = st.text_area("Detalles de la Transacción/Nota:", max_chars=200)

        submit_button = st.form_submit_button("Guardar Transacción", type="primary", use_container_width=True)

        if submit_button:
            if not cliente_name and tipo_transaccion != "Alquiler Normal":
                st.error("El nombre del cliente es obligatorio para Créditos/Adelantos/Cobros de Crédito.")
            elif monto_usd <= 0:
                st.error("El monto debe ser mayor a cero.")
            elif cancha_name == "N/A" and tipo_transaccion == "Alquiler Normal":
                st.error("Debe seleccionar una cancha para un 'Alquiler Normal'.")
            else:
                transaction_data = {
                    'tipo_transaccion': tipo_transaccion,
                    'cancha_referencia': cancha_name,
                    'cliente_nombre': cliente_name,
                    'monto_usd': monto_usd,
                    'metodo_pago': metodo_pago,
                    'nota': nota,
                }
                success, message = save_cancha_transaction(db, transaction_data)
                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.markdown("---")
    st.subheader("2. Resumen de Créditos y Adelantos del Día (Ajustes de Caja)")

    today_date = datetime.now().date()
    start_time = datetime.combine(today_date, time.min)
    end_time = datetime.combine(today_date, time.max)

    summary = get_summary_cancha_transactions(db, start_time, end_time)

    col_sum1, col_sum2 = st.columns(2)
    col_sum1.metric(
        "Cobro de Créditos Pendientes",
        f"$ {summary['cobros_creditos_usd']:,.2f}",
        help="Dinero que entra hoy, pero que ya se había 'vendido' (deuda cobrada)."
    )
    col_sum2.metric(
        "Créditos por Suspensión/Pagos Adelantados",
        f"$ {summary['pagos_adelantados_usd']:,.2f}",
        help="Dinero que entra hoy, pero que pertenece a servicios futuros."
    )

def cancha_report_interface(db):
    st.title("🎾 Reporte Consolidado de Canchas")
    st.markdown("---")

    col_d1, col_d2 = st.columns(2)
    today = datetime.now().date()
    start_date = col_d1.date_input("Fecha de Inicio:", value=today - timedelta(days=7), key="cancha_start_date")
    end_date = col_d2.date_input("Fecha Final:", value=today, key="cancha_end_date")

    df_canchas = load_cancha_transactions(db, start_date, end_date)

    if df_canchas.empty:
        st.info("No hay transacciones de canchas registradas en el período seleccionado.")
        return

    df_canchas['Monto_raw'] = pd.to_numeric(df_canchas['Monto_raw'])
    total_recaudado_usd = df_canchas['Monto_raw'].sum()

    sum_by_type = df_canchas.groupby('Tipo')['Monto_raw'].sum()
    alquiler_normal_usd = sum_by_type.get('Alquiler Normal', 0.0)
    cobro_creditos_usd = sum_by_type.get('Cobro de Crédito Pendiente', 0.0)
    adelantos_y_creditos_usd = sum_by_type.get('Pago Adelantado', 0.0) + sum_by_type.get('Crédito (por Suspensión)', 0.0)

    sum_by_payment = df_canchas.groupby('Método Pago')['Monto_raw'].sum().sort_values(ascending=False)

    st.subheader("Resumen Consolidado (USD)")
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("Recaudado Total (Bruto)", f"$ {total_recaudado_usd:,.2f}")
    col_k2.metric("Alquiler Normal (Venta)", f"$ {alquiler_normal_usd:,.2f}")
    col_k3.metric("Cobros de Créditos", f"$ {cobro_creditos_usd:,.2f}")
    col_k4.metric("Adelantos y Créditos por Susp.", f"$ {adelantos_y_creditos_usd:,.2f}")

    st.markdown("---")
    st.subheader("Desglose por Método de Pago")
    df_payment = pd.DataFrame(sum_by_payment).rename(columns={'Monto_raw': 'Total Recaudado (USD)'})
    df_payment['Total Recaudado (USD)'] = df_payment['Total Recaudado (USD)'].apply(lambda x: f"$ {x:,.2f}")
    st.dataframe(df_payment, use_container_width=True)

    st.markdown("---")
    st.subheader("Transacciones Detalladas")
    display_cols = ["Fecha/Hora", "Tipo", "Cancha", "Cliente", "Método Pago", "Monto (USD)", "Registrado Por", "Nota"]
    st.dataframe(df_canchas[display_cols], use_container_width=True, height=400)

    csv = df_canchas.drop(columns=['Monto_raw']).to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar Reporte Detallado en CSV",
        data=csv,
        file_name=f'reporte_canchas_{start_date}_a_{end_date}.csv',
        mime='text/csv',
    )

def login_interface():
    st.title("🔒 Cierre de Caja App")
    st.subheader("Inicio de Sesión")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        username = st.text_input("Usuario")
        pin = st.text_input("PIN (Clave)", type="password", max_chars=5)

        if st.button("Ingresar", type="primary", use_container_width=True):
            if username and pin:
                check_login(username, pin)
            else:
                st.warning("Introduce tu usuario y PIN.")

def tasa_registration_interface(db):
    st.subheader("1. Registro de Tasa de Cambio")
    latest_tasa = get_latest_tasa(db)

    if latest_tasa:
        st.info(f"Última Tasa Registrada: **Bs. {latest_tasa['tasa_bs']:,.2f}** (al {latest_tasa['fecha'].strftime('%d-%m-%Y %H:%M')})")
        current_tasa = latest_tasa['tasa_bs']
    else:
        st.warning("No hay tasas registradas. Por favor, registre una.")
        current_tasa = 0

    with st.form(key='tasa_form', clear_on_submit=True):
        new_tasa_bs = st.number_input("Nueva Tasa Bs/USD:", min_value=1.0, step=0.01, format="%.2f", key="tasa_input")
        submit_tasa = st.form_submit_button("Guardar Tasa")
        if submit_tasa:
            success, message = save_tasa(db, new_tasa_bs, st.session_state.username)
            if success:
                st.success(message)
                t.sleep(1)
                st.rerun()
            else:
                st.error(message)
    return current_tasa

def cierre_caja_interface(db, tasa_bs):
    st.title("🧾 Registro de Cierre de Caja")
    st.markdown("---")

    if tasa_bs == 0:
        st.error("No hay una tasa de cambio registrada. No se puede proceder con el cierre.")
        return

    st.info(f"Tasa de Cambio Actual: **Bs. {tasa_bs:,.2f}**")

    with st.form(key='cierre_form'):
        form_data = {}
        form_data['tasa_bs'] = tasa_bs

        col_caja, col_tasa_info = st.columns([1, 2])
        selected_caja = col_caja.selectbox(
            "Caja a Cerrar:",
            options=AVAILABLE_CAJAS,
            key="selected_caja_input",
            help="Selecciona la caja a cerrar."
        )
        form_data['caja_id'] = selected_caja

        is_padel_caja = "Canchas Padel" in selected_caja

        today_date = datetime.now().date()
        start_time = datetime.combine(today_date, time.min)
        end_time = datetime.combine(today_date, time.max)
        summary_transactions = get_summary_cancha_transactions(db, start_time, end_time)

        st.markdown("---")
        st.subheader("A. Saldo Inicial")
        col_si1, col_si2 = st.columns(2)
        form_data['saldo_inicial_bs'] = col_si1.number_input("Saldo Inicial en **Bs** (Contado/Sistema):", min_value=0.0, step=1.0, format="%.2f")
        form_data['saldo_inicial_usd'] = col_si2.number_input("Saldo Inicial en **USD** (Contado/Sistema):", min_value=0.0, step=1.0, format="%.2f")

        st.subheader("B. Conteo de Efectivo")
        col_efectivo_bs, col_efectivo_usd = st.columns(2)

        col_efectivo_bs.markdown("##### 💵 Bolívar Digital (Bs)")
        form_data['efectivo_bs'] = {}
        total_bs_contado = 0
        for denom in CASH_DENOMINATIONS_BS:
            qty = col_efectivo_bs.number_input(f"Billetes de **{denom} Bs**:", min_value=0, step=1, key=f"bs_{denom}")
            subtotal = qty * denom
            form_data['efectivo_bs'][str(denom)] = subtotal
            total_bs_contado += subtotal
        col_efectivo_bs.markdown(f"**Total Efectivo en Bs: Bs. {total_bs_contado:,.2f}**")

        col_efectivo_usd.markdown("##### 💵 Dólar Estadounidense (USD)")
        form_data['efectivo_usd'] = {}
        total_usd_contado = 0
        for denom in CASH_DENOMINATIONS_USD:
            qty = col_efectivo_usd.number_input(f"Billetes de **{denom} USD**:", min_value=0, step=1, key=f"usd_{denom}")
            subtotal = qty * denom
            form_data['efectivo_usd'][str(denom)] = subtotal
            total_usd_contado += subtotal
        col_efectivo_usd.markdown(f"**Total Efectivo en USD: $ {total_usd_contado:,.2f}**")

        st.subheader("C. Medios de Pago Electrónicos (Recaudado)")
        col_bs, col_usd = st.columns(2)
        with col_bs:
            col_bs.markdown("##### 💳 Pagos en Bolívares (Bs)")
            form_data['pago_movil'] = st.number_input("Pago Móvil (Bs):", min_value=0.0, step=1.0, format="%.2f", key="pm_bs")
            form_data['transferencia_bs'] = st.number_input("Transferencia Bancaria (Bs):", min_value=0.0, step=1.0, format="%.2f", key="transf_bs")
            form_data['otros_pagos_bs'] = st.number_input("Otros Pagos (Bs) *Aclarar en notas*:", min_value=0.0, step=1.0, format="%.2f", key="otros_bs")
        with col_usd:
            col_usd.markdown("##### 💵 Pagos en Dólares (USD)")
            form_data['zelle_usd'] = st.number_input("Zelle/Paypal (USD):", min_value=0.0, step=1.0, format="%.2f", key="zelle_usd")
            form_data['transferencia_usd'] = st.number_input("Transf. Internacional (USD):", min_value=0.0, step=1.0, format="%.2f", key="transf_usd")
            form_data['otros_pagos_usd'] = st.number_input("Otros Pagos (USD) *Aclarar en notas*:", min_value=0.0, step=1.0, format="%.2f", key="otros_usd")

        if is_padel_caja:
            st.subheader("D. Ajustes de Conciliación (Créditos/Adelantados)")
            st.caption(f"Montos consultados automáticamente del módulo de Canchas para hoy {today_date.strftime('%d-%m-%Y')}.")
            cobros_creditos_usd_auto = summary_transactions['cobros_creditos_usd']
            pagos_adelantados_usd_auto = summary_transactions['pagos_adelantados_usd']
            col_aj1, col_aj2 = st.columns(2)
            col_aj1.info(f"Cobro de Créditos Pendientes (USD): $ {cobros_creditos_usd_auto:,.2f}")
            form_data['cobro_creditos_usd'] = cobros_creditos_usd_auto
            col_aj2.info(f"Pagos Adelantados/Reubicaciones (USD): $ {pagos_adelantados_usd_auto:,.2f}")
            form_data['pagos_adelantados_usd'] = pagos_adelantados_usd_auto
            form_data['notas_tienda'] = st.text_area("Notas de la Tienda (Ej: Detalle de Venta de Pelotas y Bebidas):", key="notas_tienda")
        else:
            form_data['cobro_creditos_usd'] = 0.0
            form_data['pagos_adelantados_usd'] = 0.0
            form_data['notas_tienda'] = ""

        st.subheader("E. Observaciones Generales")
        form_data['notas'] = st.text_area("Observaciones del cierre (diferencias, pagos extraños, etc.):", key="notas_generales")

        st.markdown("---")
        submit_cierre = st.form_submit_button("FINALIZAR Y REGISTRAR CIERRE", type="primary", use_container_width=True)

        if submit_cierre:
            success, message = save_cierre_caja(db, form_data)
            if success:
                st.success(message)
                t.sleep(1)
                st.balloons()
                st.rerun()
            else:
                st.error(message)

def dashboard_interface(db):
    st.title("📈 Dashboard General de Cierres")
    st.markdown("---")

    st.subheader("Reporte General Consolidado")
    col_d1, col_d2, col_d3 = st.columns([1.5, 1.5, 1])
    today = datetime.now().date()
    start_date = col_d1.date_input("Fecha de Inicio:", value=today - timedelta(days=7))
    end_date = col_d2.date_input("Fecha Final:", value=today)

    cajas_options = ["Todas las Cajas"] + AVAILABLE_CAJAS
    selected_caja = col_d3.selectbox("Filtrar por Caja:", options=cajas_options, index=0, key="general_caja_filter")

    df_cierres = load_cierres_report(db, start_date, end_date, selected_caja=selected_caja)

    if not df_cierres.empty:
        total_recaudado = df_cierres['total_recaudado_bs_raw'].sum()
        st.markdown("##### Total Recaudado del Período Seleccionado")
        col_k1, col_k2, col_k3 = st.columns(3)
        col_k1.metric("Recaudado Total (Bs)", f"Bs. {total_recaudado:,.2f}")
        col_k2.metric("Ventas (Sistema)", "N/A")
        col_k3.metric("Diferencia Neta", "N/A")

        st.markdown("---")
        report_cols = ["Fecha", "Caja", "Cajera", "Tasa (Bs/USD)", "Recaudado (Bs)",
                       "Cobro Créditos (USD)", "Pagos Adelantados (USD)",
                       "Ventas Sistema (Bs)", "Egresos Sistema (Bs)", "Diferencia (Bs)"]
        st.dataframe(df_cierres[report_cols], use_container_width=True, height=500)

        csv = df_cierres.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar Reporte en CSV",
            data=csv,
            file_name=f'reporte_cierres_{selected_caja.replace(" ", "_")}_{start_date}_a_{end_date}.csv',
            mime='text/csv',
        )
    else:
        st.warning(f"No hay cierres de caja registrados para '{selected_caja}' en el período seleccionado.")

def kpi_dashboard_interface(db):
    st.title("📊 Analíticas de Rendimiento Operacional")
    st.markdown("---")

    st.subheader("Filtros de Período")
    col_d1, col_d2 = st.columns(2)
    today = datetime.now().date()
    start_date = col_d1.date_input("Fecha de Inicio:", value=today - timedelta(days=30), key="kpi_start_date")
    end_date = col_d2.date_input("Fecha Final:", value=today, key="kpi_end_date")

    df_cierres = load_cierres_report(db, start_date, end_date, selected_caja="Todas las Cajas")

    if df_cierres.empty:
        st.warning("No hay datos de cierres para generar las analíticas en el período seleccionado.")
        return

    st.header("1. Tendencia de Ingresos Diarios (Recaudado Bruto)")
    df_cierres['Fecha_Cierre'] = pd.to_datetime(df_cierres['Fecha'].str.split(' ').str[0])
    df_tendencia = df_cierres.groupby('Fecha_Cierre')['total_recaudado_bs_raw'].sum().reset_index()
    df_tendencia.columns = ['Fecha', 'Total Recaudado (Bs)']
    st.line_chart(df_tendencia, x='Fecha', y='Total Recaudado (Bs)', use_container_width=True)
    st.markdown("---")

    st.header("2. Rendimiento y Precisión por Cajera")
    df_kpis = calculate_cajera_kpis(df_cierres)

    if df_kpis.empty:
        st.info("No hay datos suficientes para calcular los KPIs por cajera.")
        return

    display_kpis = df_kpis.copy()
    display_kpis['Total Recaudado (Bs)'] = display_kpis['Total Recaudado (Bs)'].apply(lambda x: f"Bs. {x:,.2f}")
    display_kpis['promedio_error_abs'] = display_kpis['promedio_error_abs'].apply(lambda x: f"Bs. {x:,.2f}")
    display_kpis['promedio_diferencia'] = display_kpis['promedio_diferencia'].apply(lambda x: f"Bs. {x:,.2f}")
    display_kpis['% Error Promedio'] = display_kpis['% Error Promedio'].apply(lambda x: f"{x:,.2f}%")

    st.dataframe(
        display_kpis.rename(columns={'promedio_error_abs': 'Error Promedio (ABS)',
                                    'promedio_diferencia': 'Diferencia Neta Promedio'}),
        use_container_width=True
    )
    st.caption("Nota: El 'Error Promedio (ABS)' mide la precisión sin importar si el error es a favor o en contra de la empresa.")

    st.markdown("#### Comparativa de Errores Promedio por Empleado")
    st.bar_chart(
        df_kpis.set_index('Cajera')[['promedio_error_abs']],
        height=300
    )
    st.caption("A menor altura de la barra, mayor precisión en los cierres.")

def user_management_interface(db):
    """Interfaz para crear, editar y desactivar usuarios."""
    st.header("Gestión de Usuarios")

    if 'edit_user_doc_id' not in st.session_state:
        st.session_state.edit_user_doc_id = None
        st.session_state.edit_user_data = {}

    df_users = load_all_users(db)
    st.subheader("Lista de Usuarios del Sistema")

    user_display_df = df_users.drop(columns=['doc_id', 'PIN']).set_index('Usuario') if not df_users.empty else pd.DataFrame()
    st.dataframe(user_display_df, use_container_width=True)

    mode = "Creación"
    if st.session_state.edit_user_doc_id:
        mode = "Edición"

    st.markdown("---")
    st.subheader(f"{mode} de Usuario")

    with st.form(key=f"user_form_{mode}"):

        col1, col2 = st.columns(2)
        nombre = col1.text_input("Nombre", value=st.session_state.edit_user_data.get('nombre', ''))
        apellido = col2.text_input("Apellido", value=st.session_state.edit_user_data.get('apellido', ''))

        col3, col4, col5 = st.columns(3)
        username = col3.text_input("Username (Único)", value=st.session_state.edit_user_data.get('username', ''), disabled=(mode == "Edición"), help="No se puede cambiar en modo edición.")
        pin = col4.text_input("PIN (5 Dígitos)", type="password", max_chars=5, value=st.session_state.edit_user_data.get('pin', ''))

        available_roles = ["cajera", "supervisora", "administrador", "programador"]
        default_role_index = available_roles.index(st.session_state.edit_user_data.get('rol', 'cajera')) if st.session_state.edit_user_data.get('rol') in available_roles else 0
        rol = col5.selectbox("Rol", options=available_roles, index=default_role_index)

        activo = st.checkbox("Activo", value=st.session_state.edit_user_data.get('activo', True))

        col_b1, col_b2, col_b3 = st.columns([2, 2, 8])

        save_button_label = "Actualizar Usuario" if mode == "Edición" else "Crear Usuario"
        submit_button = col_b1.form_submit_button(save_button_label, type="primary")
        cancel_button = col_b2.form_submit_button("Cancelar Edición", type="secondary", disabled=(mode == "Creación"))

        if submit_button:
            new_user_data = {
                'nombre': nombre,
                'apellido': apellido,
                'username': username,
                'pin': pin,
                'rol': rol,
                'activo': activo
            }
            success, message = create_or_update_user(db, new_user_data, st.session_state.edit_user_doc_id)
            if success:
                st.success(message)
                st.session_state.edit_user_doc_id = None
                st.session_state.edit_user_data = {}
                t.sleep(1)
                st.rerun()
            else:
                st.error(message)

        if cancel_button:
            st.session_state.edit_user_doc_id = None
            st.session_state.edit_user_data = {}
            st.rerun()

    st.markdown("---")
    st.subheader("Acciones Rápidas")

    col_action_id, col_action_edit, col_action_toggle = st.columns([1, 1.5, 1.5])

    username_to_act = col_action_id.text_input("Username para Acción:", key="username_action_input", help="Ingresa el nombre de usuario de la tabla.")
    user_row = df_users[df_users['Usuario'] == username_to_act] if not df_users.empty else pd.DataFrame()

    if not user_row.empty:
        doc_id_to_act = user_row.iloc[0]['doc_id']
        is_active = user_row.iloc[0]['Activo'] == "Sí"

        if col_action_edit.button("✏️ Editar Usuario", use_container_width=True):
            user_data = get_user_by_doc_id(db, doc_id_to_act)
            if user_data:
                st.session_state.edit_user_doc_id = doc_id_to_act
                st.session_state.edit_user_data = user_data
                st.rerun()
            else:
                st.warning("No se pudieron cargar los datos del usuario.")

        toggle_label = "🔒 Desactivar" if is_active else "✅ Reactivar"
        toggle_type = "secondary" if is_active else "primary"

        if col_action_toggle.button(toggle_label, type=toggle_type, use_container_width=True):
            success, message = toggle_user_active_status(db, doc_id_to_act, is_active)
            if success:
                st.success(message)
                st.session_state.edit_user_doc_id = None
                st.session_state.edit_user_data = {}
                st.session_state.username_action_input = ""
                t.sleep(1)
                st.rerun()
            else:
                st.error(message)
    else:
        col_action_edit.button("✏️ Editar Usuario", use_container_width=True, disabled=True)
        col_action_toggle.button("🔒 Desactivar/Reactivar", use_container_width=True, disabled=True)
        if username_to_act:
            st.caption(f"El usuario '{username_to_act}' no fue encontrado.")

# =========================================================================
# FUNCIÓN PRINCIPAL (MAIN)
# =========================================================================

def main():
    # Inicialización de session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None
        st.session_state.user_name = None
        st.session_state.user_apellido = None

    # Manejo de fallo de conexión a DB
    if db is None:
        st.title("📊 Cierre de Caja App")
        st.error("❌ La aplicación no puede funcionar: Falló la conexión a la base de datos (Firebase).")
        st.warning("Por favor, revisa tus 'Secrets' en Streamlit Cloud y los mensajes de error.")
        st.stop()

    # Sidebar (logo y datos del usuario)
    if os.path.exists(LOGO_PATH):
        try:
            st.sidebar.image(LOGO_PATH, use_container_width=True)
        except Exception as e:
            st.sidebar.error(f"Error al cargar el logo: {e}")
    else:
        st.sidebar.warning(f"No se encontró el archivo logo.png en la raíz del repositorio.")

    username_display = st.session_state.username if st.session_state.username else 'Invitado'
    st.sidebar.markdown(f"**Usuario:** {username_display}")

    user_role_display = st.session_state.user_role
    role_text = user_role_display.capitalize() if user_role_display else 'No Logueado'
    st.sidebar.markdown(f"**Rol:** {role_text}")

    st.sidebar.button("Cerrar Sesión", on_click=logout, disabled=not st.session_state.logged_in)
    st.sidebar.markdown("---")
    st.sidebar.info("App desarrollada en Streamlit y Firestore.")

    # Flujo de la aplicación por rol
    if not st.session_state.logged_in:
        login_interface()
    else:
        latest_tasa_data = get_latest_tasa(db)
        tasa_bs = latest_tasa_data['tasa_bs'] if latest_tasa_data else 0

        if st.session_state.user_role == "cajera":
            st.title("Panel de Cajera 🎫")
            tab_cierre, tab_canchas = st.tabs(["Cierre de Caja", "Registro de Canchas/Créditos"])
            with tab_cierre:
                cierre_caja_interface(db, tasa_bs)
            with tab_canchas:
                canchas_interface(db)
        elif st.session_state.user_role in ["supervisora", "administrador", "programador"]:
            st.title("Panel de Control de Gerencia 🧭")
            st.markdown(f"Bienvenido/a, **{st.session_state.user_role.capitalize()}**.")
            with st.expander("1. Registro de Tasa de Cambio", expanded=False):
                tasa_registration_interface(db)
            st.markdown("---")
            daily_summary_interface(db)
            tab_reporte, tab_canchas, tab_kpis = st.tabs(["Reporte Cierres", "Reporte Canchas", "Analíticas y KPIs"])
            with tab_reporte:
                cajera_cierre_history_interface(db)
                st.markdown("---")
                dashboard_interface(db)
            with tab_canchas:
                cancha_report_interface(db)
            with tab_kpis:
                kpi_dashboard_interface(db)
            st.markdown("---")
            if st.session_state.user_role in ["administrador", "programador"]:
                with st.expander("3. Administración de Usuarios (CRUD)", expanded=False):
                    user_management_interface(db)
        else:
            st.error("Rol de usuario no reconocido.")

if __name__ == '__main__':
    main()


