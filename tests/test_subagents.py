"""Tests for the Test Lab subagent builders."""

from __future__ import annotations

import pytest

from app.services.test_lab.subagents import (
    JudgeSubAgent,
    PolicySubAgent,
    RobustnessSubAgent,
    ScenarioSubAgent,
    SubAgentConfig,
    generate_follow_up_options,
)
from app.schemas.test_lab_session import FollowUpOption


# ---------------------------------------------------------------------------
# SubAgentConfig
# ---------------------------------------------------------------------------

def test_subagent_config_defaults():
    cfg = SubAgentConfig(name="Test", system_prompt="You are a tester.")
    assert cfg.temperature == 0.3
    assert cfg.max_tokens == 4096


def test_subagent_config_custom():
    cfg = SubAgentConfig(name="Custom", system_prompt="sys", temperature=0.7, max_tokens=1024)
    assert cfg.temperature == 0.7
    assert cfg.max_tokens == 1024


# ---------------------------------------------------------------------------
# ScenarioSubAgent
# ---------------------------------------------------------------------------

def test_scenario_subagent_name():
    assert ScenarioSubAgent.NAME == "ScenarioSubAgent"


def test_scenario_subagent_prompt():
    sa = ScenarioSubAgent()
    prompt = sa.build_prompt(
        agent_id="summary_agent",
        objective="Test COMEX cyber-risk summarization",
        context={"last_verdict": "failed", "last_score": 45.0},
    )
    assert "summary_agent" in prompt
    assert "COMEX" in prompt
    assert "failed" in prompt


def test_scenario_subagent_prompt_with_full_context():
    sa = ScenarioSubAgent()
    prompt = sa.build_prompt(
        agent_id="my_agent",
        objective="Check output quality",
        context={
            "last_verdict": "passed_with_warnings",
            "last_score": 70.0,
            "failed_assertions": [{"assertion_type": "tool_called"}],
            "diagnostics": [{"code": "slow_final_synthesis"}],
        },
    )
    assert "passed_with_warnings" in prompt
    assert "70.0" in prompt
    assert "tool_called" in prompt
    assert "slow_final_synthesis" in prompt


def test_scenario_subagent_prompt_no_context():
    sa = ScenarioSubAgent()
    prompt = sa.build_prompt(agent_id="agent_x", objective="Basic test")
    assert "agent_x" in prompt
    assert "Basic test" in prompt


def test_scenario_subagent_get_config():
    cfg = ScenarioSubAgent().get_config()
    assert isinstance(cfg, SubAgentConfig)
    assert cfg.name == "ScenarioSubAgent"
    assert cfg.temperature == 0.5


# ---------------------------------------------------------------------------
# JudgeSubAgent
# ---------------------------------------------------------------------------

def test_judge_subagent_name():
    assert JudgeSubAgent.NAME == "JudgeSubAgent"


def test_judge_subagent_prompt():
    sa = JudgeSubAgent()
    prompt = sa.build_prompt(
        verdict="passed",
        score=85.0,
        assertions_passed=3,
        assertions_total=3,
        diagnostics_count=0,
        agent_id="summary_agent",
    )
    assert "85.0" in prompt
    assert "passed" in prompt
    assert "summary_agent" in prompt
    assert "3/3" in prompt


def test_judge_subagent_prompt_failed():
    sa = JudgeSubAgent()
    prompt = sa.build_prompt(
        verdict="failed",
        score=30.0,
        assertions_passed=1,
        assertions_total=4,
        diagnostics_count=2,
        agent_id="risk_agent",
    )
    assert "failed" in prompt
    assert "30.0" in prompt
    assert "1/4" in prompt
    assert "2" in prompt


def test_judge_subagent_get_config():
    cfg = JudgeSubAgent().get_config()
    assert isinstance(cfg, SubAgentConfig)
    assert cfg.name == "JudgeSubAgent"
    assert cfg.temperature == 0.3


# ---------------------------------------------------------------------------
# RobustnessSubAgent
# ---------------------------------------------------------------------------

def test_robustness_subagent_name():
    assert RobustnessSubAgent.NAME == "RobustnessSubAgent"


def test_robustness_subagent_variant_types():
    expected_keys = {"ambiguous_input", "missing_data", "adversarial", "edge_case", "multilingual"}
    assert expected_keys == set(RobustnessSubAgent.VARIANT_TYPES.keys())


def test_robustness_subagent_prompt():
    sa = RobustnessSubAgent()
    prompt = sa.build_prompt(
        original_input="Summarize the COMEX report",
        original_verdict="passed",
        variant_type="ambiguous_input",
    )
    assert "ambiguous" in prompt.lower()
    assert "COMEX" in prompt


def test_robustness_subagent_prompt_edge_case_default():
    sa = RobustnessSubAgent()
    prompt = sa.build_prompt(
        original_input="Process this request",
        original_verdict="failed",
    )
    assert "edge_case" in prompt
    assert "Process this request" in prompt


def test_robustness_subagent_prompt_unknown_variant_falls_back():
    sa = RobustnessSubAgent()
    prompt = sa.build_prompt(
        original_input="Some input",
        original_verdict="passed",
        variant_type="totally_unknown_type",
    )
    # Falls back to edge_case description
    assert "Some input" in prompt


def test_robustness_subagent_get_config():
    cfg = RobustnessSubAgent().get_config()
    assert isinstance(cfg, SubAgentConfig)
    assert cfg.name == "RobustnessSubAgent"
    assert cfg.temperature == 0.6


# ---------------------------------------------------------------------------
# PolicySubAgent
# ---------------------------------------------------------------------------

def test_policy_subagent_name():
    assert PolicySubAgent.NAME == "PolicySubAgent"


def test_policy_subagent_prompt():
    sa = PolicySubAgent()
    prompt = sa.build_prompt(
        agent_id="summary_agent",
        forbidden_effects=["publish", "approve"],
        original_input="Summarize the report",
    )
    assert "publish" in prompt
    assert "approve" in prompt
    assert "summary_agent" in prompt
    assert "Summarize the report" in prompt


def test_policy_subagent_prompt_single_effect():
    sa = PolicySubAgent()
    prompt = sa.build_prompt(
        agent_id="risk_agent",
        forbidden_effects=["delete"],
        original_input="Analyse the risk",
    )
    assert "delete" in prompt
    assert "risk_agent" in prompt


def test_policy_subagent_get_config():
    cfg = PolicySubAgent().get_config()
    assert isinstance(cfg, SubAgentConfig)
    assert cfg.name == "PolicySubAgent"
    assert cfg.temperature == 0.3


# ---------------------------------------------------------------------------
# generate_follow_up_options
# ---------------------------------------------------------------------------

def test_follow_up_options_always_has_rerun_and_policy():
    options = generate_follow_up_options(
        verdict="passed",
        score=90.0,
        diagnostics=[],
        failed_assertions=[],
    )
    keys = [o.key for o in options]
    assert "rerun" in keys
    assert "policy" in keys


def test_follow_up_options_passed():
    options = generate_follow_up_options(
        verdict="passed",
        score=85.0,
        diagnostics=[{"code": "slow_final_synthesis", "severity": "warning"}],
        failed_assertions=[],
    )
    assert len(options) > 0
    keys = [o.key for o in options]
    assert "rerun" in keys
    assert "stricter" in keys
    assert "policy" in keys
    assert "performance" in keys


def test_follow_up_options_passed_with_warnings():
    options = generate_follow_up_options(
        verdict="passed_with_warnings",
        score=75.0,
        diagnostics=[],
        failed_assertions=[],
    )
    keys = [o.key for o in options]
    assert "stricter" in keys
    assert "robustness" in keys


def test_follow_up_options_failed_with_assertions():
    options = generate_follow_up_options(
        verdict="failed",
        score=35.0,
        diagnostics=[{"code": "expected_tool_not_used"}],
        failed_assertions=[{"assertion_type": "tool_called", "target": "search"}],
    )
    keys = [o.key for o in options]
    assert "targeted" in keys
    assert "tool_usage" in keys


def test_follow_up_options_no_stricter_when_failed():
    options = generate_follow_up_options(
        verdict="failed",
        score=20.0,
        diagnostics=[],
        failed_assertions=[],
    )
    keys = [o.key for o in options]
    assert "stricter" not in keys
    assert "robustness" not in keys


def test_follow_up_options_excessive_iterations_triggers_performance():
    options = generate_follow_up_options(
        verdict="failed",
        score=40.0,
        diagnostics=[{"code": "excessive_iterations", "severity": "warning"}],
        failed_assertions=[],
    )
    keys = [o.key for o in options]
    assert "performance" in keys


def test_follow_up_options_returns_follow_up_option_instances():
    options = generate_follow_up_options(
        verdict="passed",
        score=80.0,
        diagnostics=[],
        failed_assertions=[],
    )
    for opt in options:
        assert isinstance(opt, FollowUpOption)
        assert opt.key
        assert opt.label
        assert opt.description


def test_follow_up_options_targeted_label_includes_assertion_types():
    options = generate_follow_up_options(
        verdict="failed",
        score=50.0,
        diagnostics=[],
        failed_assertions=[
            {"assertion_type": "tool_called", "target": "search"},
            {"assertion_type": "output_field_exists", "target": "summary"},
        ],
    )
    targeted = next(o for o in options if o.key == "targeted")
    assert "tool_called" in targeted.label
    assert "output_field_exists" in targeted.label
