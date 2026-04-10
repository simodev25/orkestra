"""Agentic Test Lab services.

Architecture:
- execution_engine: Deterministic 5-phase test pipeline
- target_agent_runner: Real agent execution abstraction
- session_orchestrator: Interactive multi-turn session management
- subagents: LLM-assisted helpers (ScenarioSubAgent, JudgeSubAgent, etc.)
- assertion_engine: Deterministic assertion evaluation (authoritative)
- diagnostic_engine: Deterministic diagnostic analysis (authoritative)
- scoring: Deterministic scoring and verdict (authoritative)
- agent_summary: Agent lifecycle eligibility (authoritative)
- scenario_service: CRUD for test scenarios
- orchestrator: Backward-compatible wrapper over execution_engine
"""
