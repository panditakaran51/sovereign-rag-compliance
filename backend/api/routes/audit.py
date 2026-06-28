from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import AuditLogResponse, AuditEntry
from backend.audit.logger import get_audit_log, get_audit_entry

router = APIRouter()


@router.get("/audit-log", response_model=AuditLogResponse, tags=["Audit"])
async def audit_log(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AuditLogResponse:
    """
    Return paginated audit log of all queries — newest first.
    Required for DORA ICT risk documentation and AI decision traceability.
    """
    entries = await get_audit_log(limit=limit, offset=offset)
    return AuditLogResponse(
        total_shown=len(entries),
        offset=offset,
        entries=[AuditEntry(**e) for e in entries],
    )


@router.get("/audit-log/{query_id}", tags=["Audit"])
async def audit_entry(query_id: str) -> dict:
    """Return the full record for a single query, including answer and sources."""
    entry = await get_audit_entry(query_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found.")
    return entry
