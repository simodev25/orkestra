"""Interactive Test Lab Session API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.test_lab_session import TestSessionState
from app.services.test_lab.session_agent import SessionAgent
from app.services.test_lab.session_orchestrator import SessionOrchestrator

router = APIRouter(prefix="/api/test-lab/sessions")

# Replace with Redis for production
_sessions: dict[str, TestSessionState] = {}

# One SessionAgent per session — preserves LLM model state across turns
_session_agents: dict[str, SessionAgent] = {}

_orchestrator = SessionOrchestrator()


# ── Request / Response models ─────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    agent_id: str | None = None
    agent_label: str | None = None
    agent_version: str | None = None


class SendMessageRequest(BaseModel):
    message: str


class SessionResponse(BaseModel):
    session: TestSessionState
    last_response: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(body: CreateSessionRequest = None):
    """Create a new interactive test lab session."""
    state = _orchestrator.create_session()

    if body and body.agent_id:
        state = _orchestrator.select_agent(
            state,
            agent_id=body.agent_id,
            agent_label=body.agent_label,
            agent_version=body.agent_version,
        )

    _sessions[state.session_id] = state
    _session_agents[state.session_id] = SessionAgent()
    return SessionResponse(session=state, last_response=None)


@router.get("/", response_model=list[TestSessionState])
async def list_sessions():
    """List all active sessions."""
    return list(_sessions.values())


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get the current state of a session."""
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return SessionResponse(session=state, last_response=None)


@router.post("/{session_id}/message", response_model=SessionResponse)
async def send_message(session_id: str, body: SendMessageRequest):
    """Send a message to an active session and get a response."""
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Retrieve (or lazily create) the per-session SessionAgent
    agent = _session_agents.get(session_id)
    if agent is None:
        agent = SessionAgent()
        _session_agents[session_id] = agent

    updated_state, response = await _orchestrator.handle_message(
        state, body.message, session_agent=agent
    )
    _sessions[session_id] = updated_state
    return SessionResponse(session=updated_state, last_response=response)
