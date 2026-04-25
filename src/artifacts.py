from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


def timestamped_root(base: str | Path = "artifacts") -> Path:
    root = Path(base) / datetime.now().strftime("%Y%m%d-%H%M%S")
    root.mkdir(parents=True, exist_ok=False)
    return root


def variant_dir(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(to_jsonable(data), indent=2, ensure_ascii=False), encoding="utf-8")


def save_arrays(path: Path, phase: np.ndarray, target: np.ndarray, focal_intensity: np.ndarray) -> None:
    np.save(path / "phase.npy", phase)
    np.save(path / "target.npy", target)
    np.save(path / "focal_intensity.npy", focal_intensity)
