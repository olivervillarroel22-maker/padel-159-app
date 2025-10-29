# main.py
# Versión corregida: inicialización de Firebase y ajustes de imports
import os
import time as t
from datetime import datetime, timedelta, time
import json
import pandas as pd
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# =========================================================================
# INICIALIZACIÓN Y CONEXIONES
# =========================================================================

def init_firebase():
    """
    Inicializa Firebase y devuelve el cliente de Firestore.

    Requiere que en Streamlit Cloud (Settings -> Secrets) tengas:
    [firebase.service_account_key]
    (un table con las mismas keys que el JSON de la service account)
    """
    # Evitar re-inicializar
    if firebase_admin._apps:
        return firestore.client()

    try:
        # Leer secret
        firebase_secret = st.secrets.get("firebase", {}).get("service_account_key")
        if firebase_secret is None:
            st.error("❌ No se encontró 'firebase.service_account_key' en Streamlit Secrets. Añádelo en Settings -> Secrets.")
            st.stop()
            return None

        # Si la secret es un string JSON, convertir a dict
        if isinstance(firebase_secret, str):
            try:
                cred_json = json.loads(firebase_secret)
            except Exception:
                # Podría ser un string multilinea con la clave; fall back a intentar eval-like (no ideal)
                st.error("❌ El formato de firebase.service_account_key no parece JSON. Usa un table en Secrets (recomendado).")
                st.stop()
                return None
        else:
            cred_json = firebase_secret

        # credentials.Certificate acepta dict
        cred = credentials.Certificate(cred_json)

        # Inicializar la app correctamente (prefijando firebase_admin)
        firebase_admin.initialize_app(cred)

        return firestore.client()

    except Exception as e:
        st.error(f"❌ Error al conectar con Firebase: {e}")
        st.stop()
        return None

# =========================================================================
# CONFIGURACIÓN DE LA APP (Streamlit)
# =========================================================================

st.set_page_config(
    page_title="App Cierre de Caja",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos (mantengo los tuyos)
COLOR_TEXTO_PRINCIPAL = "#1A237E"
COLOR_PRIMARIO_ACCENT = "#00897B"
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
# FUNCIONES (autenticación, negocio y UI)
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

# --- Tasa de Cambio ---
def get_latest_tasa(db):
    if db is None: return None
    try:
        tasa_ref = db.collection(COLLECTION_NAME_TASAS).order_by('fecha', direction=firestore.Query.DESCENDING).limit(1).get()
        if tasa_ref:
            return tasa_ref[0].to_dict()
        return None
    except Exception:
        return None

def save_tasa(db, tasa_bs, user):
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

# --- Transacciones de Canchas ---
def save_cancha_transaction(db, data):
    if db is None: return False, "DB no conectada."
    try:
        data['fecha_registro'] = datetime.now()
        data['registrado_por'] = st.session_state.get('username')
        db.collection(COLLECTION_NAME_TRANSACCIONES_CANCHAS).add(data)
        return True, f"Transacción de {data.get('tipo_transaccion')} registrada exitosamente."
    except Exception as e:
        return False, f"Error al guardar la transacción de cancha: {e}"

def get_summary_cancha_transactions(db, start_time, end_time):
    if db is None: return {'cobros_creditos_usd': 0.0, 'pagos_adelantados_usd': 0.0}
    try:
        transactions_ref = db.collection(COLLECTION_NAME_TRANSACCIONES_CANCHAS)
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
        return {'cobros_creditos_usd': cobros_creditos_usd, 'pagos_adelantados_usd': pagos_adelantados_usd}
    except Exception as e:
        st.error(f"Error al cargar el resumen de transacciones de cancha: {e}")
        return {'cobros_creditos_usd': 0.0, 'pagos_adelantados_usd': 0.0}

# --- Resto de funciones y UI ---
# Nota: para no duplicar demasiado en este parche, se asume que el resto del
# código de tu main.py original (interfaces, CRUD, reportes, etc.) se pega aquí
# sin cambios lógicos. Lo fundamental era arreglar imports e init_firebase.
# Si quieres, te devuelvo el archivo completo con todo el código original ya
# integrado en esta versión corregida.

# =========================================================================
# MAIN
# =========================================================================

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None

    if db is None:
        st.title("📊 Cierre de Caja App")
        st.error("❌ La aplicación no puede funcionar: Falló la conexión a la base de datos (Firebase).")
        st.warning("Por favor, revisa tus 'Secrets' en Streamlit Cloud y los mensajes de error.")
        st.stop()

    # Sidebar y flujo de la aplicación (coloca aquí el resto de la UI que ya tenías)
    st.sidebar.markdown(f"**Usuario:** {st.session_state.username if st.session_state.username else 'Invitado'}")
    role_text = st.session_state.user_role.capitalize() if st.session_state.user_role else 'No Logueado'
    st.sidebar.markdown(f"**Rol:** {role_text}")
    st.sidebar.button("Cerrar Sesión", on_click=logout, disabled=not st.session_state.logged_in)
    st.sidebar.markdown("---")
    st.sidebar.info("App desarrollada en Streamlit y Firestore.")

    # FLOW SIMPLIFICADO: (reemplaza por tu flow original)
    if not st.session_state.logged_in:
        st.title("📊 Cierre de Caja App")
        st.subheader("Inicio de Sesión")
        username = st.text_input("Usuario")
        pin = st.text_input("PIN (Clave)", type="password", max_chars=5)
        if st.button("Ingresar", type="primary", use_container_width=True):
            if username and pin:
                check_login(username, pin)
            else:
                st.warning("Introduce tu usuario y PIN.")
    else:
        st.success(f"Sesión iniciada como {st.session_state.username} ({st.session_state.user_role})")
        st.markdown("Aquí mostrarías las pestañas y la funcionalidad según rol...")

if __name__ == '__main__':
    main()
