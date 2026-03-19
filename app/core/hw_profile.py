"""
Hardware profiler.

Detects available RAM and physical CPU cores at startup and
returns conservative crawl settings appropriate for the machine.
Prevents RadarCL from choking low-spec hardware (Dell Optiplex etc.).
"""

import psutil
from dataclasses import dataclass


@dataclass
class HWProfile:
    """
    Tuned crawl settings for the current machine.

    Attributes
    ----------
    concurrency : int
        Simultaneous HTTP requests.
    request_delay : float
        Seconds to wait between requests.
    max_pages : int
        Hard cap on total pages crawled per session.
    tier : str
        Human-readable tier label for display in UI.
    ram_gb : float
        Detected total RAM in gigabytes.
    cpu_cores : int
        Detected physical CPU core count.
    """
    concurrency: int
    request_delay: float
    max_pages: int
    tier: str
    ram_gb: float
    cpu_cores: int


def get_hw_profile() -> HWProfile:
    """
    Detect hardware specs and return appropriate crawl settings.

    Tiers
    -----
    low    : RAM < 4GB  or cores <= 2  → concurrency 2, delay 1.0s
    medium : RAM 4–8GB and cores 2–4   → concurrency 3, delay 0.5s
    high   : RAM > 8GB and cores > 4   → concurrency 6, delay 0.2s

    Returns
    -------
    HWProfile
    """
    ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 1

    if ram_gb < 4 or cpu_cores <= 2:
        return HWProfile(
            concurrency=2,
            request_delay=1.0,
            max_pages=1000,
            tier="low",
            ram_gb=round(ram_gb, 1),
            cpu_cores=cpu_cores,
        )
    elif ram_gb <= 8 or cpu_cores <= 4:
        return HWProfile(
            concurrency=3,
            request_delay=0.5,
            max_pages=2000,
            tier="medium",
            ram_gb=round(ram_gb, 1),
            cpu_cores=cpu_cores,
        )
    else:
        return HWProfile(
            concurrency=6,
            request_delay=0.2,
            max_pages=5000,
            tier="high",
            ram_gb=round(ram_gb, 1),
            cpu_cores=cpu_cores,
        )