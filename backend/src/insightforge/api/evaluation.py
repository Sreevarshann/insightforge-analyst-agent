from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter

from insightforge.api.deps import AppSettings

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("")
def latest_results(settings: AppSettings) -> list[dict[str, Any]]:
    """Latest stored benchmark report per provider label (written by `make evaluate`)."""
    root = settings.eval_results_dir
    if not root.is_dir():
        return []
    out = []
    for f in sorted(root.glob("latest-*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    return out
