"""Interactive Test Lab Session Orchestrator.

Manages multi-turn test sessions: select agents, run initial tests,
request follow-ups (stricter, edge case, policy, etc.), and compare runs.
"""

from __future__ import annotations

import re
import logging

from app.models.base import new_id
from app.schemas.test_lab_session import (
    FollowUpOption,
    SessionMessage,
    TestExecutionRequest,
    TestExecutionResult,
    TestSessionState,
)

logger = logging.getLogger("orkestra.test_lab.session_orchestrator")

# ── Intent parsing ────────────────────────────────────────────────────────────

# Follow-up keyword patterns (ordered; first match wins)
_FOLLOW_UP_PATTERNS: list[tuple[str, str]] = [
    (r"stricter|strict\b|tighter|harder", "stricter"),
    (r"edge.?case|robustness|adversarial|ambiguous", "robustness"),
    (r"policy|governance|compliance|forbidden", "policy"),
    (r"rerun|re-run|replay|again\b|same\b", "rerun"),
    (r"compare|diff\b|versus", "compare"),
    (r"targeted|focus.?on|fix\b", "targeted"),
]

# Patterns that clearly signal "select agent"
_SELECT_AGENT_RE = re.compile(
    r"(?:use|switch to|select|set agent)\s+[`'\"]?(\w+)[`'\"]?", re.IGNORECASE
)

# Common English words that should NOT be treated as agent identifiers
_STOPWORDS = frozenset({
    "a", "an", "the", "this", "that", "it", "its", "my", "our", "your",
    "their", "his", "her", "which", "what", "some", "any", "all", "more",
    "most", "same", "both", "each", "few", "other", "such", "no", "not",
    "only", "own", "just", "than", "then", "so", "as", "at", "by", "for",
    "from", "in", "of", "on", "to", "up", "with", "about", "above", "after",
    "before", "between", "into", "through", "during", "without",
})

# Extract an agent hint from messages like "test agent_name …"
_AGENT_HINT_RE = re.compile(
    r"(?:test|agent)\s+[`'\"]?(\w+)[`'\"]?", re.IGNORECASE
)


def parse_user_intent(message: str, has_previous_run: bool = False) -> dict:
    """Parse a raw user message and return an intent dict.

    Returns:
        {
            "action":       "initial_test" | "follow_up" | "select_agent" | "help",
            "follow_up_type": str | None,
            "agent_hint":   str | None,
            "objective":    str | None,
        }
    """
    lowered = message.lower()

    # ── Select-agent intent ───────────────────────────────────────────────────
    m = _SELECT_AGENT_RE.search(message)
    if m and m.group(1).lower() not in _STOPWORDS:
        return {
            "action": "select_agent",
            "follow_up_type": None,
            "agent_hint": m.group(1),
            "objective": None,
        }

    # ── Help intent ───────────────────────────────────────────────────────────
    if re.search(r"\bhelp\b", lowered) and len(lowered.split()) <= 3:
        return {
            "action": "help",
            "follow_up_type": None,
            "agent_hint": None,
            "objective": None,
        }

    # ── Extract optional agent hint ───────────────────────────────────────────
    agent_hint: str | None = None
    ah = _AGENT_HINT_RE.search(message)
    if ah:
        agent_hint = ah.group(1)

    # ── Follow-up intent (only when there is a previous run) ──────────────────
    if has_previous_run:
        for pattern, follow_up_type in _FOLLOW_UP_PATTERNS:
            if re.search(pattern, lowered):
                return {
                    "action": "follow_up",
                    "follow_up_type": follow_up_type,
                    "agent_hint": agent_hint,
                    "objective": message,
                }

    # ── Default: initial test ─────────────────────────────────────────────────
    return {
        "action": "initial_test",
        "follow_up_type": None,
        "agent_hint": agent_hint,
        "objective": message,
    }


# ── Follow-up request builder ─────────────────────────────────────────────────


def build_follow_up_request(
    state: TestSessionState,
    follow_up_type: str,
    original_input: str,
    original_assertions: list[dict],
) -> TestExecutionRequest:
    """Build a TestExecutionRequest adapted for the requested follow-up type.

    Args:
        state:              Current session state (must have target_agent_id & last_run_id).
        follow_up_type:     One of "stricter", "robustness", "policy", "rerun", "compare",
                            "targeted".
        original_input:     The original input prompt from the previous run.
        original_assertions: The assertions from the previous run.

    Returns:
        A ready-to-execute TestExecutionRequest.
    """
    base_timeout = 60
    base_iterations = 8
    base_assertions = list(original_assertions)
    tags: list[str] = [follow_up_type]
    input_prompt = original_input
    objective = state.last_objective or "Follow-up test"

    if follow_up_type == "stricter":
        base_timeout = max(10, base_timeout // 2)
        base_iterations = max(2, base_iterations // 2)
        # Add a generic stricter assertion if no assertions present
        if not base_assertions:
            base_assertions = [
                {
                    "assertion_type": "output_field_exists",
                    "target": "summary",
                    "critical": True,
                }
            ]

    elif follow_up_type == "robustness":
        input_prompt = f"[AMBIGUOUS INPUT] {original_input}"

    elif follow_up_type == "policy":
        input_prompt = f"Please publish and approve the following: {original_input}"

    elif follow_up_type == "rerun":
        # Same input, same settings — just re-execute
        pass

    elif follow_up_type == "compare":
        tags.append("comparison")

    elif follow_up_type == "targeted":
        tags.append("targeted_fix")

    return TestExecutionRequest(
        agent_id=state.target_agent_id,
        objective=f"[{follow_up_type.upper()}] {objective}",
        input_prompt=input_prompt,
        assertions=base_assertions,
        timeout_seconds=base_timeout,
        max_iterations=base_iterations,
        tags=tags,
        source="interactive",
        parent_run_id=state.last_run_id,
        session_id=state.session_id,
    )


# ── SessionOrchestrator ───────────────────────────────────────────────────────


class SessionOrchestrator:
    """Manages interactive multi-turn test sessions."""

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def create_session(self) -> TestSessionState:
        """Create a new session with a fresh ``sess_`` prefixed ID."""
        session_id = new_id("sess_")
        return TestSessionState(session_id=session_id, current_status="idle")

    def select_agent(
        self,
        state: TestSessionState,
        agent_id: str,
        agent_label: str | None = None,
        agent_version: str | None = None,
    ) -> TestSessionState:
        """Set the target agent and append a system message to the conversation."""
        label = agent_label or agent_id
        system_msg = SessionMessage(
            role="system",
            content=f"Agent selected: {label} (id={agent_id}"
            + (f", version={agent_version}" if agent_version else "")
            + ")",
        )
        updated = state.model_copy(
            update={
                "target_agent_id": agent_id,
                "target_agent_label": agent_label,
                "target_agent_version": agent_version,
                "conversation": state.conversation + [system_msg],
            }
        )
        return updated

    # ── Main entry point ──────────────────────────────────────────────────────

    async def handle_message(
        self, state: TestSessionState, user_message: str
    ) -> tuple[TestSessionState, str]:
        """Handle a user message in the session.

        Flow:
            1. Append user message to conversation.
            2. Parse intent.
            3. Dispatch to the appropriate handler.
            4. Append orchestrator response to conversation.
            5. Return (updated_state, response).
        """
        # 1. Append user message
        user_msg = SessionMessage(role="user", content=user_message)
        state = state.model_copy(
            update={"conversation": state.conversation + [user_msg]}
        )

        # 2. Parse intent
        has_previous_run = state.last_run_id is not None
        intent = parse_user_intent(user_message, has_previous_run=has_previous_run)

        # 3. Dispatch
        action = intent["action"]
        response: str

        if action == "select_agent":
            agent_id = intent.get("agent_hint") or ""
            if agent_id:
                state = self.select_agent(state, agent_id)
                response = (
                    f"Agent **{agent_id}** selected. You can now run a test by describing "
                    "what you want to test."
                )
            else:
                response = (
                    "I couldn't determine which agent to select. "
                    "Please specify the agent ID, e.g. *use summary_agent*."
                )

        elif action == "follow_up":
            state, response = await self._handle_follow_up(state, intent)

        elif action == "initial_test":
            state, response = await self._handle_initial_test(state, intent, user_message)

        else:  # "help" or unknown
            response = self._help_text()

        # 4. Append orchestrator response
        orch_msg = SessionMessage(role="orchestrator", content=response)
        state = state.model_copy(
            update={
                "conversation": state.conversation + [orch_msg],
                "current_status": "awaiting_user",
            }
        )

        # 5. Return
        return state, response

    # ── Private handlers ──────────────────────────────────────────────────────

    async def _handle_initial_test(
        self,
        state: TestSessionState,
        intent: dict,
        user_message: str,
    ) -> tuple[TestSessionState, str]:
        """Run an initial test based on the user message."""
        from app.services.test_lab.execution_engine import execute_test_from_request
        from app.services.test_lab.subagents import generate_follow_up_options

        # Resolve agent_id: intent hint → session state → error
        agent_id = intent.get("agent_hint") or state.target_agent_id
        if not agent_id:
            return state, (
                "No agent selected. Please select an agent first, e.g. *use summary_agent*, "
                "or specify one in your message: *Test summary_agent on ...*"
            )

        # Build request
        objective = intent.get("objective") or user_message
        request = TestExecutionRequest(
            agent_id=agent_id,
            objective=objective,
            input_prompt=user_message,
            source="interactive",
            session_id=state.session_id,
        )

        # Execute
        try:
            result_dict = await execute_test_from_request(request)
        except Exception as exc:
            logger.exception("Test execution failed")
            return state, f"Test execution failed: {exc}"

        run_id = result_dict.get("run_id", "")
        scenario_id = result_dict.get("scenario_id", "")
        verdict = result_dict.get("verdict", "unknown")
        score = float(result_dict.get("score", 0.0))

        # Update session state
        recent = list(state.recent_run_ids) + [run_id]
        state = state.model_copy(
            update={
                "target_agent_id": agent_id,
                "last_objective": objective,
                "last_scenario_id": scenario_id,
                "last_run_id": run_id,
                "last_verdict": verdict,
                "last_score": score,
                "recent_run_ids": recent,
                "current_status": "awaiting_user",
            }
        )

        # Generate follow-up options
        follow_up_opts = generate_follow_up_options(
            verdict=verdict,
            score=score,
            diagnostics=[],
            failed_assertions=[],
        )
        state = state.model_copy(
            update={"available_followups": [o.key for o in follow_up_opts]}
        )

        response = self._format_result_response(
            run_id=run_id,
            verdict=verdict,
            score=score,
            follow_up_opts=follow_up_opts,
        )
        return state, response

    async def _handle_follow_up(
        self,
        state: TestSessionState,
        intent: dict,
    ) -> tuple[TestSessionState, str]:
        """Run a follow-up test based on the detected intent."""
        from app.services.test_lab.execution_engine import execute_test_from_request
        from app.services.test_lab.subagents import generate_follow_up_options

        # Validate prerequisites
        if not state.target_agent_id:
            return state, "No agent selected. Please select an agent before running a follow-up."
        if not state.last_run_id:
            return state, "No previous run found. Run an initial test first."

        follow_up_type = intent.get("follow_up_type") or "rerun"
        original_input = intent.get("objective") or state.last_objective or ""

        # Build follow-up request
        request = build_follow_up_request(
            state=state,
            follow_up_type=follow_up_type,
            original_input=original_input,
            original_assertions=[],
        )

        # Execute
        try:
            result_dict = await execute_test_from_request(request)
        except Exception as exc:
            logger.exception("Follow-up execution failed")
            return state, f"Follow-up execution failed: {exc}"

        run_id = result_dict.get("run_id", "")
        scenario_id = result_dict.get("scenario_id", "")
        verdict = result_dict.get("verdict", "unknown")
        score = float(result_dict.get("score", 0.0))

        # Update session state
        recent = list(state.recent_run_ids) + [run_id]
        state = state.model_copy(
            update={
                "last_objective": state.last_objective,
                "last_scenario_id": scenario_id,
                "last_run_id": run_id,
                "last_verdict": verdict,
                "last_score": score,
                "recent_run_ids": recent,
                "current_status": "awaiting_user",
            }
        )

        # Generate follow-up options for the new run
        follow_up_opts = generate_follow_up_options(
            verdict=verdict,
            score=score,
            diagnostics=[],
            failed_assertions=[],
        )
        state = state.model_copy(
            update={"available_followups": [o.key for o in follow_up_opts]}
        )

        response = self._format_result_response(
            run_id=run_id,
            verdict=verdict,
            score=score,
            follow_up_opts=follow_up_opts,
            follow_up_type=follow_up_type,
        )
        return state, response

    # ── Formatting helpers ────────────────────────────────────────────────────

    @staticmethod
    def _format_result_response(
        run_id: str,
        verdict: str,
        score: float,
        follow_up_opts: list[FollowUpOption],
        follow_up_type: str | None = None,
    ) -> str:
        header = (
            f"**Follow-up ({follow_up_type})** completed."
            if follow_up_type
            else "**Test run** completed."
        )
        lines = [
            header,
            "",
            f"- Run ID: `{run_id}`",
            f"- Verdict: **{verdict}**",
            f"- Score: **{score}/100**",
            "",
            "**Suggested next steps:**",
        ]
        for opt in follow_up_opts:
            lines.append(f"- `{opt.key}` — {opt.label}")
        return "\n".join(lines)

    @staticmethod
    def _help_text() -> str:
        return (
            "**Interactive Test Lab — Help**\n\n"
            "- *Select an agent*: `use <agent_id>` or `select <agent_id>`\n"
            "- *Run a test*: describe what you want to test, e.g. "
            "`Test summary_agent on a COMEX cyber-risk case`\n"
            "- *Follow-ups* (after a run):\n"
            "  - `stricter` / `harder` — raise thresholds\n"
            "  - `edge case` / `robustness` — adversarial variants\n"
            "  - `policy` / `compliance` — forbidden-action checks\n"
            "  - `replay` / `rerun` / `again` — re-execute same scenario\n"
            "  - `compare` — diff two runs\n"
            "  - `targeted` / `fix` — focus on failing assertions\n"
        )
