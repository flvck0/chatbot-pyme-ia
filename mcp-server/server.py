"""
chatbot_pyme_mcp — MCP Server para gestión de chatbots con IA local para PYMEs chilenas.

Herramientas disponibles:
- Gestionar negocios (crear, listar, actualizar)
- Gestionar sesiones de chat
- Analizar métricas de conversaciones
- Administrar base de conocimiento de cada negocio
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ─── Servidor ────────────────────────────────────────────────────────────────

mcp = FastMCP("chatbot_pyme_mcp")

# ─── Constantes ──────────────────────────────────────────────────────────────

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_TIMEOUT = 30.0

# ─── Utilidades compartidas ───────────────────────────────────────────────────

def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BACKEND_URL, timeout=API_TIMEOUT)


def _handle_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 404:
            return "Error: Recurso no encontrado. Verifica el ID."
        elif code == 403:
            return "Error: Sin permisos para este recurso."
        elif code == 422:
            try:
                detail = e.response.json().get("detail", "Datos inválidos")
                return f"Error de validación: {detail}"
            except Exception:
                return "Error: Datos inválidos enviados al servidor."
        elif code == 429:
            return "Error: Demasiadas solicitudes. Espera un momento."
        return f"Error API: status {code} — {e.response.text[:200]}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: La solicitud tardó demasiado. Intenta de nuevo."
    elif isinstance(e, httpx.ConnectError):
        return f"Error: No se pudo conectar al backend en {BACKEND_URL}. ¿Está corriendo?"
    return f"Error inesperado: {type(e).__name__}: {str(e)}"


def _format_datetime(dt_str: Optional[str]) -> str:
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M UTC")
    except Exception:
        return dt_str


def _format_business_md(b: Dict[str, Any]) -> str:
    return (
        f"### {b.get('name', 'Sin nombre')} (`{b.get('id', '?')}`)\n"
        f"- **Rubro**: {b.get('industry', 'N/A')}\n"
        f"- **Activo**: {'✅' if b.get('active') else '❌'}\n"
        f"- **Creado**: {_format_datetime(b.get('created_at'))}\n"
        f"- **Sesiones totales**: {b.get('total_sessions', 0)}\n"
        f"- **Mensajes totales**: {b.get('total_messages', 0)}\n"
    )


def _format_session_md(s: Dict[str, Any]) -> str:
    return (
        f"- **Sesión** `{s.get('session_id', '?')}` | "
        f"Negocio: `{s.get('business_id', '?')}` | "
        f"Mensajes: {s.get('message_count', 0)} | "
        f"Iniciada: {_format_datetime(s.get('started_at'))}"
    )


# ─── Modelos de entrada ───────────────────────────────────────────────────────

class CreateBusinessInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(..., description="Nombre del negocio (ej: 'VetCare Las Condes')", min_length=2, max_length=100)
    industry: str = Field(..., description="Rubro del negocio (ej: 'veterinaria', 'cafeteria', 'inmobiliaria')", min_length=2, max_length=60)
    system_prompt: str = Field(..., description="Prompt del sistema que define el comportamiento del chatbot para este negocio", min_length=50)
    contact_info: Optional[str] = Field(default=None, description="Contacto de derivación para el humano (ej: '+56 9 XXXX XXXX')", max_length=200)
    schedule: Optional[str] = Field(default=None, description="Horario del negocio (ej: 'Lunes a viernes 9:00-18:00')", max_length=200)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.replace(" ", "").isalnum() and not any(c in v for c in ["-", "_", ".", ","]):
            pass  # Permitir caracteres especiales en nombres de negocios
        return v


class UpdateBusinessInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    business_id: str = Field(..., description="ID único del negocio a actualizar", min_length=1)
    name: Optional[str] = Field(default=None, description="Nuevo nombre del negocio", min_length=2, max_length=100)
    industry: Optional[str] = Field(default=None, description="Nuevo rubro", min_length=2, max_length=60)
    system_prompt: Optional[str] = Field(default=None, description="Nuevo prompt del sistema", min_length=50)
    contact_info: Optional[str] = Field(default=None, description="Nuevo contacto de derivación", max_length=200)
    schedule: Optional[str] = Field(default=None, description="Nuevo horario", max_length=200)
    active: Optional[bool] = Field(default=None, description="Activar o desactivar el chatbot del negocio")


class ListBusinessesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_only: bool = Field(default=False, description="Si es True, solo retorna negocios activos")
    industry: Optional[str] = Field(default=None, description="Filtrar por rubro (ej: 'veterinaria')", max_length=60)
    limit: int = Field(default=20, description="Máximo de resultados a retornar", ge=1, le=100)
    offset: int = Field(default=0, description="Saltar N resultados para paginación", ge=0)
    response_format: str = Field(default="markdown", description="Formato de respuesta: 'markdown' o 'json'")


class GetBusinessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: str = Field(..., description="ID único del negocio", min_length=1)


class SendMessageInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    business_id: str = Field(..., description="ID del negocio al que pertenece este chat", min_length=1)
    session_id: Optional[str] = Field(default=None, description="ID de sesión existente. Si no se provee, se crea una nueva.")
    message: str = Field(..., description="Mensaje del usuario final", min_length=1, max_length=2000)


class GetSessionHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., description="ID de la sesión de chat", min_length=1)
    limit: int = Field(default=50, description="Máximo de mensajes a retornar", ge=1, le=200)


class ListSessionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: Optional[str] = Field(default=None, description="Filtrar sesiones por negocio")
    limit: int = Field(default=20, description="Máximo de sesiones a retornar", ge=1, le=100)
    offset: int = Field(default=0, description="Saltar N resultados para paginación", ge=0)


class GetMetricsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: Optional[str] = Field(default=None, description="ID del negocio. Si es None, retorna métricas globales.")
    days: int = Field(default=7, description="Cantidad de días hacia atrás para calcular métricas", ge=1, le=90)


class AddKnowledgeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    business_id: str = Field(..., description="ID del negocio al que agregar el conocimiento", min_length=1)
    topic: str = Field(..., description="Tema o categoría del conocimiento (ej: 'precios', 'horarios', 'servicios')", min_length=1, max_length=100)
    content: str = Field(..., description="Contenido del conocimiento en texto plano", min_length=10, max_length=5000)


class DeleteKnowledgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: str = Field(..., description="ID del negocio", min_length=1)
    knowledge_id: str = Field(..., description="ID del ítem de conocimiento a eliminar", min_length=1)


# ─── Herramientas — Gestión de Negocios ──────────────────────────────────────

@mcp.tool(
    name="chatbot_pyme_create_business",
    annotations={
        "title": "Crear Negocio",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def chatbot_pyme_create_business(params: CreateBusinessInput) -> str:
    """Crea un nuevo negocio en el sistema con su chatbot configurado.

    Registra el negocio y su system prompt que define cómo el chatbot
    responderá a los clientes. Cada negocio tiene su propio chatbot aislado.

    Args:
        params (CreateBusinessInput): Datos del negocio:
            - name (str): Nombre del negocio
            - industry (str): Rubro o categoría
            - system_prompt (str): Instrucciones para el chatbot (mínimo 50 chars)
            - contact_info (Optional[str]): Datos de contacto humano
            - schedule (Optional[str]): Horario de atención

    Returns:
        str: Confirmación con el ID generado y resumen del negocio creado.
    """
    try:
        async with _get_client() as client:
            resp = await client.post("/businesses", json=params.model_dump(exclude_none=True))
            resp.raise_for_status()
            data = resp.json()
        return (
            f"✅ **Negocio creado exitosamente**\n\n"
            f"- **ID**: `{data['id']}`\n"
            f"- **Nombre**: {data['name']}\n"
            f"- **Rubro**: {data['industry']}\n"
            f"- **Estado**: {'Activo ✅' if data.get('active') else 'Inactivo ❌'}\n\n"
            f"El chatbot está listo. Usa `chatbot_pyme_send_message` con "
            f"`business_id='{data['id']}'` para probarlo."
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="chatbot_pyme_list_businesses",
    annotations={
        "title": "Listar Negocios",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def chatbot_pyme_list_businesses(params: ListBusinessesInput) -> str:
    """Lista todos los negocios registrados con sus métricas básicas.

    Permite filtrar por rubro y estado, con soporte de paginación.

    Args:
        params (ListBusinessesInput): Filtros y opciones:
            - active_only (bool): Solo negocios activos
            - industry (Optional[str]): Filtrar por rubro
            - limit (int): Máximo resultados (1-100)
            - offset (int): Para paginación
            - response_format (str): 'markdown' o 'json'

    Returns:
        str: Lista de negocios con nombre, rubro, estado y métricas básicas.
    """
    try:
        query: Dict[str, Any] = {"limit": params.limit, "offset": params.offset}
        if params.active_only:
            query["active"] = "true"
        if params.industry:
            query["industry"] = params.industry

        async with _get_client() as client:
            resp = await client.get("/businesses", params=query)
            resp.raise_for_status()
            data = resp.json()

        businesses = data.get("items", [])
        total = data.get("total", len(businesses))

        if params.response_format == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)

        if not businesses:
            return "No se encontraron negocios con los filtros aplicados."

        lines = [f"## Negocios ({len(businesses)} de {total} total)\n"]
        for b in businesses:
            lines.append(_format_business_md(b))

        has_more = total > params.offset + len(businesses)
        if has_more:
            next_offset = params.offset + len(businesses)
            lines.append(f"\n_Hay más resultados. Usa `offset={next_offset}` para continuar._")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="chatbot_pyme_get_business",
    annotations={
        "title": "Obtener Detalle de Negocio",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def chatbot_pyme_get_business(params: GetBusinessInput) -> str:
    """Obtiene el detalle completo de un negocio, incluyendo su system prompt y base de conocimiento.

    Args:
        params (GetBusinessInput):
            - business_id (str): ID del negocio

    Returns:
        str: Detalle completo del negocio con system prompt y conocimiento registrado.
    """
    try:
        async with _get_client() as client:
            resp = await client.get(f"/businesses/{params.business_id}")
            resp.raise_for_status()
            b = resp.json()

        knowledge = b.get("knowledge", [])
        knowledge_section = ""
        if knowledge:
            knowledge_section = "\n### 📚 Base de Conocimiento\n"
            for k in knowledge:
                knowledge_section += f"- **{k.get('topic', '?')}** (`{k.get('id', '?')}`): {k.get('content', '')[:100]}...\n"
        else:
            knowledge_section = "\n_Sin conocimiento adicional registrado._"

        return (
            f"## {b.get('name', 'Sin nombre')}\n\n"
            f"- **ID**: `{b.get('id')}`\n"
            f"- **Rubro**: {b.get('industry', 'N/A')}\n"
            f"- **Estado**: {'Activo ✅' if b.get('active') else 'Inactivo ❌'}\n"
            f"- **Horario**: {b.get('schedule', 'No especificado')}\n"
            f"- **Contacto**: {b.get('contact_info', 'No especificado')}\n"
            f"- **Creado**: {_format_datetime(b.get('created_at'))}\n"
            f"- **Sesiones totales**: {b.get('total_sessions', 0)}\n"
            f"- **Mensajes totales**: {b.get('total_messages', 0)}\n\n"
            f"### 🤖 System Prompt\n```\n{b.get('system_prompt', 'N/A')}\n```\n"
            f"{knowledge_section}"
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="chatbot_pyme_update_business",
    annotations={
        "title": "Actualizar Negocio",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def chatbot_pyme_update_business(params: UpdateBusinessInput) -> str:
    """Actualiza los datos de un negocio existente. Solo se actualizan los campos provistos.

    Args:
        params (UpdateBusinessInput):
            - business_id (str): ID del negocio a actualizar
            - name (Optional[str]): Nuevo nombre
            - industry (Optional[str]): Nuevo rubro
            - system_prompt (Optional[str]): Nuevo prompt
            - contact_info (Optional[str]): Nuevo contacto
            - schedule (Optional[str]): Nuevo horario
            - active (Optional[bool]): Activar/desactivar

    Returns:
        str: Confirmación con los campos actualizados.
    """
    try:
        business_id = params.business_id
        payload = params.model_dump(exclude={"business_id"}, exclude_none=True)

        if not payload:
            return "No se especificaron campos para actualizar."

        async with _get_client() as client:
            resp = await client.patch(f"/businesses/{business_id}", json=payload)
            resp.raise_for_status()
            data = resp.json()

        updated_fields = ", ".join(f"`{k}`" for k in payload.keys())
        return (
            f"✅ **Negocio actualizado**\n\n"
            f"- **ID**: `{data['id']}`\n"
            f"- **Nombre**: {data['name']}\n"
            f"- **Campos actualizados**: {updated_fields}\n"
            f"- **Estado actual**: {'Activo ✅' if data.get('active') else 'Inactivo ❌'}"
        )
    except Exception as e:
        return _handle_error(e)


# ─── Herramientas — Chat ──────────────────────────────────────────────────────

@mcp.tool(
    name="chatbot_pyme_send_message",
    annotations={
        "title": "Enviar Mensaje al Chatbot",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def chatbot_pyme_send_message(params: SendMessageInput) -> str:
    """Envía un mensaje al chatbot de un negocio y obtiene la respuesta de la IA.

    Si no se provee session_id, se crea una nueva sesión automáticamente.
    El historial de la sesión se mantiene para dar contexto a la IA.

    Args:
        params (SendMessageInput):
            - business_id (str): ID del negocio
            - session_id (Optional[str]): ID de sesión existente (o None para nueva)
            - message (str): Mensaje del usuario

    Returns:
        str: Respuesta del chatbot con el session_id para continuar la conversación.
    """
    try:
        session_id = params.session_id or str(uuid.uuid4())
        payload = {
            "session_id": session_id,
            "message": params.message,
            "business_id": params.business_id,
        }
        async with _get_client() as client:
            resp = await client.post("/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return (
            f"**🤖 Respuesta del chatbot:**\n\n{data['reply']}\n\n"
            f"---\n_Session ID: `{data['session_id']}` — úsalo para continuar esta conversación._"
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="chatbot_pyme_get_session_history",
    annotations={
        "title": "Obtener Historial de Sesión",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def chatbot_pyme_get_session_history(params: GetSessionHistoryInput) -> str:
    """Obtiene el historial completo de mensajes de una sesión de chat.

    Args:
        params (GetSessionHistoryInput):
            - session_id (str): ID de la sesión
            - limit (int): Máximo de mensajes a retornar (1-200)

    Returns:
        str: Historial de mensajes ordenado cronológicamente con rol y timestamp.
    """
    try:
        async with _get_client() as client:
            resp = await client.get(
                f"/sessions/{params.session_id}/history",
                params={"limit": params.limit}
            )
            resp.raise_for_status()
            data = resp.json()

        messages = data.get("messages", [])
        if not messages:
            return f"No hay mensajes en la sesión `{params.session_id}`."

        lines = [f"## Historial — Sesión `{params.session_id}`\n"]
        lines.append(f"_Negocio: `{data.get('business_id', 'N/A')}` | Total mensajes: {len(messages)}_\n")

        for msg in messages:
            role = msg.get("role", "?")
            icon = "👤" if role == "user" else "🤖"
            ts = _format_datetime(msg.get("created_at"))
            content = msg.get("content", "")
            lines.append(f"**{icon} {role.capitalize()}** _{ts}_\n> {content}\n")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="chatbot_pyme_list_sessions",
    annotations={
        "title": "Listar Sesiones de Chat",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def chatbot_pyme_list_sessions(params: ListSessionsInput) -> str:
    """Lista las sesiones de chat, opcionalmente filtradas por negocio.

    Args:
        params (ListSessionsInput):
            - business_id (Optional[str]): Filtrar por negocio
            - limit (int): Máximo de sesiones (1-100)
            - offset (int): Para paginación

    Returns:
        str: Lista de sesiones con cantidad de mensajes y fecha de inicio.
    """
    try:
        query: Dict[str, Any] = {"limit": params.limit, "offset": params.offset}
        if params.business_id:
            query["business_id"] = params.business_id

        async with _get_client() as client:
            resp = await client.get("/sessions", params=query)
            resp.raise_for_status()
            data = resp.json()

        sessions = data.get("items", [])
        total = data.get("total", len(sessions))

        if not sessions:
            return "No se encontraron sesiones con los filtros aplicados."

        lines = [f"## Sesiones de Chat ({len(sessions)} de {total})\n"]
        for s in sessions:
            lines.append(_format_session_md(s))

        has_more = total > params.offset + len(sessions)
        if has_more:
            lines.append(f"\n_Usa `offset={params.offset + len(sessions)}` para más resultados._")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ─── Herramientas — Métricas ──────────────────────────────────────────────────

@mcp.tool(
    name="chatbot_pyme_get_metrics",
    annotations={
        "title": "Obtener Métricas",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def chatbot_pyme_get_metrics(params: GetMetricsInput) -> str:
    """Obtiene métricas de uso de los chatbots en un rango de días.

    Si no se especifica business_id, retorna métricas globales de todos los negocios.

    Args:
        params (GetMetricsInput):
            - business_id (Optional[str]): ID del negocio (None = global)
            - days (int): Días hacia atrás para calcular (1-90)

    Returns:
        str: Resumen de métricas con sesiones, mensajes, promedios y tendencias.
    """
    try:
        query: Dict[str, Any] = {"days": params.days}
        if params.business_id:
            query["business_id"] = params.business_id

        async with _get_client() as client:
            resp = await client.get("/metrics", params=query)
            resp.raise_for_status()
            m = resp.json()

        scope = f"Negocio `{params.business_id}`" if params.business_id else "**Global (todos los negocios)**"
        return (
            f"## 📊 Métricas — {scope}\n"
            f"_Últimos {params.days} días_\n\n"
            f"| Métrica | Valor |\n"
            f"|---|---|\n"
            f"| Sesiones nuevas | {m.get('new_sessions', 0)} |\n"
            f"| Mensajes totales | {m.get('total_messages', 0)} |\n"
            f"| Mensajes de usuarios | {m.get('user_messages', 0)} |\n"
            f"| Mensajes del bot | {m.get('bot_messages', 0)} |\n"
            f"| Promedio msgs/sesión | {m.get('avg_messages_per_session', 0):.1f} |\n"
            f"| Sesiones activas hoy | {m.get('active_today', 0)} |\n"
            f"| Negocios con actividad | {m.get('active_businesses', 0)} |\n\n"
            f"_Generado: {_format_datetime(m.get('generated_at'))}_"
        )
    except Exception as e:
        return _handle_error(e)


# ─── Herramientas — Base de Conocimiento ─────────────────────────────────────

@mcp.tool(
    name="chatbot_pyme_add_knowledge",
    annotations={
        "title": "Agregar Conocimiento al Negocio",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def chatbot_pyme_add_knowledge(params: AddKnowledgeInput) -> str:
    """Agrega un ítem de conocimiento a la base del negocio.

    El conocimiento se inyecta al system prompt del chatbot para que
    pueda responder preguntas específicas del negocio (precios, servicios, etc).

    Args:
        params (AddKnowledgeInput):
            - business_id (str): ID del negocio
            - topic (str): Categoría del conocimiento (ej: 'precios', 'servicios')
            - content (str): Contenido en texto plano (10-5000 chars)

    Returns:
        str: Confirmación con el ID del conocimiento creado.
    """
    try:
        payload = {
            "topic": params.topic,
            "content": params.content,
        }
        async with _get_client() as client:
            resp = await client.post(f"/businesses/{params.business_id}/knowledge", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return (
            f"✅ **Conocimiento agregado**\n\n"
            f"- **ID**: `{data['id']}`\n"
            f"- **Negocio**: `{params.business_id}`\n"
            f"- **Tema**: {params.topic}\n"
            f"- **Longitud**: {len(params.content)} caracteres\n\n"
            f"El chatbot ya puede usar este conocimiento en sus respuestas."
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="chatbot_pyme_delete_knowledge",
    annotations={
        "title": "Eliminar Conocimiento",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def chatbot_pyme_delete_knowledge(params: DeleteKnowledgeInput) -> str:
    """Elimina un ítem de conocimiento de la base de un negocio.

    Args:
        params (DeleteKnowledgeInput):
            - business_id (str): ID del negocio
            - knowledge_id (str): ID del ítem a eliminar

    Returns:
        str: Confirmación de eliminación.
    """
    try:
        async with _get_client() as client:
            resp = await client.delete(
                f"/businesses/{params.business_id}/knowledge/{params.knowledge_id}"
            )
            resp.raise_for_status()

        return (
            f"🗑️ **Conocimiento eliminado**\n\n"
            f"- **Knowledge ID**: `{params.knowledge_id}`\n"
            f"- **Negocio**: `{params.business_id}`\n\n"
            f"El chatbot ya no usará este conocimiento."
        )
    except Exception as e:
        return _handle_error(e)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
