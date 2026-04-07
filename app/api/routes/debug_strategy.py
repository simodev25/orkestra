"""Debug Strategy API — read debug-strategy JSON files from disk."""

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

DEBUG_DIR = Path(os.environ.get("ORKESTRA_DEBUG_STRATEGY_DIR", "/app/storage/debug-strategy"))


@router.get("/debug-strategy")
async def list_debug_strategies(
    strategy_id: Optional[str] = None,
    status: Optional[str] = None,
    pair: Optional[str] = None,
    limit: int = Query(50, le=200),
):
    """List debug-strategy files from disk, most recent first."""
    if not DEBUG_DIR.exists():
        return {"total": 0, "files": []}

    files = sorted(DEBUG_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

    results = []
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)

            sid = data.get("strategy_id", "")
            st = data.get("status", "")
            p = data.get("input", {}).get("pair", "")

            if strategy_id and strategy_id not in sid:
                continue
            if status and status not in st:
                continue
            if pair and pair not in p:
                continue

            results.append({
                "filename": f.name,
                "strategy_id": sid,
                "status": st,
                "pair": p,
                "timeframe": data.get("input", {}).get("timeframe", ""),
                "template": data.get("result", {}).get("template", ""),
                "elapsed_seconds": data.get("elapsed_seconds", 0),
                "validation_status": data.get("validation", {}).get("status", ""),
                "validation_score": data.get("validation", {}).get("score", 0),
                "generated_at": data.get("generated_at", ""),
                "tags": data.get("tags", []),
            })

            if len(results) >= limit:
                break
        except Exception:
            results.append({"filename": f.name, "error": "parse_error"})

    return {"total": len(results), "files": results}


@router.get("/debug-strategy/{filename}")
async def get_debug_strategy(filename: str):
    """Get the full content of a debug-strategy file."""
    filepath = DEBUG_DIR / filename
    if not filepath.exists() or filepath.suffix != ".json":
        raise HTTPException(status_code=404, detail="File not found")

    with open(filepath) as f:
        return json.load(f)
