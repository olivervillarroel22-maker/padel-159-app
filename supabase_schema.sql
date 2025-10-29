-- Tablas para la app Cierre de Caja en Supabase (Postgres)

create extension if not exists pgcrypto; -- genera gen_random_uuid()

-- 1. usuarios
create table if not exists usuarios (
  id uuid default gen_random_uuid() primary key,
  username text not null unique,
  pin text not null,
  nombre text,
  apellido text,
  rol text default 'cajera',
  activo boolean default true,
  creado_en timestamptz default now()
);

-- 2. tasas_cambio
create table if not exists tasas_cambio (
  id uuid default gen_random_uuid() primary key,
  fecha timestamptz not null default now(),
  tasa_bs numeric(20,6) not null,
  registrado_por text
);

-- 3. transacciones_canchas
create table if not exists transacciones_canchas (
  id uuid default gen_random_uuid() primary key,
  fecha_registro timestamptz not null default now(),
  tipo_transaccion text,
  cancha_referencia text,
  cliente_nombre text,
  monto_usd numeric(12,2) default 0.0,
  metodo_pago text,
  nota text,
  registrado_por text
);

-- 4. cierres_caja
create table if not exists cierres_caja (
  id uuid default gen_random_uuid() primary key,
  fecha_cierre timestamptz not null default now(),
  caja_id text,
  username text,
  nombre_cajera text,
  tasa_bs numeric(20,6),

  saldo_inicial_bs numeric(18,2) default 0.0,
  saldo_inicial_usd numeric(12,2) default 0.0,

  efectivo_bs jsonb,
  efectivo_usd jsonb,

  pago_movil numeric(18,2) default 0.0,
  zelle_usd numeric(12,2) default 0.0,
  transferencia_usd numeric(12,2) default 0.0,
  transferencia_bs numeric(18,2) default 0.0,
  otros_pagos_bs numeric(18,2) default 0.0,
  otros_pagos_usd numeric(12,2) default 0.0,

  cobro_creditos_usd numeric(12,2) default 0.0,
  pagos_adelantados_usd numeric(12,2) default 0.0,

  ventas_total_bs numeric(18,2) default 0.0,
  egresos_total_bs numeric(18,2) default 0.0,

  notas text,
  notas_tienda text,

  total_bs_efectivo numeric(18,2) default 0.0,
  total_usd_efectivo numeric(12,2) default 0.0,
  total_usd_electronico numeric(12,2) default 0.0,
  total_recaudado_bs numeric(18,2) default 0.0,
  ajustes_netos_usd numeric(12,2) default 0.0,
  diferencia_bs numeric(18,2) default 0.0
);-- Usuarios de prueba
insert into usuarios (username, pin, nombre, apellido, rol, activo)
values 
  ('admin', '12345', 'Admin', 'Local', 'administrador', true),
  ('cajera1', '11111', 'Maria', 'Perez', 'cajera', true);

-- Tasa inicial
insert into tasas_cambio (tasa_bs, registrado_por)
values (25.50, 'admin');

-- Ejemplo de transacción de cancha (opcional)
insert into transacciones_canchas (tipo_transaccion, cancha_referencia, cliente_nombre, monto_usd, metodo_pago, nota, registrado_por)
values ('Alquiler Normal', 'Cancha 1', 'Juan Lopez', 10.00, 'Efectivo (USD)', 'Reserva normal', 'cajera1');

-- Ejemplo de cierre (opcional)
insert into cierres_caja (caja_id, username, nombre_cajera, tasa_bs, saldo_inicial_bs, saldo_inicial_usd, efectivo_bs, efectivo_usd, pago_movil, zelle_usd, transferencia_usd, transferencia_bs, otros_pagos_bs, otros_pagos_usd, cobro_creditos_usd, pagos_adelantados_usd, ventas_total_bs, egresos_total_bs, notas, notas_tienda, total_bs_efectivo, total_usd_efectivo, total_usd_electronico, total_recaudado_bs, ajustes_netos_usd, diferencia_bs)
values (
  'Canchas Padel (Incluye Tienda)',
  'cajera1',
  'Maria Perez',
  25.50,
  0.00,
  0.00,
  '{"10":0,"20":0,"50":0}',
  '{"1":10}',
  0.00,
  10.00,
  0.00,
  0.00,
  0.00,
  0.00,
  0.00,
  0.00,
  0.00,
  0.00,
  'Cierre de prueba',
  'Venta de pelotas',
  0.00,
  10.00,
  0.00,
  255.00,
  0.00,
  0.00
);
