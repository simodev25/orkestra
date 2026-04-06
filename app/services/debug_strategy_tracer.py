"""Debug Strategy Tracer — converts strategy debug JSON into OTLP spans for Grafana."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("orkestra.debug_strategy")

_tracing_initialized = False


def _ensure_tracing():
    global _tracing_initialized
    if _tracing_initialized:
        return
    _tracing_initialized = True
    try:
        from app.core.config import get_settings
        endpoint = get_settings().OTEL_ENDPOINT
        if not endpoint:
            return
        from agentscope.tracing import setup_tracing
        setup_tracing(endpoint=endpoint)
    except Exception:
        pass


def _truncate(s: str, max_len: int = 32000) -> str:
    return s[:max_len] if len(s) > max_len else s


def _safe_str(v: Any) -> str:
    if isinstance(v, str):
        return v
    return json.dumps(v, default=str)


def emit_debug_strategy_trace(data: dict) -> str:
    """Convert a debug-strategy JSON into OTLP spans and send to Tempo.

    Returns the trace ID.
    """
    _ensure_tracing()

    from opentelemetry import trace as otel_trace
    tracer = otel_trace.get_tracer("orkestra.debug_strategy")

    strategy_id = data.get("strategy_id", "unknown")
    status = data.get("status", "unknown")
    elapsed = data.get("elapsed_seconds", 0)
    inp = data.get("input", {})
    llm = data.get("llm", {})
    prompts = data.get("prompts", {})
    context = data.get("context", {})
    tools = data.get("tools", {})
    result = data.get("result", {})
    validation = data.get("validation", {})
    gen_opt = data.get("generation_optimization", {})
    strategy = data.get("strategy", {})
    prompt_history = data.get("prompt_history", [])

    # ── Root span ───────────────────────────────────────────────
    with tracer.start_as_current_span(
        "strategy_generation",
        attributes={
            "strategy.id": strategy_id,
            "strategy.status": status,
            "strategy.elapsed_seconds": elapsed,
            "strategy.pair": inp.get("pair", ""),
            "strategy.timeframe": inp.get("timeframe", ""),
            "strategy.template": result.get("template", ""),
            "strategy.name": result.get("name", ""),
            "gen_ai.system": llm.get("provider", ""),
            "gen_ai.request.model": llm.get("model", ""),
            "gen_ai.operation.name": "strategy_generation",
        },
    ) as root_span:

        # ── Prompts ─────────────────────────────────────────────
        with tracer.start_as_current_span(
            "prompts",
            attributes={
                "gen_ai.prompt.system": _truncate(prompts.get("system_prompt", "")),
                "gen_ai.prompt.system_length": len(prompts.get("system_prompt", "")),
                "gen_ai.prompt.user": _truncate(prompts.get("user_prompt", "")),
                "gen_ai.prompt.user_length": len(prompts.get("user_prompt", "")),
            },
        ):
            pass

        # ── Market context ──────────────────────────────────────
        with tracer.start_as_current_span(
            "market_context",
            attributes={
                "context.news_count": context.get("news_count", 0),
                "context.news_headlines": json.dumps(context.get("news_headlines", [])),
                "context.snapshot": json.dumps(context.get("snapshot", {})),
            },
        ):
            pass

        # ── Tool calls ──────────────────────────────────────────
        with tracer.start_as_current_span(
            "tool_calls",
            attributes={
                "tools.total_called": tools.get("total_called", 0),
                "tools.total_expected": tools.get("total_expected", 0),
                "tools.called": json.dumps(tools.get("called", [])),
                "tools.missing": json.dumps(tools.get("missing", [])),
            },
        ):
            # Individual tool invocations
            for tool_name, tool_data in data.get("tool_invocations", {}).items():
                with tracer.start_as_current_span(
                    f"tool:{tool_name}",
                    attributes={
                        "tool.name": tool_name,
                        "tool.input": _truncate(_safe_str(tool_data.get("input", ""))),
                        "tool.output": _truncate(_safe_str(tool_data.get("output", ""))),
                        "tool.duration_ms": tool_data.get("duration_ms", 0),
                    },
                ):
                    pass

        # ── LLM prompt history ──────────────────────────────────
        with tracer.start_as_current_span(
            "prompt_history",
            attributes={
                "prompt_history.message_count": len(prompt_history),
            },
        ):
            for i, msg in enumerate(prompt_history):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                with tracer.start_as_current_span(
                    f"message:{role}:{i}",
                    attributes={
                        "message.role": role,
                        "message.index": i,
                        "message.content": _truncate(content),
                        "message.content_length": len(content),
                    },
                ):
                    pass

        # ── Generation optimization / candidates ────────────────
        candidates = gen_opt.get("candidates", [])
        if candidates:
            with tracer.start_as_current_span(
                "generation_optimization",
                attributes={
                    "optimization.enabled": gen_opt.get("enabled", False),
                    "optimization.template_locked": gen_opt.get("template_locked", ""),
                    "optimization.selected_source": gen_opt.get("selected_source", ""),
                    "optimization.selected_score": gen_opt.get("selected_score", 0),
                    "optimization.candidate_count": len(candidates),
                },
            ):
                for cand in candidates:
                    metrics = cand.get("metrics", {})
                    with tracer.start_as_current_span(
                        f"candidate:{cand.get('source', 'unknown')}",
                        attributes={
                            "candidate.source": cand.get("source", ""),
                            "candidate.reason": _truncate(cand.get("reason", "")),
                            "candidate.params": json.dumps(cand.get("params", {})),
                            "candidate.generation_score": cand.get("generation_score", 0),
                            "candidate.total_trades": metrics.get("total_trades", 0),
                            "candidate.total_return_pct": metrics.get("total_return_pct", 0),
                            "candidate.sharpe_ratio": metrics.get("sharpe_ratio", 0),
                            "candidate.win_rate_pct": metrics.get("win_rate_pct", 0),
                            "candidate.profit_factor": metrics.get("profit_factor", 0),
                            "candidate.max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
                        },
                    ):
                        pass

        # ── Result / strategy ───────────────────────────────────
        with tracer.start_as_current_span(
            "strategy_result",
            attributes={
                "result.template": result.get("template", ""),
                "result.name": result.get("name", ""),
                "result.description": result.get("description", ""),
                "result.params": json.dumps(result.get("params", {})),
                "strategy.symbol": strategy.get("symbol", ""),
                "strategy.timeframe": strategy.get("timeframe", ""),
                "strategy.db_status": strategy.get("status", ""),
            },
        ):
            pass

        # ── Validation ──────────────────────────────────────────
        if validation:
            val_metrics = validation.get("metrics", {})
            with tracer.start_as_current_span(
                "validation",
                attributes={
                    "validation.score": validation.get("score", 0),
                    "validation.status": validation.get("status", ""),
                    "validation.raw_score": validation.get("raw_score", 0),
                    "validation.flags": json.dumps(validation.get("validation_flags", [])),
                    "validation.win_rate": val_metrics.get("win_rate", 0),
                    "validation.profit_factor": val_metrics.get("profit_factor", 0),
                    "validation.max_drawdown": val_metrics.get("max_drawdown", 0),
                    "validation.total_return": val_metrics.get("total_return", 0),
                    "validation.trades": val_metrics.get("trades", 0),
                    "validation.gate_passed": val_metrics.get("validation_gate_passed", False),
                },
            ):
                pass

        # ── Selection warnings ──────────────────────────────────
        warnings = data.get("selection_warnings", [])
        if warnings:
            root_span.set_attribute("strategy.warnings", json.dumps(warnings))
            root_span.set_attribute("strategy.warning_count", len(warnings))

        # ── Tags ────────────────────────────────────────────────
        tags = data.get("tags", [])
        if tags:
            root_span.set_attribute("strategy.tags", json.dumps(tags))

    # Flush
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush(timeout_millis=5000)
    except Exception:
        pass

    return strategy_id
