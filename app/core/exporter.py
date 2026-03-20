"""
CSV exporter.

Auto-export destination: ~/Desktop/RadarCL-YYYY-MM-DD.csv
Manual export: caller supplies an explicit path.
"""

import csv
import datetime
from pathlib import Path


def default_export_path() -> Path:
    """Return the auto-export path on the user's Desktop."""
    date_str = datetime.date.today().strftime('%Y-%m-%d')
    desktop = Path.home() / 'Desktop'
    desktop.mkdir(parents=True, exist_ok=True)
    return desktop / f'RadarCL-{date_str}.csv'


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
        writer = csv.DictWriter(f, fieldnames=['email', 'source', 'status', 'error'], extrasaction='ignore')
        writer.writeheader()
        writer.writerows(valid)

    return path