"""
Unit tests for the email pattern generator.

Run with: pytest tests/test_pattern_generator.py -v
"""

from app.core.pattern_generator import (
    generate_candidates,
    harvest_names,
    COMMON_PATTERNS,
)


# ── harvest_names tests

def test_harvests_basic_name_pair() -> None:
    """Should detect a basic capitalised name pair."""
    html = "<p>Contactar a Felipe Carvajal para más información.</p>"
    names = harvest_names(html)
    assert ("Felipe", "Carvajal") in names


def test_known_first_name_assigned_correctly() -> None:
    """Known Chilean first name should be assigned as first, not last."""
    html = "<p>Responsable: Felipe Muñoz</p>"
    names = harvest_names(html)
    assert ("Felipe", "Muñoz") in names


def test_ignores_single_word_names() -> None:
    """Single capitalised words should not produce name pairs."""
    html = "<p>Contacto: Chile</p>"
    names = harvest_names(html)
    assert len(names) == 0


def test_deduplicates_names() -> None:
    """Same name appearing twice should only be harvested once."""
    html = "<p>Felipe Carvajal y Felipe Carvajal</p>"
    names = harvest_names(html)
    assert names.count(("Felipe", "Carvajal")) == 1


def test_harvest_empty_html_returns_empty() -> None:
    """Empty HTML should return no names."""
    names = harvest_names("")
    assert names == []

# ── generate_candidates tests

def test_generates_first_dot_last() -> None:
    """Pattern {first}.{last} should produce felipe.carvajal@bhp.cl."""
    html = "<p>Felipe Carvajal</p>"
    candidates = generate_candidates(html, "{first}.{last}", "bhp.cl")
    assert "felipe.carvajal@bhp.cl" in candidates


def test_generates_initial_last() -> None:
    """Pattern {f}{last} should produce fcarvajal@bhp.cl."""
    html = "<p>Felipe Carvajal</p>"
    candidates = generate_candidates(html, "{f}{last}", "bhp.cl")
    assert "fcarvajal@bhp.cl" in candidates


def test_generates_first_initial_dot_last() -> None:
    """Pattern {f}.{last} should produce f.carvajal@bhp.cl."""
    html = "<p>Felipe Carvajal</p>"
    candidates = generate_candidates(html, "{f}.{last}", "bhp.cl")
    assert "f.carvajal@bhp.cl" in candidates


def test_strips_accents() -> None:
    """Accented characters should be normalised in output."""
    html = "<p>Andrés Muñoz</p>"
    candidates = generate_candidates(html, "{first}.{last}", "bhp.cl")
    assert "andres.munoz@bhp.cl" in candidates


def test_domain_with_at_prefix() -> None:
    """Target domain supplied with @ prefix should still work."""
    html = "<p>Felipe Carvajal</p>"
    candidates = generate_candidates(html, "{first}.{last}", "@bhp.cl")
    assert "felipe.carvajal@bhp.cl" in candidates


def test_candidates_empty_html_returns_empty() -> None:
    """Empty HTML should return no candidates."""
    candidates = generate_candidates("", "{first}.{last}", "bhp.cl")
    assert candidates == []


def test_deduplicates_candidates() -> None:
    """Same name twice should produce only one candidate."""
    html = "<p>Felipe Carvajal y Felipe Carvajal</p>"
    candidates = generate_candidates(html, "{first}.{last}", "bhp.cl")
    assert candidates.count("felipe.carvajal@bhp.cl") == 1


# ── COMMON_PATTERNS tests

def test_common_patterns_not_empty() -> None:
    """COMMON_PATTERNS should have at least 5 presets."""
    assert len(COMMON_PATTERNS) >= 5


def test_common_patterns_have_required_keys() -> None:
    """Each preset should have label and pattern keys."""
    for preset in COMMON_PATTERNS:
        assert "label" in preset
        assert "pattern" in preset