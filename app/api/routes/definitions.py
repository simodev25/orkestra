"""Routes REST pour import/export/validate des définitions GH-14."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.definitions import validate_definition_payload
from app.services.definition_export_service import (
    DefinitionExportNotFoundError,
    export_definition,
)
from app.services.definition_import_service import (
    DefinitionImportError,
    import_definitions,
)
from app.services.definition_resolver_service import validate_definitions_batch


router = APIRouter()


class DefinitionsBatchIn(BaseModel):
    definitions: list[dict]


class ImportReportOut(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[dict]
    warnings: list[dict]


class ValidationReportOut(BaseModel):
    valid: bool
    errors: list[dict]
    warnings: list[dict]


def _validate_payload_or_422(definitions: list[dict]) -> list[dict]:
    validated: list[dict] = []
    for index, raw in enumerate(definitions):
        try:
            parsed = validate_definition_payload(raw)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "index": index,
                    "message": "Invalid definition schema",
                    "errors": exc.errors(),
                },
            )
        validated.append(parsed.model_dump())
    return validated


@router.post("/import", response_model=ImportReportOut)
async def import_definitions_route(
    payload: DefinitionsBatchIn,
    db: AsyncSession = Depends(get_db),
):
    validated = _validate_payload_or_422(payload.definitions)
    try:
        report = await import_definitions(db, validated)
    except DefinitionImportError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return ImportReportOut(
        created=report.created,
        updated=report.updated,
        skipped=report.skipped,
        errors=report.errors,
        warnings=report.warnings,
    )


@router.post("/validate", response_model=ValidationReportOut)
async def validate_definitions_route(
    payload: DefinitionsBatchIn,
    db: AsyncSession = Depends(get_db),
):
    validated = _validate_payload_or_422(payload.definitions)
    errors, warnings = await validate_definitions_batch(db, validated)
    return ValidationReportOut(valid=len(errors) == 0, errors=errors, warnings=warnings)


@router.get("/export")
async def export_definition_route(
    kind: str = Query(..., pattern="^(agent|orchestrator|scenario)$"),
    id: str | None = Query(default=None),
    definition_key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await export_definition(
            db,
            kind=kind,
            definition_id=id,
            definition_key=definition_key,
        )
    except DefinitionExportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/import-all", response_model=ImportReportOut)
async def import_all_definitions_route(
    payload: DefinitionsBatchIn,
    db: AsyncSession = Depends(get_db),
):
    """Importe toutes les définitions depuis un bundle JSON { definitions: [...] }."""
    validated = _validate_payload_or_422(payload.definitions)

    try:
        report = await import_definitions(db, validated)
    except DefinitionImportError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return ImportReportOut(
        created=report.created,
        updated=report.updated,
        skipped=report.skipped,
        errors=report.errors,
        warnings=report.warnings,
    )
