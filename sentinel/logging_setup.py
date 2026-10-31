"""Structured logging setup for sentinel-core."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_dir: str | Path = "logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("sentinel")
    if root.handlers:
        return
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    fh = logging.FileHandler(Path(log_dir) / "sentinel.log", encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"sentinel.{name}")
