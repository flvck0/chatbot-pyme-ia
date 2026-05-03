# 🤖 Chatbot IA Local para PYMEs Chilenas

Stack: **FastAPI + Ollama (DeepSeek) + Supabase + React 18 + MCP Server**

Arquitectura multi-tenant: un backend sirve múltiples negocios con chatbots aislados.
Los datos **nunca salen de tu infraestructura** — privacidad total.

```
React (Vite)          Claude Desktop
    ↓                      ↓
FastAPI Backend ←── MCP Server
    ↓          ↓
Ollama (local)  Supabase (PostgreSQL)
```

---

## 🚀 Setup rápido

### 1. Supabase

```bash
# Crea proyecto en supabase.com
# SQL Editor → ejecuta backend/schema.sql
# Settings → API → copia URL y anon key
```

### 2. Ollama

```bash
brew install ollama
ollama pull deepseek-r1:8b
ollama serve
```

### 3. Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edita con tus credenciales
uvicorn main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
# → http://localhost:5173
```

---

## 🔌 MCP Server — Claude Desktop

```bash
cd mcp-server
pip install -r requirements.txt
```

Configura en `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "chatbot-pyme": {
      "command": "python",
      "args": ["/ruta/completa/mcp-server/server.py"],
      "env": { "BACKEND_URL": "http://localhost:8000" }
    }
  }
}
```

**10 herramientas disponibles:**
`create_business`, `list_businesses`, `get_business`, `update_business`,
`send_message`, `get_session_history`, `list_sessions`, `get_metrics`,
`add_knowledge`, `delete_knowledge`

---

## 📁 Estructura

```
chatbot-pyme/
├── backend/
│   ├── main.py           # FastAPI completa
│   ├── schema.sql        # Tablas + datos demo
│   ├── requirements.txt
│   ├── .env.example
│   └── Procfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx       # React — UI completa
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── mcp-server/
│   ├── server.py         # 10 herramientas MCP
│   └── requirements.txt
└── README.md
```

---

## 🧪 Probar

```bash
# Chat con VetCare demo
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test-001","message":"¿Cuánto cuesta una consulta?","business_id":"demo-vetcare-001"}'

# Health check
curl http://localhost:8000/health

# Métricas
curl http://localhost:8000/metrics
```

---

## 💰 Costos producción

| Componente | Costo/mes |
|---|---|
| Railway (backend) | ~$5–10 USD |
| Supabase (free tier) | $0 |
| VPS DigitalOcean (Ollama) | $24 USD |
| Vercel (frontend) | $0 |
| **Total** | **~$30–35 USD** |

Precio por cliente: $80k–$150k CLP/mes → con 5 clientes = $450k–$750k CLP/mes.
