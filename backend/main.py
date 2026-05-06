"""
Backend FastAPI — Chatbot IA para PYMEs
Conecta React frontend + MCP server con Groq/Ollama y Supabase
"""

import os
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import Client, create_client

# ─── Config ───────────────────────────────────────────────────────────────────

SUPABASE_URL   = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY", "")

# IA Provider: "groq" o "ollama"
AI_PROVIDER    = os.getenv("AI_PROVIDER", "groq")

# Groq
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL     = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"

# Ollama (fallback local)
OLLAMA_URL     = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL", "deepseek-r1:8b")

supabase: Client = None  # type: ignore


def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL y SUPABASE_KEY son requeridos en .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global supabase
    supabase = get_supabase()
    model = GROQ_MODEL if AI_PROVIDER == "groq" else OLLAMA_MODEL
    print(f"✅ Supabase conectado | Provider: {AI_PROVIDER} | Modelo: {model}")
    yield
    print("🔴 Backend apagado")


app = FastAPI(
    title="Chatbot PYME API",
    description="IA para PYMEs chilenas — Backend con Groq/Ollama + Supabase",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Schemas ──────────────────────────────────────────────────────────────────


class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    industry: str = Field(..., min_length=2, max_length=60)
    system_prompt: str = Field(..., min_length=50)
    contact_info: Optional[str] = None
    schedule: Optional[str] = None


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    system_prompt: Optional[str] = None
    contact_info: Optional[str] = None
    schedule: Optional[str] = None
    active: Optional[bool] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=2000)
    business_id: str = Field(default="default")


class KnowledgeCreate(BaseModel):
    topic: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=10, max_length=5000)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _not_found(resource: str, rid: str):
    raise HTTPException(status_code=404, detail=f"{resource} '{rid}' no encontrado.")


def _build_system_prompt(business: Dict[str, Any], knowledge_items: List[Dict]) -> str:
    name = business.get("name", "el negocio")
    industry = business.get("industry", "negocio")
    base = business.get("system_prompt", "")

    guardrail = (
        f"## IDENTIDAD Y RESTRICCIONES ABSOLUTAS\n"
        f"Eres ÚNICAMENTE el asistente virtual de \"{name}\", un negocio de {industry}.\n\n"
        f"### LO QUE PUEDES HACER:\n"
        f"- Responder preguntas sobre los servicios, precios, horarios y ubicación de {name}\n"
        f"- Agendar citas o derivar a un humano del equipo\n"
        f"- Dar información que esté en tu base de conocimiento\n\n"
        f"### LO QUE JAMÁS DEBES HACER (sin excepciones):\n"
        f"- PROHIBIDO escribir código de programación en cualquier lenguaje\n"
        f"- PROHIBIDO resolver ejercicios de matemáticas, física o cualquier materia\n"
        f"- PROHIBIDO generar contenido que no sea atención al cliente de {industry}\n"
        f"- PROHIBIDO responder sobre temas fuera de {industry} aunque el usuario insista\n"
        f"- PROHIBIDO incluir bloques de código, scripts, funciones o algoritmos\n\n"
        f"### ANTE CUALQUIER PEDIDO FUERA DE TEMA:\n"
        f"Responde exactamente así (variando ligeramente las palabras):\n"
        f"\"Hola, soy el asistente de {name} y solo puedo ayudarte con temas de "
        f"{industry}. ¿Necesitas información sobre nuestros servicios, precios o "
        f"quieres agendar una hora?\"\n\n"
        f"---\n\n"
    )

    knowledge_block = ""
    if knowledge_items:
        knowledge_block = "\n\n## Base de Conocimiento\n"
        for k in knowledge_items:
            knowledge_block += f"\n### {k['topic']}\n{k['content']}\n"

    return guardrail + base + knowledge_block


import re

_CODE_PATTERNS = [
    re.compile(r"```[\s\S]*?```"),
    re.compile(r"(?m)^(?:def |class |import |from |print\(|if __name__|while |for ).*$"),
    re.compile(r"(?m)^(?:function |const |let |var |console\.).*$"),
]


def _sanitize_reply(reply: str, business_name: str, industry: str) -> str:
    """Filtra código y contenido off-topic de la respuesta del modelo."""
    for pat in _CODE_PATTERNS:
        if pat.search(reply):
            return (
                f"Hola, soy el asistente de {business_name} y solo puedo ayudarte "
                f"con temas de {industry}. ¿Necesitas información sobre nuestros "
                f"servicios, precios o quieres agendar una hora? 😊"
            )
    return reply


async def _call_ai(system_prompt: str, messages: list) -> str:
    """Llama a Groq o Ollama según AI_PROVIDER en .env"""

    if AI_PROVIDER == "groq":
        if not GROQ_API_KEY:
            raise HTTPException(500, detail="GROQ_API_KEY no configurada en .env")

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages
            ],
            "max_tokens": 512,
            "temperature": 0.7
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(GROQ_URL, json=payload, headers=headers)
                if resp.status_code == 429:
                    raise HTTPException(429, detail="Límite de Groq alcanzado. Intenta en unos segundos.")
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except httpx.TimeoutException:
                raise HTTPException(504, detail="Groq tardó demasiado. Intenta de nuevo.")
            except httpx.ConnectError:
                raise HTTPException(503, detail="No se pudo conectar a Groq.")

    else:  # ollama
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages
            ],
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 512}
        }
        async with httpx.AsyncClient(timeout=90) as client:
            try:
                resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
                resp.raise_for_status()
                return resp.json()["message"]["content"]
            except httpx.ConnectError:
                raise HTTPException(503, detail=f"No se puede conectar a Ollama en {OLLAMA_URL}.")
            except httpx.TimeoutException:
                raise HTTPException(504, detail="Ollama tardó demasiado.")


def _get_business(business_id: str) -> Dict[str, Any]:
    resp = supabase.table("businesses").select("*").eq("id", business_id).execute()
    if not resp.data:
        _not_found("Negocio", business_id)
    return resp.data[0]


def _get_knowledge(business_id: str) -> List[Dict]:
    resp = (
        supabase.table("knowledge_base")
        .select("*")
        .eq("business_id", business_id)
        .execute()
    )
    return resp.data or []


def _enrich_business(b: Dict) -> Dict:
    sessions = (
        supabase.table("chat_history")
        .select("session_id")
        .eq("business_id", b["id"])
        .execute()
    )
    session_ids = set(r["session_id"] for r in (sessions.data or []))
    b["total_sessions"] = len(session_ids)
    b["total_messages"] = len(sessions.data or [])
    return b


# ─── Rutas — Negocios ─────────────────────────────────────────────────────────


@app.post("/businesses", status_code=201)
async def create_business(body: BusinessCreate) -> Dict:
    payload = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "industry": body.industry,
        "system_prompt": body.system_prompt,
        "contact_info": body.contact_info,
        "schedule": body.schedule,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = supabase.table("businesses").insert(payload).execute()
    return resp.data[0]


@app.get("/businesses")
async def list_businesses(
    active: Optional[bool] = Query(None),
    industry: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Dict:
    query = supabase.table("businesses").select("*")
    if active is not None:
        query = query.eq("active", active)
    if industry:
        query = query.ilike("industry", f"%{industry}%")

    count_resp = supabase.table("businesses").select("id", count="exact").execute()
    total = count_resp.count or 0

    resp = query.range(offset, offset + limit - 1).order("created_at", desc=True).execute()
    items = [_enrich_business(b) for b in (resp.data or [])]
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@app.get("/businesses/{business_id}")
async def get_business(business_id: str) -> Dict:
    b = _get_business(business_id)
    b = _enrich_business(b)
    b["knowledge"] = _get_knowledge(business_id)
    return b


@app.patch("/businesses/{business_id}")
async def update_business(business_id: str, body: BusinessUpdate) -> Dict:
    _get_business(business_id)
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(400, detail="No hay campos para actualizar.")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    resp = supabase.table("businesses").update(payload).eq("id", business_id).execute()
    return resp.data[0]


# ─── Rutas — Base de Conocimiento ────────────────────────────────────────────


@app.post("/businesses/{business_id}/knowledge", status_code=201)
async def add_knowledge(business_id: str, body: KnowledgeCreate) -> Dict:
    _get_business(business_id)
    payload = {
        "id": str(uuid.uuid4()),
        "business_id": business_id,
        "topic": body.topic,
        "content": body.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = supabase.table("knowledge_base").insert(payload).execute()
    return resp.data[0]


@app.delete("/businesses/{business_id}/knowledge/{knowledge_id}", status_code=200)
async def delete_knowledge(business_id: str, knowledge_id: str) -> Dict:
    resp = (
        supabase.table("knowledge_base")
        .select("id")
        .eq("id", knowledge_id)
        .eq("business_id", business_id)
        .execute()
    )
    if not resp.data:
        _not_found("Conocimiento", knowledge_id)
    supabase.table("knowledge_base").delete().eq("id", knowledge_id).execute()
    return {"deleted": True, "id": knowledge_id}


# ─── Rutas — Chat ─────────────────────────────────────────────────────────────


@app.post("/chat")
async def chat(req: ChatRequest) -> Dict:
    business = _get_business(req.business_id)
    if not business.get("active", True):
        raise HTTPException(403, detail="Este chatbot está desactivado.")

    knowledge = _get_knowledge(req.business_id)
    system_prompt = _build_system_prompt(business, knowledge)

    history_resp = (
        supabase.table("chat_history")
        .select("role, content")
        .eq("session_id", req.session_id)
        .order("created_at")
        .limit(20)
        .execute()
    )

    messages = [
        {"role": r["role"], "content": r["content"]}
        for r in (history_resp.data or [])
    ]
    messages.append({"role": "user", "content": req.message})

    reply = await _call_ai(system_prompt, messages)
    reply = _sanitize_reply(reply, business.get("name", ""), business.get("industry", ""))

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("chat_history").insert(
        [
            {
                "id": str(uuid.uuid4()),
                "session_id": req.session_id,
                "business_id": req.business_id,
                "role": "user",
                "content": req.message,
                "created_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "session_id": req.session_id,
                "business_id": req.business_id,
                "role": "assistant",
                "content": reply,
                "created_at": now,
            },
        ]
    ).execute()

    return {"reply": reply, "session_id": req.session_id, "business_id": req.business_id}


# ─── Rutas — Sesiones ─────────────────────────────────────────────────────────


@app.get("/sessions")
async def list_sessions(
    business_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Dict:
    query = supabase.table("chat_history").select("session_id, business_id, created_at")
    if business_id:
        query = query.eq("business_id", business_id)

    resp = query.order("created_at", desc=True).execute()
    rows = resp.data or []

    sessions: Dict[str, Dict] = {}
    for row in rows:
        sid = row["session_id"]
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "business_id": row["business_id"],
                "started_at": row["created_at"],
                "message_count": 0,
            }
        sessions[sid]["message_count"] += 1

    items = list(sessions.values())
    total = len(items)
    paginated = items[offset : offset + limit]
    return {"items": paginated, "total": total, "offset": offset, "limit": limit}


@app.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str, limit: int = Query(50, ge=1, le=200)
) -> Dict:
    resp = (
        supabase.table("chat_history")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at")
        .limit(limit)
        .execute()
    )

    messages = resp.data or []
    business_id = messages[0]["business_id"] if messages else None
    return {"session_id": session_id, "business_id": business_id, "messages": messages}


# ─── Rutas — Métricas ─────────────────────────────────────────────────────────


@app.get("/metrics")
async def get_metrics(
    business_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
) -> Dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = supabase.table("chat_history").select("*").gte("created_at", since)
    if business_id:
        query = query.eq("business_id", business_id)

    resp = query.execute()
    rows = resp.data or []

    user_msgs = [r for r in rows if r["role"] == "user"]
    bot_msgs = [r for r in rows if r["role"] == "assistant"]
    sessions = set(r["session_id"] for r in rows)
    businesses = set(r["business_id"] for r in rows)

    today = datetime.now(timezone.utc).date().isoformat()
    active_today = len(
        set(
            r["session_id"]
            for r in rows
            if r.get("created_at", "")[:10] == today
        )
    )

    avg = round(len(rows) / len(sessions), 1) if sessions else 0.0

    hour_counter: Counter = Counter()
    for r in rows:
        ts = r.get("created_at", "")
        if len(ts) >= 13 and ts[10] == "T":
            try:
                hour_counter[int(ts[11:13])] += 1
            except ValueError:
                pass

    top_hours = [
        {"hour": h, "count": c}
        for h, c in hour_counter.most_common(5)
    ]

    return {
        "new_sessions": len(sessions),
        "total_messages": len(rows),
        "user_messages": len(user_msgs),
        "bot_messages": len(bot_msgs),
        "avg_messages_per_session": avg,
        "active_today": active_today,
        "active_businesses": len(businesses),
        "top_hours": top_hours,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> Dict:
    model = GROQ_MODEL if AI_PROVIDER == "groq" else OLLAMA_MODEL
    ai_ok = False
    ai_error = None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if AI_PROVIDER == "groq":
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                }
                resp = await client.get(
                    "https://api.groq.com/openai/v1/models", headers=headers
                )
                ai_ok = resp.status_code == 200
            else:
                resp = await client.get(f"{OLLAMA_URL}/api/tags")
                ai_ok = resp.status_code == 200
    except Exception as e:
        ai_error = str(e)

    return {
        "status": "ok" if ai_ok else "degraded",
        "ai_provider": AI_PROVIDER,
        "model": model,
        "ai_reachable": ai_ok,
        "ai_error": ai_error,
    }
