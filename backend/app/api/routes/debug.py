"""Temporary debug endpoint."""
from __future__ import annotations
import io
from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/debug")

@router.post("/pdf-preview")
async def pdf_preview(file: UploadFile = File(...)):
    content = await file.read()

    import json
    from pathlib import Path
    ref = json.load(open(
        Path(__file__).parent.parent.parent / "reference_data" / "relius_schema.json"
    ))
    valid = frozenset(ref['table_to_domain'].keys())

    try:
        from app.services.schema.extractor import extractor
        pr = extractor.extract(file.filename or "upload.pdf", content)
        found = {t.name.upper() for t in pr.tables}
        return {
            "tables_found":    pr.table_count,
            "fields_found":    pr.field_count,
            "false_positives": sorted(found - valid),
            "missing":         sorted(valid - found),
        }
    except Exception as e:
        return {"error": str(e)}
