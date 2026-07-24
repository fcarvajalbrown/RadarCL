"""
Result exporters: CSV, JSON and HTML.

CSV keeps the meaning it has always had — the mailable deliverable, so
VALID only. JSON and HTML instead carry every record with its status,
because UNKNOWN is a first-class verification outcome (ADR-0009) and a
report that hides it throws away the rows worth retrying. See ADR-0010.

Format is picked from the output extension, or forced by the caller.

Auto-export destination: ~/Desktop/RadarCL-YYYY-MM-DD.csv
Manual export: caller supplies an explicit path.
"""

import csv
import datetime
import html
import json
from pathlib import Path

from app import __version__

FIELDS = ['email', 'source', 'status', 'error']

_EXTENSIONS = {
    '.csv': 'csv',
    '.json': 'json',
    '.html': 'html',
    '.htm': 'html',
}

# Display order and Spanish label for each status the verifier produces.
_STATUS_LABELS = {
    'valid': 'Válidos',
    'unknown': 'Desconocidos',
    'invalid': 'Inválidos',
}

_ROW_LABELS = {
    'valid': 'Válido',
    'unknown': 'Desconocido',
    'invalid': 'Inválido',
}


def default_export_path() -> Path:
    """Return the auto-export path on the user's Desktop."""
    date_str = datetime.date.today().strftime('%Y-%m-%d')
    desktop = Path.home() / 'Desktop'
    desktop.mkdir(parents=True, exist_ok=True)
    return desktop / f'RadarCL-{date_str}.csv'


def summarize(results: list[dict]) -> dict[str, int]:
    """
    Count records per status, plus a total.

    The three known statuses are always present, even at zero, so a
    consumer can index them without guarding. Any status the verifier
    grows later is appended rather than dropped.
    """
    counts = {'total': len(results)}
    counts.update({status: 0 for status in _STATUS_LABELS})
    for record in results:
        status = record.get('status', 'unknown')
        counts[status] = counts.get(status, 0) + 1
    return counts


def _normalize(record: dict) -> dict:
    """Reduce a result to the four exported fields, filling in blanks."""
    return {field: record.get(field) or '' for field in FIELDS}


def _timestamp() -> str:
    """Local export time, to the second, with UTC offset."""
    return (
        datetime.datetime.now()
        .astimezone()
        .isoformat(timespec='seconds')
    )


def export_valid(results: list[dict], path: Path | None = None) -> Path:
    """
    Write only VALID emails to a CSV file.

    Parameters
    ----------
    results : list[dict]
        Each dict must have keys: 'email', 'source', 'status'.
    path : Path | None
        Destination file. If None, uses default_export_path().

    Returns
    -------
    Path
        The path where the file was written.
    """
    if path is None:
        path = default_export_path()

    valid = [r for r in results if r.get('status') == 'valid']

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(valid)

    return path


def export_json(results: list[dict], path: Path) -> Path:
    """
    Write every result to a JSON document, with run metadata and counts.

    The payload is an object rather than a bare array so the summary and
    the tool version travel with the data — a bare array would force every
    consumer to re-tally the rows to learn how the run went.
    """
    path = Path(path)
    payload = {
        'tool': 'RadarCL',
        'version': __version__,
        'exported_at': _timestamp(),
        'summary': summarize(results),
        'results': [_normalize(record) for record in results],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    return path


_HTML_STYLE = """\
:root { color-scheme: light dark; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
       margin: 2rem auto; max-width: 60rem; padding: 0 1rem;
       line-height: 1.5; }
h1 { margin-bottom: 0; font-size: 1.5rem; }
.meta { color: #666; margin-top: .25rem; font-size: .9rem; }
.resumen { display: flex; flex-wrap: wrap; gap: .75rem; list-style: none;
           padding: 0; margin: 1.5rem 0; }
.resumen li { border: 1px solid #ddd; border-left-width: 4px;
              border-radius: 4px; padding: .5rem .9rem; min-width: 7rem; }
.resumen b { display: block; font-size: 1.4rem; }
.valid { border-left-color: #2e7d32; }
.unknown { border-left-color: #ef6c00; }
.invalid { border-left-color: #c62828; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { text-align: left; padding: .45rem .6rem;
         border-bottom: 1px solid #e0e0e0; vertical-align: top; }
th { border-bottom-width: 2px; }
td.estado { white-space: nowrap; font-weight: 600; }
tr.valid td.estado { color: #2e7d32; }
tr.unknown td.estado { color: #ef6c00; }
tr.invalid td.estado { color: #c62828; }
td.origen { word-break: break-all; }
a { color: inherit; }
.nota { color: #666; font-size: .88rem; margin-top: 1.5rem;
        border-top: 1px solid #e0e0e0; padding-top: 1rem; }
@media (prefers-color-scheme: dark) {
  .meta, .nota { color: #aaa; }
  .resumen li { border-color: #444; }
  th, td, .nota { border-color: #333; }
}
"""


def _source_cell(source: str) -> str:
    """
    Render the source column, linking it only when it is safe to.

    Sources come from crawled pages, so a scheme other than http(s) is
    shown as plain text rather than turned into a clickable link.
    """
    escaped = html.escape(source)
    if source.startswith(('http://', 'https://')):
        return f'<a href="{escaped}">{escaped}</a>'
    return escaped


def export_html(results: list[dict], path: Path) -> Path:
    """
    Write every result to a single self-contained HTML report.

    No JavaScript, no external stylesheet, no remote font: the file has to
    open and read correctly on a machine with no network, which is the
    same stance ADR-0008 takes on dependencies.
    """
    path = Path(path)
    counts = summarize(results)

    cards = [f'<li><b>{counts["total"]}</b>Total</li>']
    cards += [
        f'<li class="{status}"><b>{counts[status]}</b>{label}</li>'
        for status, label in _STATUS_LABELS.items()
    ]

    rows = []
    for record in results:
        row = _normalize(record)
        status = row['status']
        rows.append(
            f'<tr class="{html.escape(status)}">'
            f'<td>{html.escape(row["email"])}</td>'
            f'<td class="origen">{_source_cell(row["source"])}</td>'
            f'<td class="estado">{html.escape(_ROW_LABELS.get(status, status))}</td>'
            f'<td>{html.escape(row["error"])}</td>'
            f'</tr>'
        )

    document = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RadarCL — resultados</title>
<style>
{_HTML_STYLE}</style>
</head>
<body>
<h1>RadarCL — resultados de verificación</h1>
<p class="meta">Generado el {html.escape(_timestamp())} · RadarCL {html.escape(__version__)}</p>
<ul class="resumen">
{chr(10).join(cards)}
</ul>
<table>
<thead><tr><th>Correo</th><th>Origen</th><th>Estado</th><th>Detalle</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
<p class="nota">Desconocido no significa inválido: es una dirección que no
se pudo comprobar, normalmente porque el servidor de correo rechaza las
sondas de verificación o porque la consulta DNS no obtuvo respuesta. Vale
la pena reintentarla desde otra red antes de descartarla.</p>
</body>
</html>
"""
    path.write_text(document, encoding='utf-8')
    return path


_WRITERS = {
    'csv': export_valid,
    'json': export_json,
    'html': export_html,
}


def infer_format(path: str | Path) -> str:
    """
    Map an output path's extension to an export format.

    Raises ValueError when the extension is not one RadarCL writes, so a
    caller can fail before doing the slow work rather than after it.
    """
    name = Path(path).name
    fmt = _EXTENSIONS.get(Path(path).suffix.lower())
    if fmt is None:
        raise ValueError(
            f"No se pudo deducir el formato de salida de '{name}'. "
            f"Use una extension .csv, .json o .html, o indique --format."
        )
    return fmt


def export(
    results: list[dict], path: str | Path, fmt: str | None = None
) -> Path:
    """
    Write results in the requested format, or the one the extension implies.

    This is the single entry point the CLI and the GUI both use, so the
    format-selection rule lives in one place.
    """
    path = Path(path)
    fmt = fmt or infer_format(path)
    writer = _WRITERS.get(fmt)
    if writer is None:
        known = ', '.join(_WRITERS)
        raise ValueError(f"Formato de salida desconocido: {fmt}. Use {known}.")
    return writer(results, path)
