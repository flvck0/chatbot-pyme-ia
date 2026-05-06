# 🤖 Chatbot IA Local para PYMEs Chilenas

> Asistente virtual multi-tenant con IA privada — los datos nunca salen de tu infraestructura.

**Stack:** FastAPI · Groq API (Llama 3.1) · Supabase · React + TypeScript · MCP Server

---

## ¿Qué es esto?

Sistema que permite instalar chatbots con IA en negocios locales chilenos (veterinarias, dentales, cafeterías, inmobiliarias). Cada negocio tiene su propio bot configurado con su información real — precios, horarios, servicios. Los clientes interactúan vía web o iframe embebido en el sitio del negocio.

**Diferenciador de venta:** La IA corre en infraestructura controlada (Groq open-source o Ollama local), no en OpenAI. Los datos de los clientes del negocio no salen a servidores de terceros.

---

## Arquitectura

```
React (Vercel)  <->  FastAPI (Railway)  <->  Groq API / Ollama
                           |
                      Supabase (PostgreSQL)

MCP Server -> gestión desde Claude Desktop en lenguaje natural
```

---

## 3 Modos del Frontend

El frontend detecta automáticamente el modo según los query params de la URL.

### Modo 1 — Demo standalone
```
https://tu-app.vercel.app
```
Muestra el selector de negocios. El usuario elige y entra al chat.

### Modo 2 — Demo preseleccionada (para enviar al cliente antes de la reunión)
```
https://tu-app.vercel.app/?business=ID-DEL-NEGOCIO
```
Entra directo al chat sin pasar por el selector. Manda esta URL antes de la reunión — cuando llegues, el cliente ya interactuó con su propio bot.

> **Nota:** El ID del negocio se obtiene desde la tabla `businesses` en Supabase. El de demo es `demo-vetcare-001`.

### Modo 3 — Embed con burbuja (para pegar en la web del cliente)
```
https://tu-app.vercel.app/?embed=true&business=ID-DEL-NEGOCIO
```
Muestra solo la burbuja 💬 flotante en la esquina inferior derecha. Al hacer clic abre el panel de chat. Tiene badge rojo de notificación después de 3 segundos.

#### Script de integración (pegar en `<body>` del sitio del cliente)
```html
<script>
(function() {
  var f = document.createElement('iframe');
  f.src = 'https://TU-APP.vercel.app/?embed=true&business=ID-DEL-NEGOCIO';
  f.style.cssText = 'position:fixed;bottom:0;right:0;width:430px;height:700px;border:none;z-index:9999;background:transparent;';
  f.allow = 'clipboard-write';
  document.body.appendChild(f);
})();
</script>
```

**Sin acceso al código del cliente:**
- WordPress → plugin "Insert Headers and Footers" → pegar en Footer
- Wix → Settings → Custom Code → Add to Body

---

## Setup

### 1. Supabase

1. Crear proyecto en [supabase.com](https://supabase.com)
2. SQL Editor → ejecutar `backend/schema.sql` (tablas + datos demo VetCare)
3. Copiar **Project URL** y **anon key** desde Settings → API

### 2. Groq API Key (gratis, sin tarjeta de crédito)

1. Ir a [console.groq.com](https://console.groq.com)
2. Sign Up → API Keys → Create API Key → nombre: `chatbot-pyme-prod`
3. Copiar la key (empieza con `gsk_...`)

**Límites free tier 2026:** 30 RPM · 6.000 TPM · 1.000 requests/día. Suficiente para los primeros 2-3 clientes.

### 3. Backend FastAPI

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus credenciales
uvicorn main:app --reload --port 8000
```

### 4. Frontend React

```bash
cd frontend
npm install
cp .env.example .env
# VITE_API_URL=http://localhost:8000
npm run dev
# http://localhost:5173
```

### 5. MCP Server (Claude Desktop)

Agregar en `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "chatbot-pyme": {
      "command": "python",
      "args": ["/ruta/absoluta/mcp-server/server.py"],
      "env": { "BACKEND_URL": "http://localhost:8000" }
    }
  }
}
```

---

## Variables de entorno

### `backend/.env`
```bash
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_KEY=tu_anon_key_aqui

# IA Provider: "groq" (recomendado) o "ollama" (local)
AI_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.1-8b-instant

# Solo si AI_PROVIDER=ollama:
# OLLAMA_URL=http://localhost:11434
# OLLAMA_MODEL=deepseek-r1:8b
```

### `frontend/.env`
```bash
VITE_API_URL=http://localhost:8000
# Producción: VITE_API_URL=https://tu-backend.railway.app
```

---

## Groq vs Ollama — Cuándo usar cada uno

| | Groq (recomendado ahora) | Ollama (local/VPS) |
|---|---|---|
| Costo fijo | $0 free tier | $24 USD/mes VPS |
| Velocidad | ~1-2 seg | ~3-8 seg |
| Privacidad | Datos van a Groq | 100% local |
| Setup | 5 minutos | 1-2 horas |

**Estrategia por etapa:**
- 0-3 clientes → Groq gratis
- 3-5 clientes pagando → VPS con Ollama ($24/mes compartido)
- 5+ clientes → VPS más grande, costo se diluye

Para cambiar entre proveedores: solo modifica `AI_PROVIDER` en `.env` y reinicia el backend. Sin cambios de código.

---

## Seguridad implementada

### Rate limiting
15 requests/minuto por IP en `/chat`. Protege contra spam y agotamiento del free tier de Groq.

### Protección contra prompt injection
Filtro automático de patrones maliciosos antes de enviar a la IA ("ignora tus instrucciones", "act as", "jailbreak", etc).

### CORS en producción
En `main.py`, cambiar `allow_origins=["*"]` por los dominios reales del cliente.

### Derecho al olvido (Ley 21.719 Chile)
```
DELETE /sessions/{session_id}
```
Elimina todos los mensajes de una sesión. Requerido por la ley chilena de protección de datos personales.

---

## MCP Server — 10 herramientas disponibles

Gestiona todo desde Claude Desktop en lenguaje natural:

| Herramienta | Descripción |
|---|---|
| `chatbot_pyme_create_business` | Crear negocio con su chatbot |
| `chatbot_pyme_list_businesses` | Listar todos los negocios |
| `chatbot_pyme_get_business` | Ver detalle + knowledge base |
| `chatbot_pyme_update_business` | Actualizar o desactivar |
| `chatbot_pyme_send_message` | Probar el chatbot |
| `chatbot_pyme_get_session_history` | Ver historial de conversación |
| `chatbot_pyme_list_sessions` | Listar sesiones |
| `chatbot_pyme_get_metrics` | Métricas por negocio |
| `chatbot_pyme_add_knowledge` | Agregar conocimiento al bot |
| `chatbot_pyme_delete_knowledge` | Eliminar conocimiento |

---

## Deploy a producción

### Backend → Railway
```bash
npm install -g @railway/cli
railway login && cd backend && railway init && railway up
# Agregar env vars en el dashboard de Railway
```

### Frontend → Vercel
```bash
npm install -g vercel && cd frontend && vercel --prod
# Agregar VITE_API_URL=https://tu-backend.railway.app en Vercel dashboard
```

### Costos estimados

| Componente | Costo/mes |
|---|---|
| Railway (backend) | ~$5-10 USD |
| Supabase (free tier) | $0 |
| Groq (0-3 clientes) | $0 |
| VPS Ollama (3+ clientes) | $24 USD |
| Vercel (frontend) | $0 |
| **Total** | **$5-34 USD** |

**Precio de venta por cliente:** $80k-$150k CLP/mes
**Con 5 clientes:** ~$565k CLP/mes de margen neto

---

## API Reference

```
POST   /businesses                    Crear negocio
GET    /businesses                    Listar (filtros: active, industry, limit, offset)
GET    /businesses/{id}               Detalle + knowledge base
PATCH  /businesses/{id}               Actualizar campos

POST   /businesses/{id}/knowledge     Agregar conocimiento
DELETE /businesses/{id}/knowledge/{kid} Eliminar conocimiento

POST   /chat                          Enviar mensaje al bot
GET    /sessions                      Listar sesiones
GET    /sessions/{id}/history         Historial de sesión
DELETE /sessions/{id}                 Eliminar sesión (derecho al olvido)

GET    /metrics                       Métricas (?business_id=X&days=7)
GET    /health                        Status del sistema
```

---

## Estructura del proyecto

```
chatbot-pyme-ia/
├── backend/
│   ├── main.py          # FastAPI — endpoints + lógica + rate limiting + filtro injection
│   ├── schema.sql       # Tablas Supabase + índices + datos demo VetCare Las Condes
│   ├── requirements.txt
│   ├── Procfile         # Para Railway
│   └── .env.example
├── frontend/
│   └── src/
│       └── App.tsx      # React — 3 modos (standalone / preseleccionado / embed burbuja)
├── mcp-server/
│   ├── server.py        # 10 herramientas MCP con Pydantic v2
│   └── requirements.txt
└── README.md
```

---

## Modelo de negocio

**Setup inicial (única vez):** $400k–$600k CLP
**Mensualidad:** $80k–$150k CLP/mes

**Flujo de venta:**
1. Identificar PYME con alto volumen de consultas WhatsApp
2. Configurar demo con info real del negocio vía MCP server en Claude Desktop
3. Enviar URL preseleccionada (`?business=ID`) antes de la reunión
4. En la reunión: dejar que el dueño escriba en el bot él mismo
5. Integrar en su web con el script de 5 líneas

---

*Desarrollado en Chile 🇨🇱*
