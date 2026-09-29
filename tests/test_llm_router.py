"""
Test Suite: Multi-Provider LLM Router & Smart Switching
Verifies:
1. Provider auto-detection based on API keys and environment variables.
2. Cascading failover when primary provider fails (e.g. Rate Limit / 429).
3. Graceful offline fallback to deterministic regex/heuristic engine when no remote keys are present.
4. Parsing into valid EngineeringModel objects with SI units and mechanical features.
"""

import os
from unittest.mock import patch, MagicMock
import pytest
from mdie.ai.llm_router import LLMRouter
from mdie.ai.parser import NLParser


def test_provider_auto_detection():
    """Verify that provider list respects configured environment keys and custom priority."""
    with patch.dict(os.environ, {}, clear=True):
        assert LLMRouter.get_configured_providers() == []

    # Individual key detection
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test123"}, clear=True):
        assert LLMRouter.get_configured_providers() == ["groq"]

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-test"}, clear=True):
        assert LLMRouter.get_configured_providers() == ["openrouter"]

    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyTest"}, clear=True):
        assert LLMRouter.get_configured_providers() == ["gemini"]

    # Multiple keys default priority: groq -> openrouter -> gemini
    with patch.dict(os.environ, {
        "GROQ_API_KEY": "gsk_test",
        "OPENROUTER_API_KEY": "sk-or-test",
        "GEMINI_API_KEY": "AIza_test"
    }, clear=True):
        assert LLMRouter.get_configured_providers() == ["groq", "openrouter", "gemini"]

    # Explicit override via MDIE_LLM_PROVIDER
    with patch.dict(os.environ, {
        "GROQ_API_KEY": "gsk_test",
        "OPENROUTER_API_KEY": "sk-or-test",
        "MDIE_LLM_PROVIDER": "openrouter,groq"
    }, clear=True):
        assert LLMRouter.get_configured_providers() == ["openrouter", "groq"]


def test_cascading_failover():
    """Verify that if Groq hits 429 rate limit, it automatically cascades to OpenRouter."""
    with patch.dict(os.environ, {
        "GROQ_API_KEY": "gsk_test",
        "OPENROUTER_API_KEY": "sk-or-test"
    }, clear=True):
        # Mock _call_groq to fail with rate limit, and _call_openrouter to succeed
        with patch.object(LLMRouter, "_call_groq", side_effect=RuntimeError("HTTP 429: Rate limit reached")):
            with patch.object(LLMRouter, "_call_openrouter", return_value='{"name": "Shaft", "total_length": 0.5}'):
                text, provider, logs = LLMRouter.call_chat_completion(
                    system_prompt="Test system",
                    user_prompt="stepped shaft 500 mm"
                )
                assert text is not None
                assert provider == "openrouter"
                assert any("Rate limit reached" in l for l in logs)
                assert any("Successfully received response from 'OPENROUTER'" in l for l in logs)


def test_offline_deterministic_fallback():
    """When all providers fail or no keys exist, NLParser cleanly executes offline heuristics."""
    from mdie.physics.solver import PhysicsSolver
    with patch.dict(os.environ, {}, clear=True):
        model, logs = NLParser.parse("stepped shaft 600 mm long, 25 kW at 1800 rpm")
        assert model is not None
        assert abs(model.total_length - 0.600) < 1e-4
        assert model.power_watts == 25000.0
        assert model.speed_rpm == 1800.0
        res = PhysicsSolver.solve(model)
        assert res.applied_torque_nm > 100.0  # P / omega ~ 132.6 N*m
        assert any("deterministic" in l.lower() or "offline" in l.lower() for l in logs)



def test_llm_json_construction():
    """Verify that raw JSON response from any LLM is accurately parsed into an EngineeringModel."""
    sample_json = {
        "name": "Heavy Duty Transmission Shaft",
        "component_type": "shaft",
        "total_length": 0.750,
        "power_watts": 45000.0,
        "speed_rpm": 1200.0,
        "torque_nm": 358.1,
        "material_id": "AISI_4140_QT",
        "segments": [
            {
                "start_pos": 0.0,
                "end_pos": 0.150,
                "outer_diameter": 0.040,
                "inner_diameter": 0.0,
                "feature_type": "bearing_seat",
                "keyway": None
            },
            {
                "start_pos": 0.150,
                "end_pos": 0.600,
                "outer_diameter": 0.055,
                "inner_diameter": 0.0,
                "feature_type": "gear_mount",
                "keyway": {
                    "position": 0.300,
                    "length": 0.060,
                    "width": 0.012,
                    "depth": 0.005
                }
            },
            {
                "start_pos": 0.600,
                "end_pos": 0.750,
                "outer_diameter": 0.040,
                "inner_diameter": 0.0,
                "feature_type": "bearing_seat",
                "keyway": None
            }
        ],
        "supports": [
            {"name": "Bearing Left", "support_type": "bearing", "position": 0.075},
            {"name": "Bearing Right", "support_type": "bearing", "position": 0.675}
        ],
        "point_loads": [
            {"name": "Gear Radial Load", "magnitude": 6500.0, "position": 0.375}
        ]
    }

    model = NLParser._build_model_from_json(sample_json, provider_name="groq")
    assert model.name == "Heavy Duty Transmission Shaft"
    assert model.total_length == 0.750
    assert len(model.segments) == 3
    assert model.segments[1].keyway is not None
    assert model.segments[1].keyway.position == 0.300
    assert len(model.supports) == 2
    assert len(model.point_loads) == 1
    assert model.point_loads[0].magnitude == 6500.0
    assert model.metadata.get("source") == "groq"
