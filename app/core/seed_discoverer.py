"""
Seed discoverer.

Generates 10-20 high-quality seed URLs from a single target domain
using a cascading, self-improving pipeline:

  1. crt.sh Certificate Transparency logs
     → reveals every subdomain that ever had an SSL cert issued
     → 1 request per session, no API key, no registration

  2. DNS verification
     → confirms which discovered subdomains are actually alive
     → fully local, no external dependency

  3. Entity-aware semantic path scoring
     → fetches homepage of each live subdomain
     → scores every internal link by email-hunting relevance
     → scoring table adapts to entity type

  4. Known high-value Chilean sources per entity type
     → transparencia.cl, munitel.cl, subdere.gov.cl etc.
     → always included, no user action required

  5. DuckDuckGo search (optional)
     → targeted queries built from confirmed live subdomains
     → fills remaining seed slots

Silent failure on every stage — if a source fails, the next runs.
Seeds can be on any domain — email filter in crawler enforces .cl target.
"""

import asyncio
import re
import socket
from enum import Enum, auto
from urllib.parse import urljoin, urlparse, quote

import httpx
from bs4 import BeautifulSoup


# ── Entity types

class EntityType(Enum):
    """Detected type of the target organisation."""
    MUNICIPALITY = auto()
    GOVERNMENT   = auto()
    UNIVERSITY   = auto()
    COMPANY      = auto()


_ENTITY_PATTERNS: dict[EntityType, list[str]] = {
    EntityType.MUNICIPALITY: [
        'muni', 'municipio', 'ilustre', 'alcald',
        'gore', 'gobernacion', 'delegacion',
    ],
    EntityType.GOVERNMENT: [
        'gob', 'gov', 'minsal', 'minedu', 'servel',
        'sii', 'registro', 'seremi', 'intendencia',
        'ministerio', 'subsecretaria', 'dipres',
        'contraloria', 'senado', 'camara',
    ],
    EntityType.UNIVERSITY: [
        'edu', 'univ', 'uc', 'udp', 'usach', 'uach',
        'ubb', 'ufro', 'utalca', 'ucn', 'uai', 'udd',
        'pucv', 'ucsc', 'ulagos', 'umag', 'uantof',
    ],
}

# Full list of Chilean municipality domains from Lupa Municipal 2026
_CL_MUNICIPALITIES: set[str] = {
    "municipalidadalgarrobo.cl", "municipalidadalhue.cl", "munialtobiobio.cl",
    "munialtodelcarmen.cl", "maho.cl", "muniancud.cl", "andacollochile.cl",
    "angol.cl", "municipalidadantofagasta.cl", "municipalidadantuco.cl",
    "muniarauco.cl", "muniarica.cl", "puertoaysen.cl", "buin.cl", "imb.cl",
    "municipiocabildo.cl", "imcabodehornos.cl", "cabrero.cl",
    "municipalidadcalama.cl", "municipalidadcalbuco.cl", "caldera.cl",
    "municaleradetango.cl", "municallelarga.cl", "municamarones.cl",
    "municipalidaddecamina.cl", "canela.cl", "municanete.cl", "carahue.cl",
    "municipalidaddecartagena.cl", "municipalidadcasablanca.cl",
    "castromunicipio.cl", "municatemu.cl", "cauquenes.cl", "mcerrillos.cl",
    "cerronavia.cl", "municipalidadchaiten.cl", "munichanaral.cl", "chanco.cl",
    "municipalidadchepica.cl", "chiguayante.cl", "chilechico.cl",
    "municipalidadchillan.cl", "chillanviejo.cl", "municipalidadchimbarongo.cl",
    "municholchol.cl", "municipalidadchonchi.cl", "municipalidadcisnes.cl",
    "cobquecura.cl", "municochamo.cl", "municochrane.cl",
    "municipalidaddecodegua.cl", "municipalidaddecoelemu.cl", "coyhaique.cl",
    "municoihueco.cl", "municoinco.cl", "municipalidadcolbun.cl", "imcolchane.cl",
    "colina.cl", "municipalidadcollipulli.cl", "coltauco.cl", "combarbala.cl",
    "concepcion.cl", "conchali.cl", "concon.cl", "constitucion.cl",
    "contulmo.cl", "copiapo.cl", "municoquimbo.cl", "coronel.cl",
    "municipalidadcorral.cl", "municunco.cl", "mcuracautin.cl",
    "municipalidadcuracavi.cl", "curacodevelez.cl", "munichue.cl",
    "curarrehue.cl", "curepto.cl", "curico.cl", "munidalcahue.cl", "imda.cl",
    "mdonihue.cl", "municipalidadelbosque.cl", "municipalidadelcarmen.cl",
    "munielmonte.cl", "elquisco.cl", "eltabo.cl", "empedrado.cl",
    "muniercilla.cl", "municipalidaddeestacioncentral.cl", "muniflorida.cl",
    "munifreire.cl", "imfreirina.cl", "munifresia.cl", "munifrutillar.cl",
    "futaleufu.cl", "munifutrono.cl", "galvarinochile.cl", "portalvisviri.cl",
    "municipalidadgorbea.cl", "municipalidadgraneros.cl", "muniguaitecas.cl",
    "hijuelas.cl", "municipalidadhualaihue.cl", "hualane.cl",
    "hualpenciudad.cl", "munihualqui.cl", "imhuara.cl", "imhuasco.cl",
    "huechuraba.cl", "municipalidadillapel.cl", "independencia.cl",
    "municipioiquique.cl", "islademaipo.cl", "rapanui.net",
    "comunajuanfernandez.cl", "lacalera.cl", "cisterna.cl", "lacruz.cl",
    "munilaestrella.cl", "laflorida.cl", "municipalidadlagranja.cl",
    "munilahiguera.cl", "laligua.cl", "pintana.cl", "lareina.cl",
    "laserena.cl", "munilaunioninfo.com", "municipalidadlagoranco.cl",
    "lagoverdeaysen.cl", "mlagunablanca.cl", "munilaja.cl", "lampa.cl",
    "munilanco.cl", "lascabrasmunicipalidad.cl", "lascondes.cl",
    "munilautaro.cl", "lebu.cl", "mlicanten.cl", "limache.cl",
    "corporacionlinares.cl", "litueche.cl", "llanquihue.cl",
    "municipalidadllayllay.cl", "lobarnechea.cl", "loespejo.cl", "loprado.cl",
    "munilolol.cl", "municipalidaddeloncoche.cl", "municipalidadlongavi.cl",
    "mlonquimay.cl", "municipalidadlosalamos.cl", "losandes.cl",
    "losangeles.cl", "muniloslagos.cl", "muermos.cl", "munilossauces.com",
    "munilosvilos.cl", "lota.cl", "munilumaco.cl", "machali.cl",
    "munimacul.cl", "munimafil.cl", "municipalidadmaipu.cl",
    "comunamalloa.cl", "marchigue.cl", "imme.cl", "mpinto.cl",
    "munimariquina.cl", "comunademaule.cl", "munimaullin.cl", "mejillones.cl",
    "melipeuko.cl", "melipilla.cl", "web.molina.cl", "munimontepatria.cl",
    "mostazal.cl", "munimulchen.cl", "nacimiento.cl",
    "municipalidadnancagua.cl", "muninatales.cl", "muninavidad.cl",
    "muninegrete.cl", "muniniquen.cl", "munininhue.cl", "muninogales.cl",
    "nuevaimperial.cl", "nunoa.cl", "municipalidadohiggins.cl",
    "muniolivar.cl", "municipalidadollague.cl", "muniolmue.cl",
    "municipalidadosorno.cl", "municipalidadovalle.cl", "mph.cl",
    "padrelascasas.cl", "municipalidaddepaihuano.cl", "munipaillaco.cl",
    "paine.cl", "municipalidadpalena.cl", "munipalmilla.cl",
    "municipalidadpanguipulli.cl", "impanquehue.cl", "municipalidadpapudo.cl",
    "comunaparedones.cl", "parral.cl", "pedroaguirrecerda.cl", "pelarco.cl",
    "munipelluhue.cl", "munipemuco.cl", "penaflor.cl", "penalolen.cl",
    "mpencahue.cl", "penco.cl", "muniperalillo.cl", "perquenco.cl",
    "munipetorca.com", "mpeumo.cl", "municipalidadpica.cl", "pichidegua.cl",
    "pichilemu.cl", "municipalidaddepinto.cl", "pirque.cl", "mpitrufquen.cl",
    "muniplacilla.cl", "municipalidaddeportezuelo.cl", "muniporvenir.cl",
    "impa.gob.cl", "municipalidaddeprimavera.cl", "providencia.cl",
    "munipuchuncavi.cl", "municipalidadpucon.cl", "mpudahuel.cl",
    "mpuentealto.cl", "puertomontt.cl", "munipuertoctay.cl", "ptovaras.cl",
    "munipumanque.cl", "munipunitaqui.cl", "puntaarenas.cl",
    "munipuqueldon.cl", "munipuren.cl", "purranque.cl", "putaendo.cl",
    "imputre.cl", "municipalidaddepuyehue.cl", "muniqueilen.cl",
    "muniquellon.cl", "muniquemchi.cl", "municipalidadquilaco.cl",
    "muniquilicura.cl", "municipalidadquilleco.cl", "quillota.cl",
    "quilpue.cl", "municipalidadquinchao.cl", "quintadetilcoco.cl",
    "quintanormal.cl", "muniquintero.cl", "municipalidadquirihue.cl",
    "rancagua.cl", "municipalidadranquil.cl", "munirauco.cl", "recoleta.cl",
    "renaico.cl", "renca.cl", "municipalidadrengo.cl", "requinoa.cl",
    "retiro.cl", "munirinconada.cl", "municipalidadderiobueno.cl",
    "rioclaro.cl", "riohurtado.cl", "rioibanez.cl", "rionegrochile.cl",
    "rioverde.cl", "muniromeral.cl", "municipiodesaavedra.cl",
    "sagradafamilia.cl", "salamanca.cl", "sanantonio.cl", "sanbernardo.cl",
    "sancarlos.cl", "sanclemente.cl", "munisanesteban.cl", "sanfabian.cl",
    "munisanfelipe.cl", "munisanfernando.cl", "sangregorio.cl",
    "munisanignacio.cl", "imsanjavier.cl", "redsanjoaquin.cl",
    "sanjosedemaipo.cl", "sanjuandelacosta.cl", "sanmiguel.cl",
    "municipalidadsannicolas.cl", "sanpablo.cl", "munisanpedro.cl",
    "sanpedroatacama.com", "sanpedrodelapaz.cl", "munisanrafael.cl",
    "municipalidadsanramon.cl", "municipalidadsanrosendo.cl",
    "municipalidadsanvicente.cl", "santabarbara.cl",
    "municipalidadsantacruz.cl", "santajuana.cl", "imsantamaria.com",
    "munistgo.cl", "santodomingo.cl", "municipalidadsierragorda.cl",
    "munitalagante.cl", "talca.cl", "talcahuano.cl", "municipalidadtaltal.cl",
    "temuco.cl", "teno.cl", "muniteodoro.cl", "tierramarilla.com", "tiltil.cl",
    "municipalidadtimaukel.cl", "munitirua.com", "imtocopilla.cl", "tolten.cl",
    "tome.cl", "torresdelpayne.cl", "municipalidaddetortel.cl",
    "mtraiguen.cl", "trehuaco.com", "municipalidadtucapel.cl",
    "munivaldivia.cl", "vallenar.cl", "web.municipalidaddevalparaiso.cl",
    "munivichuquen.cl", "victoriachile.cl", "municipalidadvicuna.cl",
    "vilcun.cl", "villalegre.cl", "villalemana.cl", "villarrica.org",
    "vinadelmarchile.cl", "vitacura.cl", "muniyerbasbuenas.cl", "yumbel.cl",
    "yungay.cl", "munizapallar.cl",
}

# Known high-value Chilean sources per entity type
# These are always included regardless of what other stages find
_KNOWN_SOURCES: dict[EntityType, list[str]] = {
    EntityType.MUNICIPALITY: [
        'https://www.transparencia.cl',
        'https://www.munitel.cl',
        'https://www.subdere.gov.cl',
    ],
    EntityType.GOVERNMENT: [
        'https://www.transparencia.cl',
        'https://www.bcn.cl',
    ],
    EntityType.UNIVERSITY: [
        'https://www.cna.cl',
        'https://www.mifuturo.cl',
    ],
    EntityType.COMPANY: [
        'https://www.cmfchile.cl',
        'https://www.fach.cl',
    ],
}

# Base scores apply to all entity types
_BASE_SCORES: dict[str, int] = {
    'contacto':       10,
    'contact':        10,
    'directorio':     10,
    'staff':           9,
    'equipo':          8,
    'team':            8,
    'nosotros':        7,
    'about':           7,
    'quienes':         7,
    'personal':        5,
    'people':          5,
    'email':           5,
    'correo':          5,
}

# Entity-specific scores on top of base
_ENTITY_SCORES: dict[EntityType, dict[str, int]] = {
    EntityType.MUNICIPALITY: {
        'funcionarios':   10,
        'organigrama':     9,
        'transparencia':   9,
        'autoridades':     8,
        'alcaldia':        8,
        'concejo':         7,
        'secretaria':      7,
        'corporacion':     6,
        'direccion':       6,
        'departamento':    6,
        'unidades':        5,
        'oficinas':        5,
        'programas':       3,
        'servicios':       3,
        'tramites':        3,
    },
    EntityType.GOVERNMENT: {
        'funcionarios':   10,
        'organigrama':     9,
        'transparencia':   9,
        'autoridades':     8,
        'estructura':      7,
        'departamento':    6,
        'oficinas':        5,
        'servicios':       3,
    },
    EntityType.UNIVERSITY: {
        'academicos':     10,
        'facultad':        9,
        'departamento':    8,
        'escuelas':        7,
        'investigacion':   6,
        'postgrado':       6,
        'autoridades':     7,
        'decano':          8,
        'rector':          8,
        'carreras':        4,
    },
    EntityType.COMPANY: {
        'ejecutivos':      9,
        'directiva':       9,
        'liderazgo':       9,
        'leadership':      9,
        'management':      8,
        'gerencia':        8,
        'gerentes':        8,
        'empresa':         5,
        'organizacion':    5,
        'socios':          6,
        'partners':        6,
        'investors':       4,
        'relaciones':      4,
    },
}

_MIN_SCORE = 3

# DuckDuckGo queries per entity type
_DDG_QUERIES: dict[EntityType, list[str]] = {
    EntityType.MUNICIPALITY: [
        '"{domain}" directorio funcionarios email',
        '"{domain}" transparencia contacto correo',
        'site:{bare} correo email contacto funcionario',
    ],
    EntityType.GOVERNMENT: [
        '"{domain}" directorio funcionarios email',
        'site:{bare} correo contacto email autoridades',
    ],
    EntityType.UNIVERSITY: [
        '"{domain}" directorio academicos email',
        'site:{bare} correo email contacto facultad',
    ],
    EntityType.COMPANY: [
        '"{domain}" equipo directivo email contacto',
        'site:{bare} correo email staff ejecutivos',
        '"{domain}" contacto ejecutivos email',
    ],
}


def detect_entity_type(domain: str) -> EntityType:
    """
    Detect the entity type from the domain name.

    Checks against the full Lupa Municipal 2026 list first,
    then falls back to keyword matching for other entity types.

    Parameters
    ----------
    domain : str
        Bare domain e.g. 'nunoa.cl' or 'bhp.cl'.

    Returns
    -------
    EntityType
    """
    domain_lower = domain.lower().strip()

    # Check exact match against known municipality list first
    if domain_lower in _CL_MUNICIPALITIES:
        return EntityType.MUNICIPALITY

    # Keyword matching for other entity types
    for entity_type, keywords in _ENTITY_PATTERNS.items():
        if any(kw in domain_lower for kw in keywords):
            return entity_type

    return EntityType.COMPANY  # Default to company if no other type matches


def _score_link(href: str, entity_type: EntityType) -> int:
    """
    Score a link path by email-hunting relevance for the entity type.

    Combines base scores (universal) with entity-specific scores,
    taking the maximum match found.

    Parameters
    ----------
    href : str
        URL or path to score.
    entity_type : EntityType

    Returns
    -------
    int
        Relevance score. 0 = not useful.
    """
    path = href.lower()
    score = 0

    for keyword, value in _BASE_SCORES.items():
        if keyword in path:
            score = max(score, value)

    for keyword, value in _ENTITY_SCORES.get(entity_type, {}).items():
        if keyword in path:
            score = max(score, value)

    return score


async def _crtsh_subdomains(
    domain: str,
    client: httpx.AsyncClient,
) -> list[str]:
    """
    Query crt.sh Certificate Transparency logs for subdomains.

    One request per session. Returns every subdomain that ever
    had an SSL certificate issued.

    Parameters
    ----------
    domain : str
        Bare domain e.g. 'nunoa.cl'.
    client : httpx.AsyncClient

    Returns
    -------
    list[str]
        Unique subdomain hostnames.
    """
    subdomains: list[str] = []
    seen: set[str] = set()

    try:
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        resp = await client.get(url, timeout=30.0)
        if resp.status_code != 200:
            return []

        records = resp.json()
        for record in records:
            for name in record.get('name_value', '').splitlines():
                name = name.strip().lower()
                if '*' in name or not name.endswith(domain):
                    continue
                if name not in seen:
                    seen.add(name)
                    subdomains.append(name)

    except Exception:
        pass

    return subdomains


async def _verify_subdomains(
    subdomains: list[str],
    client: httpx.AsyncClient,
) -> list[str]:
    """
    Verify which subdomains are alive via DNS + HTTP HEAD.

    Parameters
    ----------
    subdomains : list[str]
        Hostnames to check.
    client : httpx.AsyncClient

    Returns
    -------
    list[str]
        Live URLs (https://{subdomain}) that responded.
    """
    async def probe(host: str) -> str | None:
        """Return https URL if host resolves and responds, else None."""
        try:
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, socket.gethostbyname, host
                ),
                timeout=5.0,
            )
            url = f"https://{host}"
            resp = await client.head(url, timeout=8.0)
            if resp.status_code < 500:
                return url
        except Exception:
            pass
        return None

    results = await asyncio.gather(*[probe(sub) for sub in subdomains])
    return [r for r in results if r]


async def _semantic_seeds_from_url(
    base_url: str,
    domain: str,
    entity_type: EntityType,
    client: httpx.AsyncClient,
) -> list[tuple[int, str]]:
    """
    Fetch a page and return scored internal links likely to have emails.

    Parameters
    ----------
    base_url : str
        URL to fetch and analyse.
    domain : str
        Target domain — only keep links mentioning this domain.
    entity_type : EntityType
        Used to select the appropriate scoring table.
    client : httpx.AsyncClient

    Returns
    -------
    list[tuple[int, str]]
        (score, url) pairs, highest scores first.
    """
    scored: list[tuple[int, str]] = []

    try:
        resp = await client.get(base_url, timeout=10.0)
        if resp.status_code >= 400:
            return []

        soup = BeautifulSoup(resp.text, 'lxml')
        base_host = urlparse(base_url).netloc.lower()

        for tag in soup.find_all('a', href=True):
            href = str(tag['href']).strip()
            full = urljoin(base_url, href)
            parsed = urlparse(full)

            if parsed.scheme not in ('http', 'https'):
                continue

            host = parsed.netloc.lower()

            # For known sources: keep any link mentioning the target domain
            # For target domain pages: keep only internal links
            is_known_source = base_host not in domain
            if is_known_source:
                if domain not in full.lower():
                    continue
            else:
                if domain not in host:
                    continue

            score = _score_link(full, entity_type)
            if score >= _MIN_SCORE:
                scored.append((score, full))

    except Exception:
        pass

    seen: set[str] = set()
    unique: list[tuple[int, str]] = []
    for score, url in sorted(scored, reverse=True):
        if url not in seen:
            seen.add(url)
            unique.append((score, url))

    return unique


async def _duckduckgo_seeds(
    domain: str,
    live_urls: list[str],
    entity_type: EntityType,
    client: httpx.AsyncClient,
) -> list[str]:
    """
    Run targeted DuckDuckGo searches using confirmed live subdomains.

    Parameters
    ----------
    domain : str
    live_urls : list[str]
        Confirmed live subdomain URLs to include in queries.
    entity_type : EntityType
    client : httpx.AsyncClient

    Returns
    -------
    list[str]
        URLs extracted from search results.
    """
    urls: list[str] = []
    url_re = re.compile(r'https?://[a-zA-Z0-9.\-]+\.cl[^\s"<>]*')
    queries = _DDG_QUERIES.get(
        entity_type, _DDG_QUERIES[EntityType.COMPANY]
    )

    extra = [
        f'site:{urlparse(u).netloc} email correo contacto'
        for u in live_urls[:3]
    ]

    for query_template in queries + extra:
        query = query_template.format(
            domain=f"@{domain}", bare=domain
        )
        try:
            resp = await client.get(
                f"https://html.duckduckgo.com/html/?q={quote(query)}",
                timeout=10.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )
            for match in url_re.finditer(resp.text):
                url = match.group()
                if domain in url and url not in urls:
                    urls.append(url)
        except Exception:
            continue

    return urls


async def discover_seeds(
    domain: str,
    use_duckduckgo: bool = True,
    max_seeds: int = 20,
) -> list[str]:
    """
    Discover seed URLs for a target domain using cascading strategies.

    Pipeline
    --------
    1. crt.sh → real subdomains from SSL certificate logs
    2. DNS verification → confirm which subdomains are alive
    3. Semantic scoring → score internal links on live pages
    4. Known Chilean sources → transparencia.cl, munitel.cl etc.
    5. DuckDuckGo (optional) → targeted queries using live subdomains

    Seeds can be on any domain — the crawler's email filter
    enforces the .cl target pattern regardless of seed origin.

    Parameters
    ----------
    domain : str
        Bare domain or @-prefixed e.g. 'nunoa.cl' or '@nunoa.cl'.
    use_duckduckgo : bool
        If True, include DuckDuckGo search results.
    max_seeds : int
        Maximum number of seeds to return.

    Returns
    -------
    list[str]
        Deduplicated seed URLs, best sources first.
    """
    domain = domain.lstrip('@').lower().strip()
    entity_type = detect_entity_type(domain)
    seeds: list[str] = []
    seen: set[str] = set()

    def add(urls: list[str]) -> None:
        """Add URLs to seeds, deduplicating."""
        for url in urls:
            url = url.rstrip('/')
            if url and url not in seen:
                seen.add(url)
                seeds.append(url)

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "RadarCL/0.1"},
    ) as client:

        # Stage 1: crt.sh — get real subdomains
        subdomains = await _crtsh_subdomains(domain, client)

        # Always include base and www
        for base in [domain, f"www.{domain}"]:
            if base not in subdomains:
                subdomains.insert(0, base)

        # Stage 2: DNS verification — confirm live subdomains
        live_urls = await _verify_subdomains(subdomains, client)
        add(live_urls)

        # Stage 3: Semantic scoring on live target pages
        scored_links: list[tuple[int, str]] = []
        for base_url in live_urls[:10]:
            links = await _semantic_seeds_from_url(
                base_url, domain, entity_type, client
            )
            scored_links.extend(links)

        scored_links.sort(reverse=True)
        add([url for _, url in scored_links])

        # Stage 4: Known high-value Chilean sources
        known = _KNOWN_SOURCES.get(entity_type, [])
        for source_url in known:
            # Always add the source itself as a seed
            add([source_url])
            # Score its links for target domain mentions
            links = await _semantic_seeds_from_url(
                source_url, domain, entity_type, client
            )
            scored_links = sorted(links, reverse=True)
            add([url for _, url in scored_links])

        # Stage 5: DuckDuckGo (optional)
        if use_duckduckgo and len(seeds) < max_seeds:
            add(await _duckduckgo_seeds(
                domain, live_urls, entity_type, client
            ))

    return seeds[:max_seeds]