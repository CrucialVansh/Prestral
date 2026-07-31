from app.services.llm import _audience_system_prompt, normalize_audience


def test_normalize_audience_defaults() -> None:
    assert normalize_audience(None) == "general"
    assert normalize_audience("  ") == "general"
    assert normalize_audience("SWE") == "SWE"


def test_audience_presets_have_guidance() -> None:
    for key in ("general", "swe", "marketing", "executive"):
        text = _audience_system_prompt(key)
        assert "Audience" in text or "audience" in text.lower()


def test_free_text_audience() -> None:
    text = _audience_system_prompt("junior PM at a B2B SaaS startup")
    assert "junior PM" in text
