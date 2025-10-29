# main.py - Versión adaptada a Supabase (Postgres) usando supabase-py
import os
import time as t
from datetime import datetime, timedelta, time
import json
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# =========================================================================
# CONFIG / CONEXIÓN A SUPABASE
# =========================================================================

@st.cache_resource
def init_supabase():
    """
    Inicializa y devuelve el cliente Supabase.
    Configura en Streamlit Secrets (Settings -> Secrets) algo así:
    [supabase]
    url = "https://xxxxx.supabase.co"
    key = "PUBLIC_OR_SERVICE_ROLE_KEY"
    """
    supabase_secrets = st.secrets.get("supabase", {})
    url = supabase_secrets.get("url")
    key = supabase_secrets.get("key")
    if not url or not key:
        st.error("❌ No se encontró la configuración de Supabase en Streamlit Secrets. Añade [supabase] url y key.")
        st.stop()
        return None
    try:
        client: Client = create_client(url, key)
        return client
    except Exception as e:
        st.error(f"❌ Error al inicializar Supabase: {e}")
        st.stop()
        return None

supabase = init_supabase()

# =========================================================================
# CONSTANTES
# =========================================================================

COL_USERS = "usuarios"
COL_TASAS = "tasas_cambio"
COL_TRANSACCIONES = "transacciones_canchas"
COL_CIERRES = "cierres_caja"

CASH_DENOMINATIONS_BS = [10, 20, 50, 100, 200, 500]
CASH_DENOMINATIONS_USD = [1, 5, 10, 20, 50, 100]
AVAILABLE_CAJAS = ["Canchas Padel (Incluye Tienda)", "Cafe Bar"]
TIPOS_TRANSACCION_CANCHA = ["Alquiler Normal", "Crédito (por Suspensión)", "Cobro de Crédito Pendiente", "Pago Adelantado"]
AVAILABLE_CANCHAS = ["Cancha 1", "Cancha 2", "Cancha 3", "Cancha 4"]
METODOS_PAGO_CANCHAS = ["Punto de Venta/Débito (Bs)", "Pago Móvil (Bs)", "Efectivo (USD)", "Zelle (USD)", "Venmo (USD)"]

# =========================================================================
# UTIL: helper para consultas a Supabase
# =========================================================================

def supa_select(table, eq_filters=None, range_filters=None, order_by=None, limit=None):
    """
    Pequeño helper para SELECT con supabase.client
    eq_filters: dict de {col: value} para .eq
    range_filters: list de tuples ('col', 'gte', value) o ('col', 'lte', value)
    order_by: tuple (col, asc_boolean)
    """
    if supabase is None: return []
    q = supabase.table(table).select("*")
    if eq_filters:
        for k, v in eq_filters.items():
            q = q.eq(k, v)
    if range_filters:
        for (col, op, val) in range_filters:
            if op == "gte": q = q.gte(col, val)
            if op == "lte": q = q.lte(col, val)
    if order_by:
        col, asc = order_by
        q = q.order(col, asc=asc)
    if limit:
        q = q.limit(limit)
    res = q.execute()
    return res.data if res.status_code in (200, 201) else []

def supa_insert(table, payload):
    if supabase is None: return False, "DB no conectada."
    res = supabase.table(table).insert(payload).execute()
    if res.status_code in (200, 201):
        return True, res.data
    return False, f"Error insert: {res.status_code} {res.data}"

# =========================================================================
# AUTENTICACIÓN
# =========================================================================

def check_login(username, pin):
    if supabase is None:
        st.error("DB no conectada.")
        return False
    try:
        rows = supa_select(COL_USERS, eq_filters={"username": username, "pin": pin, "activo": True}, limit=1)
        if rows:
            user = rows[0]
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.user_role = user.get('rol', 'cajera')
            st.session_state.user_name = user.get('nombre', '')
            st.session_state.user_apellido = user.get('apellido', '')
            st.success(f"Bienvenido/a, {st.session_state.user_name} ({st.session_state.user_role})")
            t.sleep(0.8)
            st.rerun()
            return True
        else:
            st.error("Credenciales inválidas o usuario inactivo.")
            return False
    except Exception as e:
        st.error(f"Error en autenticación: {e}")
        return False

def logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.session_state.user_apellido = None
    st.info("Sesión cerrada.")
    t.sleep(0.3)
    st.rerun()

# =========================================================================
# LÓGICA (tasas, transacciones, cierres)
# =========================================================================

def get_latest_tasa():
    rows = supa_select(COL_TASAS, order_by=("fecha", False), limit=1)
    return rows[0] if rows else None

def save_tasa(tasa_bs, user):
    if supabase is None: return False, "DB no conectada."
    try:
        payload = {"tasa_bs": float(tasa_bs), "registrado_por": user, "fecha": datetime.utcnow().isoformat()}
        success, data = supa_insert(COL_TASAS, payload)
        if success: return True, "Tasa registrada."
        return False, data
    except Exception as e:
        return False, f"Error: {e}"

def save_cancha_transaction(data):
    if supabase is None: return False, "DB no conectada."
    try:
        data['fecha_registro'] = datetime.utcnow().isoformat()
        data['registrado_por'] = st.session_state.get('username')
        success, res = supa_insert(COL_TRANSACCIONES, data)
        if success: return True, "Transacción registrada."
        return False, res
    except Exception as e:
        return False, f"Error: {e}"

def get_summary_cancha_transactions(start_time, end_time):
    if supabase is None: return {'cobros_creditos_usd': 0.0, 'pagos_adelantados_usd': 0.0}
    try:
        rows = supa_select(COL_TRANSACCIONES, range_filters=[('fecha_registro', 'gte', start_time.isoformat()), ('fecha_registro', 'lte', end_time.isoformat())])
        cobros = 0.0
        pagos_adel = 0.0
        for r in rows:
            monto = float(r.get('monto_usd', 0.0))
            tipo = r.get('tipo_transaccion')
            if tipo == "Cobro de Crédito Pendiente":
                cobros += monto
            elif tipo in ["Crédito (por Suspensión)", "Pago Adelantado"]:
                pagos_adel += monto
        return {'cobros_creditos_usd': cobros, 'pagos_adelantados_usd': pagos_adel}
    except Exception as e:
        st.error(f"Error al cargar resumen: {e}")
        return {'cobros_creditos_usd': 0.0, 'pagos_adelantados_usd': 0.0}

def save_cierre_caja(form_data):
    if supabase is None: return False, "DB no conectada."
    try:
        totals = calculate_cierre_totals(form_data)
        payload = {
            "fecha_cierre": datetime.utcnow().isoformat(),
            "caja_id": form_data['caja_id'],
            "username": st.session_state.username,
            "nombre_cajera": f"{st.session_state.user_name} {st.session_state.user_apellido}",
            "tasa_bs": float(form_data['tasa_bs']),
            "saldo_inicial_bs": float(form_data['saldo_inicial_bs']),
            "saldo_inicial_usd": float(form_data['saldo_inicial_usd']),
            "efectivo_bs": json.dumps(form_data['efectivo_bs']),
            "efectivo_usd": json.dumps(form_data['efectivo_usd']),
            "pago_movil": float(form_data['pago_movil']),
            "zelle_usd": float(form_data['zelle_usd']),
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
            "total_bs_efectivo": totals['total_bs_efectivo'],
            "total_usd_efectivo": totals['total_usd_efectivo'],
            "total_usd_electronico": totals['total_usd_electronico'],
            "total_recaudado_bs": totals['total_recaudado_bs'],
            "ajustes_netos_usd": totals['ajustes_netos_usd'],
            "diferencia_bs": totals['diferencia_bs']
        }
        success, res = supa_insert(COL_CIERRES, payload)
        if success: return True, "Cierre guardado exitosamente."
        return False, res
    except Exception as e:
        return False, f"Error: {e}"

def load_cancha_transactions(start_date, end_date):
    if supabase is None: return pd.DataFrame()
    try:
        start_iso = datetime.combine(start_date, time.min).isoformat()
        end_iso = datetime.combine(end_date, time.max).isoformat()
        rows = supa_select(COL_TRANSACCIONES, range_filters=[('fecha_registro','gte', start_iso), ('fecha_registro','lte', end_iso)], order_by=('fecha_registro', False))
        data_list = []
        for r in rows:
            fecha = r.get('fecha_registro', '')[:16].replace('T',' ')
            monto_usd = float(r.get('monto_usd') or 0.0)
            data_list.append({
                "Fecha/Hora": fecha,
                "Tipo": r.get('tipo_transaccion', 'N/A'),
                "Cancha": r.get('cancha_referencia', 'N/A'),
                "Cliente": r.get('cliente_nombre', 'N/A'),
                "Método Pago": r.get('metodo_pago', 'N/A'),
                "Monto (USD)": f"$ {monto_usd:,.2f}",
                "Monto_raw": monto_usd,
                "Registrado Por": r.get('registrado_por', 'N/A'),
                "Nota": r.get('nota','')
            })
        return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"Error cargar: {e}")
        return pd.DataFrame()

def load_cierres_report(start_date, end_date, selected_caja=None, username_filter=None):
    if supabase is None: return pd.DataFrame()
    try:
        start_iso = datetime.combine(start_date, time.min).isoformat()
        end_iso = datetime.combine(end_date, time.max).isoformat()
        filters = [('fecha_cierre','gte', start_iso), ('fecha_cierre','lte', end_iso)]
        rows = supa_select(COL_CIERRES, range_filters=filters, order_by=('fecha_cierre', False))
        data_list = []
        for r in rows:
            if selected_caja and selected_caja != "Todas las Cajas" and r.get('caja_id') != selected_caja:
                continue
            if username_filter and r.get('username') != username_filter:
                continue
            fecha = r.get('fecha_cierre','')[:16].replace('T',' ')
            ventas = float(r.get('ventas_total_bs') or 0.0)
            egresos = float(r.get('egresos_total_bs') or 0.0)
            diferencia_bs = float(r.get('diferencia_bs') or 0.0)
            cobro_creditos = float(r.get('cobro_creditos_usd') or 0.0)
            pagos_adelantados = float(r.get('pagos_adelantados_usd') or 0.0)
            data_list.append({
                "Fecha": fecha,
                "Caja": r.get('caja_id', 'N/A'),
                "Cajera": r.get('nombre_cajera','N/A'),
                "Tasa (Bs/USD)": f"{float(r.get('tasa_bs',0)):,.2f}",
                "Recaudado (Bs)": f"{float(r.get('total_recaudado_bs',0)):,.2f}",
                "Cobro Créditos (USD)": f"{cobro_creditos:,.2f}",
                "Pagos Adelantados (USD)": f"{pagos_adelantados:,.2f}",
                "Ventas Sistema (Bs)": f"{ventas:,.2f}",
                "Egresos Sistema (Bs)": f"{egresos:,.2f}",
                "Diferencia (Bs)": f"{diferencia_bs:,.2f}",
                "total_recaudado_bs_raw": float(r.get('total_recaudado_bs',0)),
                "ventas_total_bs_raw": ventas,
                "egresos_total_bs_raw": egresos,
                "diferencia_bs_raw": diferencia_bs,
            })
        return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"Error al cargar cierres: {e}")
        return pd.DataFrame()

# =========================================================================
# FUNCIONES COMUNES (calculos)
# =========================================================================

def calculate_cierre_totals(cierre_data):
    tasa = cierre_data['tasa_bs']
    total_bs_cash = sum(cierre_data['efectivo_bs'].values())
    total_usd_cash = sum(cierre_data['efectivo_usd'].values())
    total_electronic_bs = cierre_data['pago_movil'] + cierre_data['transferencia_bs'] + cierre_data['otros_pagos_bs']
    total_electronic_usd = cierre_data['zelle_usd'] + cierre_data['transferencia_usd'] + cierre_data['otros_pagos_usd']
    cobros_creditos_usd = cierre_data.get('cobro_creditos_usd', 0.0)
    pagos_adelantados_usd = cierre_data.get('pagos_adelantados_usd', 0.0)
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

# =========================================================================
# UI: flujo básico (usa tu UI original si quieres)
# =========================================================================

st.set_page_config(page_title="App Cierre de Caja (Supabase)", page_icon="📊", layout="wide")

def login_interface():
    st.title("🔒 Cierre de Caja App (Supabase)")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("Usuario")
        pin = st.text_input("PIN (Clave)", type="password", max_chars=5)
        if st.button("Ingresar", type="primary", use_container_width=True):
            if username and pin:
                check_login(username, pin)
            else:
                st.warning("Introduce tu usuario y PIN.")

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None
        st.session_state.user_name = None
        st.session_state.user_apellido = None

    if supabase is None:
        st.title("📊 App Cierre de Caja")
        st.error("La aplicación no puede funcionar: Falló la conexión a Supabase.")
        st.stop()

    st.sidebar.markdown(f"**Usuario:** {st.session_state.username if st.session_state.username else 'Invitado'}")
    role_text = st.session_state.user_role.capitalize() if st.session_state.user_role else 'No Logueado'
    st.sidebar.markdown(f"**Rol:** {role_text}")
    st.sidebar.button("Cerrar Sesión", on_click=logout, disabled=not st.session_state.logged_in)
    st.sidebar.markdown("---")

    if not st.session_state.logged_in:
        login_interface()
    else:
        if st.session_state.user_role == "cajera":
            st.title("Panel de Cajera 🎫")
            st.info("Usa la UI original para cerrar cajas (implementa con save_cierre_caja).")
        else:
            st.title("Panel de Gerencia")
            st.info("Panel de gerencia operativa (usa UI original)")

if __name__ == '__main__':
    main()
