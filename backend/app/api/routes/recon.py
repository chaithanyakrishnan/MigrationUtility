"""
app/api/routes/recon.py
Reconciliation & Audit endpoints — Screen 8.

POST /engagements/{id}/recon/run           → run all (or subset of) checks
GET  /engagements/{id}/recon/results       → list latest check results
GET  /engagements/{id}/recon/results/{run} → full result for a specific run
POST /engagements/{id}/recon/counter-sync  → P4.4 counter sync live check
GET  /engagements/{id}/recon/audit         → I3 audit event log
POST /engagements/{id}/recon/cutover       → P5.3 three-party sign-off
GET  /engagements/{id}/recon/cutover       → cutover approval status
"""
from __future__ import annotations
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import Engagement, ReconResult, AuditEvent
from app.schemas.schemas import (
    AuditEventOut,
    ReconCheckResult as ReconCheckResultSchema,
    ReconRunRequest,
    ReconRunResult,
)
from app.services.pipeline.recon_engine import recon_engine, ReconCheckResult

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/engagements/{engagement_id}/recon")

# In-memory run state (Redis in production)
_run_state: dict = {}
# Cutover approvals: engagement_id → {approver_role: {user, timestamp, signature}}
_cutover_approvals: dict = {}


@router.post("/run", status_code=202)
async def run_recon(
    engagement_id: str = Path(...),
    payload: ReconRunRequest = ReconRunRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a reconciliation run for an engagement (P4.2).
    Runs all 15 checks (or a specified subset) asynchronously.
    """
    await _get_engagement(db, engagement_id)
    run_id = str(uuid.uuid4())
    _run_state[engagement_id] = {
        "run_id": run_id,
        "status": "running",
        "progress": 0,
        "message": "Running reconciliation checks…",
    }
    background_tasks.add_task(
        _run_recon_checks, engagement_id, run_id, payload.checks
    )
    return {
        "run_id": run_id,
        "engagement_id": engagement_id,
        "status": "running",
        "message": "Reconciliation started — poll /recon/results for progress",
    }


@router.get("/run/status")
async def get_run_status(engagement_id: str = Path(...)):
    """Poll current reconciliation run status."""
    state = _run_state.get(
        engagement_id,
        {"status": "idle", "message": "No run started"},
    )
    return {"engagement_id": engagement_id, **state}


@router.get("/results", response_model=ReconRunResult)
async def get_latest_results(
    engagement_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent reconciliation run results."""
    # Find most recent run_id
    q = await db.execute(
        select(ReconResult)
        .where(ReconResult.engagement_id == engagement_id)
        .order_by(desc(ReconResult.run_at))
        .limit(1)
    )
    latest = q.scalar_one_or_none()
    if not latest:
        raise HTTPException(404, "No reconciliation results found — run /recon/run first")

    run_id = latest.run_id

    # Fetch all checks for this run
    q2 = await db.execute(
        select(ReconResult)
        .where(
            ReconResult.engagement_id == engagement_id,
            ReconResult.run_id == run_id,
        )
        .order_by(ReconResult.check_id)
    )
    checks = q2.scalars().all()

    check_results = [
        ReconCheckResultSchema(
            check_id=c.check_id,
            check_name=c.check_name,
            status=c.status,
            expected=c.expected,
            actual=c.actual,
            delta=c.delta,
            detail=c.detail,
            auto_resolved=c.auto_resolved,
            resolution=c.resolution,
        )
        for c in checks
    ]

    return ReconRunResult(
        run_id=run_id,
        engagement_id=engagement_id,
        total_checks=len(check_results),
        passed=sum(1 for c in check_results if c.status == "pass"),
        failed=sum(1 for c in check_results if c.status == "fail"),
        warnings=sum(1 for c in check_results if c.status == "warning"),
        auto_resolved=sum(1 for c in check_results if c.auto_resolved),
        checks=check_results,
    )


@router.get("/results/{run_id}", response_model=ReconRunResult)
async def get_run_results(
    engagement_id: str = Path(...),
    run_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Return reconciliation results for a specific run."""
    q = await db.execute(
        select(ReconResult).where(
            ReconResult.engagement_id == engagement_id,
            ReconResult.run_id == run_id,
        ).order_by(ReconResult.check_id)
    )
    checks = q.scalars().all()
    if not checks:
        raise HTTPException(404, f"Run {run_id} not found")

    check_results = [
        ReconCheckResultSchema(
            check_id=c.check_id, check_name=c.check_name, status=c.status,
            expected=c.expected, actual=c.actual, delta=c.delta,
            detail=c.detail, auto_resolved=c.auto_resolved, resolution=c.resolution,
        )
        for c in checks
    ]
    return ReconRunResult(
        run_id=run_id, engagement_id=engagement_id,
        total_checks=len(check_results),
        passed=sum(1 for c in check_results if c.status == "pass"),
        failed=sum(1 for c in check_results if c.status == "fail"),
        warnings=sum(1 for c in check_results if c.status == "warning"),
        auto_resolved=sum(1 for c in check_results if c.auto_resolved),
        checks=check_results,
    )


@router.post("/counter-sync")
async def run_counter_sync(
    engagement_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """
    P4.4 — Run counter sync mapping consistency check immediately (synchronous).
    Returns the D_05 check result without running all 15 checks.
    """
    await _get_engagement(db, engagement_id)
    from app.services.pipeline.counter_sync import counter_sync_verifier

    # Load context
    ctx = await recon_engine._load_context(engagement_id, db)
    result = await counter_sync_verifier.check_mapping_consistency(ctx)

    return {
        "check_id": result.check_id,
        "check_name": result.check_name,
        "status": result.status,
        "expected": result.expected,
        "actual": result.actual,
        "detail": result.detail,
        "blocking": result.blocking,
        "resolution": result.resolution,
    }


@router.get("/audit", response_model=list[AuditEventOut])
async def get_audit_log(
    engagement_id: str = Path(...),
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    I3 — Return the immutable audit event log for an engagement.
    Events are in chronological order (oldest first).
    """
    q = (
        select(AuditEvent)
        .where(AuditEvent.engagement_id == engagement_id)
        .order_by(AuditEvent.created_at)
        .limit(limit)
    )
    if event_type:
        q = q.where(AuditEvent.event_type == event_type)
    result = await db.execute(q)
    return result.scalars().all()


# ── P5.3 Three-party cutover approval ────────────────────────

REQUIRED_APPROVERS = {
    "relius_sme":   "Relius SME sign-off",
    "frp_sme":     "Frp implementation specialist sign-off",
    "project_lead": "Project lead sign-off",
}


@router.post("/cutover")
async def submit_cutover_approval(
    engagement_id: str = Path(...),
    approver_role: str = Query(..., description="relius_sme | frp_sme | project_lead"),
    approver_name: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
):
    """
    P5.3 — Submit a cutover approval signature.
    All three roles must approve before the engagement can be marked complete.
    Blocked if any reconciliation checks have failing/blocking status.
    """
    await _get_engagement(db, engagement_id)

    if approver_role not in REQUIRED_APPROVERS:
        raise HTTPException(
            400,
            f"Unknown approver role '{approver_role}'. "
            f"Must be one of: {', '.join(REQUIRED_APPROVERS)}"
        )

    # Check for blocking recon failures
    latest_q = await db.execute(
        select(ReconResult)
        .where(
            ReconResult.engagement_id == engagement_id,
            ReconResult.status == "fail",
        )
    )
    blocking_failures = latest_q.scalars().all()
    # Only block on critical failures (check_id D_05, B_02, B_03, D_01, D_02, D_03)
    BLOCKING_CHECKS = {"D_05", "B_02", "B_03", "D_01", "D_02", "D_03", "A_01", "A_04"}
    critical = [r for r in blocking_failures if r.check_id in BLOCKING_CHECKS]
    if critical:
        raise HTTPException(
            409,
            f"Cutover approval blocked: {len(critical)} critical reconciliation "
            f"check(s) failing: {', '.join(r.check_id for r in critical)}. "
            "Resolve all critical failures before approving cutover."
        )

    # Record approval
    if engagement_id not in _cutover_approvals:
        _cutover_approvals[engagement_id] = {}

    from datetime import datetime, timezone
    _cutover_approvals[engagement_id][approver_role] = {
        "approver_name": approver_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signature": f"{approver_role}:{approver_name}:{engagement_id}",
    }

    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="cutover.approval_submitted",
        actor_type="sme",
        actor_id=approver_name,
        summary=f"Cutover approval: {REQUIRED_APPROVERS[approver_role]}",
        detail={
            "approver_role": approver_role,
            "approver_name": approver_name,
            "approvals_so_far": list(_cutover_approvals[engagement_id].keys()),
        },
    ))

    all_approved = all(
        role in _cutover_approvals[engagement_id]
        for role in REQUIRED_APPROVERS
    )

    if all_approved:
        # Mark engagement complete
        eng_q = await db.execute(
            select(Engagement).where(Engagement.id == engagement_id)
        )
        eng = eng_q.scalar_one_or_none()
        if eng:
            eng.status = "complete"

        db.add(AuditEvent(
            engagement_id=engagement_id,
            event_type="cutover.approved",
            actor_type="sme",
            actor_id="system",
            summary="Migration approved for cutover — all three parties signed off",
            detail={"approvals": _cutover_approvals[engagement_id]},
        ))

    await db.commit()

    approvals_received = list(_cutover_approvals[engagement_id].keys())
    pending = [r for r in REQUIRED_APPROVERS if r not in _cutover_approvals[engagement_id]]

    return {
        "engagement_id": engagement_id,
        "approver_role": approver_role,
        "approvals_received": approvals_received,
        "pending_approvals": pending,
        "cutover_approved": all_approved,
        "message": (
            "Migration approved for cutover!" if all_approved
            else f"Waiting for: {', '.join(REQUIRED_APPROVERS[r] for r in pending)}"
        ),
    }


@router.get("/cutover")
async def get_cutover_status(
    engagement_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Get current cutover approval status for an engagement."""
    await _get_engagement(db, engagement_id)
    approvals = _cutover_approvals.get(engagement_id, {})
    pending = [r for r in REQUIRED_APPROVERS if r not in approvals]
    return {
        "engagement_id": engagement_id,
        "approvals_received": {
            role: details
            for role, details in approvals.items()
        },
        "pending_approvals": {
            role: REQUIRED_APPROVERS[role]
            for role in pending
        },
        "cutover_approved": len(pending) == 0,
    }


# ── Background recon task ─────────────────────────────────────
async def _run_recon_checks(
    engagement_id: str,
    run_id: str,
    check_ids: Optional[list[str]],
) -> None:
    from app.db.session import get_session_factory

    async with get_session_factory()() as db:
        try:
            state = _run_state[engagement_id]
            state.update(progress=10, message="Loading engagement data…")

            run_result = await recon_engine.run(engagement_id, check_ids, db)

            state.update(progress=80, message="Persisting check results…")

            # Persist each check result to ReconResult table
            for check in run_result.checks:
                db.add(ReconResult(
                    engagement_id=engagement_id,
                    run_id=run_id,
                    check_id=check.check_id,
                    check_name=check.check_name,
                    status=check.status,
                    expected=check.expected,
                    actual=check.actual,
                    delta=check.delta,
                    detail=check.detail,
                    auto_resolved=check.auto_resolved,
                    resolution=check.resolution,
                ))

            db.add(AuditEvent(
                engagement_id=engagement_id,
                event_type="recon.run_complete",
                actor_type="system",
                actor_id="system",
                summary=(
                    f"Reconciliation complete: {run_result.passed} passed, "
                    f"{run_result.failed} failed, {run_result.warnings} warnings"
                ),
                detail={
                    "run_id": run_id,
                    "total": len(run_result.checks),
                    "passed": run_result.passed,
                    "failed": run_result.failed,
                    "warnings": run_result.warnings,
                    "auto_resolved": run_result.auto_resolved,
                    "cutover_ready": run_result.is_cutover_ready,
                },
            ))
            await db.commit()

            state.update(
                status="complete",
                progress=100,
                message=(
                    f"{'✓ Cutover ready' if run_result.is_cutover_ready else '✗ Issues require attention'} — "
                    f"{run_result.passed} passed · {run_result.failed} failed · "
                    f"{run_result.warnings} warnings"
                ),
                passed=run_result.passed,
                failed=run_result.failed,
                warnings=run_result.warnings,
                cutover_ready=run_result.is_cutover_ready,
            )

        except Exception as exc:
            logger.error("recon.run.error", engagement=engagement_id, error=str(exc))
            _run_state.get(engagement_id, {}).update(
                status="failed", message=str(exc)
            )


async def _get_engagement(db: AsyncSession, eid: str) -> Engagement:
    r = await db.execute(select(Engagement).where(Engagement.id == eid))
    e = r.scalar_one_or_none()
    if not e:
        raise HTTPException(404, f"Engagement {eid} not found")
    return e
