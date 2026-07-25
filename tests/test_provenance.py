"""
Unit tests for the Chilean-evidence signals.

Every case here is a fixture, not a live fetch: these assert what the code
does, not what a stranger's website still says today. Run with:
pytest tests/test_provenance.py -v
"""

from app.core.provenance import chile_evidence


def test_lang_es_cl() -> None:
    """A page declaring es-CL fires lang-es-cl."""
    html = '<html lang="es-CL"><body><p>Bienvenidos</p></body></html>'
    assert 'lang-es-cl' in chile_evidence(html, 'https://empresa.com')


def test_lang_es_alone_does_not_fire() -> None:
    """Bare es is not es-CL - most Chilean sites declare only es."""
    html = '<html lang="es"><body><p>Bienvenidos</p></body></html>'
    assert 'lang-es-cl' not in chile_evidence(html, 'https://empresa.com')


def test_valid_rut_fires() -> None:
    """A RUT with a correct check digit fires rut."""
    html = '<html><body><p>RUT 76.086.428-5</p></body></html>'
    assert 'rut' in chile_evidence(html, 'https://empresa.com')


def test_rut_with_wrong_check_digit_does_not_fire() -> None:
    """The check digit is the whole point: a malformed RUT is not evidence."""
    html = '<html><body><p>76.086.428-1</p></body></html>'
    assert 'rut' not in chile_evidence(html, 'https://empresa.com')


def test_chilean_phone_without_country_code_fires() -> None:
    """A Santiago landline written the way Chilean sites write it."""
    html = '<html><body><p>Fono: 22 818 5000</p></body></html>'
    assert 'phone-cl' in chile_evidence(html, 'https://empresa.com')


def test_foreign_phone_does_not_fire() -> None:
    """An explicit foreign country code is rejected, not reinterpreted."""
    html = '<html lang="en"><body><p>Call +1 604 699 4000</p></body></html>'
    assert 'phone-cl' not in chile_evidence(html, 'https://company.com')


def test_us_zip_plus_four_is_not_a_chilean_phone() -> None:
    """
    Measured false positive: teck.com lists `Spokane, WA 99201-0301`, and
    libphonenumber accepts those nine digits as a Chilean mobile.
    """
    html = (
        '<html lang="en"><body><p>601 West Riverside Avenue, Suite 258, '
        'Spokane, WA 99201-0301, United States</p></body></html>'
    )
    assert 'phone-cl' not in chile_evidence(html, 'https://company.com')


def test_lexicon_fires_on_institutional_vocabulary() -> None:
    """Chilean institutional words, not place names."""
    html = '<html><body><p>Casilla 150, comuna de Providencia</p></body></html>'
    assert 'lexicon' in chile_evidence(html, 'https://empresa.com')


def test_country_path_segment_fires() -> None:
    """Multinationals encode country in the path, not the host."""
    html = '<html><body><p>Tienda</p></body></html>'
    assert 'path-cl' in chile_evidence(html, 'https://falabella.com/falabella-cl')


def test_foreign_corporate_page_returns_nothing() -> None:
    """The control: an English corporate page yields no evidence at all."""
    html = (
        '<html lang="en"><head><title>Global Mining</title></head>'
        '<body><p>Our operations span four continents.</p></body></html>'
    )
    assert chile_evidence(html, 'https://company.com/about') == ()


def test_chilean_place_names_alone_are_not_evidence() -> None:
    """
    Measured false positive: teck.com names Iquique and Las Condes.

    Place-name and comuna-gazetteer matching were both excluded from the
    cascade for this reason (ADR-0014). A page whose only Chilean content
    is a list of place names must return nothing.
    """
    html = (
        '<html lang="en"><body><p>Our offices in Iquique and Las Condes, '
        'Chile, support operations in Santiago and Antofagasta.</p></body></html>'
    )
    assert chile_evidence(html, 'https://company.com/contact') == ()


def test_hreflang_es_cl_alone_is_not_evidence() -> None:
    """
    Measured false positive: the only site declaring hreflang es-CL in the
    sample was albemarle.com, a US company. Serving Chile is not being
    Chilean, so hreflang is not in the cascade.
    """
    html = (
        '<html lang="en"><head>'
        '<link rel="alternate" hreflang="es-CL" href="https://company.com/cl">'
        '</head><body><p>Global operations</p></body></html>'
    )
    assert chile_evidence(html, 'https://company.com/') == ()


def test_signals_are_sorted_and_deduplicated() -> None:
    """Result is a stable sorted tuple, so callers can compare it directly."""
    html = (
        '<html lang="es-CL"><body>'
        '<p>RUT 76.086.428-5 - Casilla 150 - Fono 22 818 5000</p>'
        '</body></html>'
    )
    assert chile_evidence(html, 'https://empresa.com/es-cl') == (
        'lang-es-cl', 'lexicon', 'path-cl', 'phone-cl', 'rut'
    )
