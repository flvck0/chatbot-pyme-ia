-- ============================================================
-- Chatbot PYME — Schema Supabase
-- Ejecutar en el SQL Editor de tu proyecto Supabase
-- ============================================================

-- Tabla de negocios
create table if not exists businesses (
  id            text primary key,
  name          text not null,
  industry      text not null,
  system_prompt text not null,
  contact_info  text,
  schedule      text,
  active        boolean default true,
  created_at    timestamptz default now(),
  updated_at    timestamptz
);

-- Tabla historial de chat (una fila por mensaje)
create table if not exists chat_history (
  id          text primary key,
  session_id  text not null,
  business_id text not null references businesses(id) on delete cascade,
  role        text not null check (role in ('user', 'assistant')),
  content     text not null,
  created_at  timestamptz default now()
);

-- Tabla base de conocimiento por negocio
create table if not exists knowledge_base (
  id          text primary key,
  business_id text not null references businesses(id) on delete cascade,
  topic       text not null,
  content     text not null,
  created_at  timestamptz default now()
);

-- Índices para performance
create index if not exists idx_chat_session
  on chat_history(session_id, created_at);

create index if not exists idx_chat_business
  on chat_history(business_id, created_at);

create index if not exists idx_knowledge_business
  on knowledge_base(business_id);

-- ============================================================
-- Datos de demo — VetCare Las Condes
-- ============================================================

insert into businesses (id, name, industry, system_prompt, contact_info, schedule, active)
values (
  'demo-vetcare-001',
  'VetCare Las Condes',
  'veterinaria',
  'Eres el asistente virtual de VetCare Las Condes.

## Tu personalidad
Eres cercano, empático y profesional. Usas un español chileno natural.
Eres breve — máximo 3 oraciones salvo que pidan más detalle.
Si no sabes algo, dices que el equipo puede ayudar y das el contacto.

## Lo que puedes hacer
1. Responder preguntas frecuentes del negocio
2. Agendar citas (recopilas: nombre, mascota, servicio, fecha preferida, teléfono)
3. Derivar a humano cuando el cliente lo pide o el tema es complejo

## Lo que NO haces
- No prometes servicios fuera del listado
- No das precios que no estén en tu información
- No discutes con clientes molestos — empatizas y escalas

## Flujo de agendamiento
Cuando alguien quiere agendar: pide nombre, nombre de la mascota, servicio, fecha preferida y teléfono.
Confirma: "Perfecto [nombre], agendamos a [mascota] para [servicio] el [fecha]. El equipo confirma en menos de 2 horas."',
  '+56 9 8765 4321',
  'Lunes a viernes 9:00–20:00 | Sábados 10:00–14:00',
  true
) on conflict (id) do nothing;

insert into knowledge_base (id, business_id, topic, content)
values
  ('kb-001', 'demo-vetcare-001', 'Precios', 'Consulta general: $25.000. Vacunación desde $15.000. Peluquería canina desde $18.000. Desparasitación: $12.000. Urgencias fuera de horario: $45.000.'),
  ('kb-002', 'demo-vetcare-001', 'Servicios', 'Ofrecemos: consulta general, vacunación, peluquería canina y felina, desparasitación, cirugías programadas, urgencias, microchip, y control de peso.'),
  ('kb-003', 'demo-vetcare-001', 'Ubicación y estacionamiento', 'Estamos en Av. Apoquindo 4501, Las Condes. Hay estacionamiento gratuito para clientes en el subterráneo del edificio.')
on conflict (id) do nothing;
