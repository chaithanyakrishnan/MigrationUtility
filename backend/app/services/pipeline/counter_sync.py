"""
app/services/pipeline/counter_sync.py
P4.4 — Counter Sync Verifier

The most critical single check in the entire migration.

Frp / FRP requires that three posting counters are equal across every plan:
  PL101  — Plan Record posting counter
  PH025  — Participant Header posting counter
  BR170  — Last HIVR (History Base Record) posting counter

If these three values are not equal at cutover, Frp will reject 100% of
post-migration transactions for the affected plan. This is the single most
common cause of migration failure in Relius → Frp projects.

This module provides two levels of verification:

  1. check_mapping_consistency(ctx)
     Pre-load, mapping-registry level.
     Confirms that all three counter fields are present and mapped from
     consistent source fields. Does not require live DB access.

  2. verify_live(engagement_id, relius_conn, frp_conn)
     Post-load, live DB level.
     Queries actual counter values from both databases per plan and per
     participant. Produces a per-plan pass/fail report.
     Called by P5.1 Frp writer before committing any plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CounterSyncCheckResult:
    """Result of the counter sync check — maps to ReconCheckResult format."""
    check_id: str = "D_05"
    check_name: str = "PL101 = PH025 = BR170 counter sync"
    category: str = "D"
    status: str = "pass"
    expected: Optional[str] = None
    actual: Optional[str] = None
    delta: Optional[float] = None
    detail: Optional[dict] = None
    auto_resolved: bool = False
    resolution: Optional[str] = None
    blocking: bool = False


@dataclass
class PlanCounterState:
    """Per-plan counter values from both systems."""
    plan_id: str
    pl101: Optional[int] = None     # Plan Record posting counter
    ph025: Optional[int] = None     # Participant Header (max across participants)
    br170: Optional[int] = None     # Last HIVR posting counter
    in_sync: bool = False
    mismatch_details: list[str] = field(default_factory=list)

    @property
    def all_equal(self) -> bool:
        vals = [v for v in (self.pl101, self.ph025, self.br170) if v is not None]
        return len(vals) == 3 and len(set(vals)) == 1


class CounterSyncVerifier:
    """
    P4.4 — Counter Sync Verifier.

    Pre-load:  check_mapping_consistency(ctx) → CounterSyncCheckResult
    Post-load: verify_live(...)               → list[PlanCounterState]
    """

    # The three Frp fields that must be equal at cutover
    COUNTER_FIELDS = {
        "PL101": "Plan Record posting counter",
        "PH025": "Participant Header posting counter",
        "BR170": "HIVR / History Base posting counter",
    }

    # Relius source fields that feed these counters
    RELIUS_COUNTER_SOURCES = {
        "PL101": {"PLANSTAT.POSTNO", "PLANDYN.POSTNO", "POSTNO", "PL101"},
        "PH025": {"PLANEESTAT.POSTNO", "PLANEE.POSTNO", "PH025"},
        "BR170": {"TRANSLED.POSTNO", "TRANSLED.TRANNO", "BR170", "POSTNO"},
    }

    # ── Pre-load: mapping consistency ────────────────────────
    async def check_mapping_consistency(self, ctx: dict) -> CounterSyncCheckResult:
        """
        Check that all three counter fields are present in the approved mappings
        and that their source fields are plausible counter-type fields.

        This is the pre-load check (no live DB required).
        The post-load check (verify_live) runs after P5.1 Frp writer completes.
        """
        mappings = ctx.get("approved_maps", [])

        # Find each counter field in the mappings
        counter_mappings = {}
        for m in mappings:
            tgt = m.tgt_field.upper()
            if tgt in self.COUNTER_FIELDS:
                counter_mappings[tgt] = m

        result = CounterSyncCheckResult()

        # Check 1: all three fields present
        missing = [f for f in self.COUNTER_FIELDS if f not in counter_mappings]
        if missing:
            result.status = "fail"
            result.blocking = True
            result.expected = "PL101, PH025, BR170 all present in mappings"
            result.actual = f"Missing counter fields: {', '.join(missing)}"
            result.detail = {
                "missing": missing,
                "present": list(counter_mappings.keys()),
            }
            result.resolution = (
                "CRITICAL: These three posting counters must ALL be present. "
                "If any is missing, post-migration transactions will be rejected. "
                "Add the missing field mappings in the Plan/Participant/Transaction domains."
            )
            return result

        # Check 2: source fields are plausible counter sources
        suspicious = []
        for frp_field, mapping in counter_mappings.items():
            src_key = f"{mapping.src_table}.{mapping.src_field}".upper()
            valid_sources = self.RELIUS_COUNTER_SOURCES[frp_field]
            # Accept exact match or field name match
            is_valid = (
                src_key in valid_sources
                or mapping.src_field.upper() in valid_sources
                or "POSTNO" in mapping.src_field.upper()
                or "TRANNO" in mapping.src_field.upper()
                or frp_field in mapping.src_field.upper()
            )
            if not is_valid:
                suspicious.append(
                    f"{frp_field} ← {src_key} "
                    f"(expected one of: {', '.join(sorted(valid_sources))})"
                )

        if suspicious:
            result.status = "warning"
            result.expected = "Counter fields mapped from POSTNO/counter-type Relius fields"
            result.actual = f"{len(suspicious)} counter mapping(s) look suspicious"
            result.detail = {
                "suspicious": suspicious,
                "counter_mappings": {
                    k: f"{v.src_table}.{v.src_field}"
                    for k, v in counter_mappings.items()
                },
            }
            result.resolution = (
                "Verify that these counter fields are mapped from the correct Relius "
                "POSTNO fields. A wrong mapping will cause post-cutover transaction "
                "rejections. Confirm with Relius SME."
            )
            return result

        # All good
        result.status = "pass"
        result.expected = "PL101 = PH025 = BR170 (pre-load mapping check)"
        result.actual = " | ".join(
            f"{k} ← {v.src_table}.{v.src_field}"
            for k, v in counter_mappings.items()
        )
        result.detail = {
            "counter_mappings": {
                k: f"{v.src_table}.{v.src_field}"
                for k, v in counter_mappings.items()
            },
            "note": (
                "Pre-load mapping check passed. Post-load verification "
                "(actual counter value equality) runs after P5.1 Frp writer."
            ),
        }
        return result

    # ── Post-load: live DB verification ───────────────────────
    async def verify_live(
        self,
        engagement_id: str,
        relius_connection,           # SQLAlchemy connection to Relius DB
        frp_connection,             # SQLAlchemy connection to Frp DB
    ) -> list[PlanCounterState]:
        """
        Post-load verification: query actual counter values from both databases
        per plan. Called by P5.1 Frp writer after writing records.

        Returns one PlanCounterState per plan. All must have all_equal=True
        before P5.3 cutover approval can proceed.
        """
        logger.info("counter_sync.verify_live.start", engagement=engagement_id)
        results = []

        try:
            # Query Relius: plan-level posting counter
            relius_plans = dict(
                relius_connection.execute(
                    "SELECT PLANID, POSTNO FROM PLANSTAT ORDER BY PLANID"
                )
            )

            # Query Frp: PL101, PH025 (max per plan), BR170 (last HIVR per plan)
            frp_pl101 = dict(
                frp_connection.execute(
                    "SELECT plan_id, post_counter FROM plan_record ORDER BY plan_id"
                )
            )
            frp_ph025 = dict(
                frp_connection.execute(
                    """SELECT plan_id, MAX(post_counter)
                       FROM participant_header
                       GROUP BY plan_id"""
                )
            )
            frp_br170 = dict(
                frp_connection.execute(
                    """SELECT plan_id, MAX(posting_counter)
                       FROM history_base
                       GROUP BY plan_id"""
                )
            )

            all_plans = set(relius_plans) | set(frp_pl101)
            for plan_id in sorted(all_plans):
                state = PlanCounterState(
                    plan_id=plan_id,
                    pl101=frp_pl101.get(plan_id),
                    ph025=frp_ph025.get(plan_id),
                    br170=frp_br170.get(plan_id),
                )
                if not state.all_equal:
                    vals = {
                        "PL101": state.pl101,
                        "PH025": state.ph025,
                        "BR170": state.br170,
                    }
                    unique_vals = set(v for v in vals.values() if v is not None)
                    state.mismatch_details = [
                        f"{k}={v}" for k, v in vals.items()
                    ]
                    if len(unique_vals) > 1:
                        state.mismatch_details.append(
                            f"MISMATCH: values differ ({unique_vals})"
                        )
                state.in_sync = state.all_equal
                results.append(state)

        except Exception as exc:
            logger.error("counter_sync.verify_live.error", error=str(exc))
            # Return a single error state rather than crashing
            results.append(PlanCounterState(
                plan_id="ERROR",
                mismatch_details=[f"Live verification failed: {exc}"],
            ))

        failed = [r for r in results if not r.in_sync and r.plan_id != "ERROR"]
        logger.info(
            "counter_sync.verify_live.complete",
            engagement=engagement_id,
            plans=len(results),
            in_sync=sum(1 for r in results if r.in_sync),
            out_of_sync=len(failed),
        )
        return results

    def summarise(self, states: list[PlanCounterState]) -> dict:
        """Produce a summary dict for audit log / API response."""
        return {
            "total_plans": len(states),
            "in_sync": sum(1 for s in states if s.in_sync),
            "out_of_sync": sum(1 for s in states if not s.in_sync),
            "cutover_blocked": any(not s.in_sync for s in states),
            "mismatched_plans": [
                {
                    "plan_id": s.plan_id,
                    "pl101": s.pl101,
                    "ph025": s.ph025,
                    "br170": s.br170,
                    "details": s.mismatch_details,
                }
                for s in states
                if not s.in_sync
            ][:20],  # cap at 20 for API response size
        }


# Module-level singleton
counter_sync_verifier = CounterSyncVerifier()
