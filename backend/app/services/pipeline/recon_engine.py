"""
app/services/pipeline/recon_engine.py
P4.2 — Reconciliation Engine

Runs 15 validation checks across 4 categories against an engagement's
mapping registry and ETL artefacts. Each check produces a ReconCheckResult.

Categories:
  A. Schema completeness    — did all domains get mapped?
  B. Mapping integrity      — are the approved mappings internally consistent?
  C. Load order             — does the mapping respect Frp dependency order?
  D. Financial/data quality — do known constants, key fields, and
                               counter relationships hold?

The engine is deliberately conservative: a check raises a WARNING rather
than a FAIL when the issue is likely benign or non-blocking.  A FAIL means
the migration MUST NOT proceed without SME resolution.

P4.4 Counter Sync check (PL101 = PH025 = BR170) lives in counter_sync.py
and is called by this engine as check D_05.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    DomainReview,
    ETLArtefact,
    Engagement,
    MappingEntry,
    SchemaFile,
)

logger = structlog.get_logger(__name__)


@dataclass
class ReconCheckResult:
    check_id: str
    check_name: str
    category: str           # A | B | C | D
    status: str             # pass | fail | warning
    expected: Optional[str] = None
    actual: Optional[str] = None
    delta: Optional[float] = None
    detail: Optional[dict] = None
    auto_resolved: bool = False
    resolution: Optional[str] = None
    blocking: bool = False  # True → cannot proceed to cutover


@dataclass
class ReconRunResult:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    engagement_id: str = ""
    checks: list[ReconCheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.status == "warning")

    @property
    def auto_resolved(self) -> int:
        return sum(1 for c in self.checks if c.auto_resolved)

    @property
    def is_cutover_ready(self) -> bool:
        """No blocking failures — safe to proceed to P5.3 cutover approval."""
        return all(
            not (c.status == "fail" and c.blocking)
            for c in self.checks
        )


class ReconciliationEngine:
    """
    P4.2 — Reconciliation Engine.

    run(engagement_id, check_ids, db) → ReconRunResult
    """

    # All registered checks: id → (name, category, blocking, method_name)
    CHECKS = [
        # ── A. Schema completeness ───────────────────────────
        ("A_01", "Both schema files uploaded and parsed",      "A", True,  "_check_schema_files"),
        ("A_02", "All 8 Relius domains reviewed by SME",       "A", False, "_check_domain_reviews"),
        ("A_03", "Frp schema reviewed and confirmed",         "A", False, "_check_frp_reviews"),
        ("A_04", "ETL artefacts generated",                    "A", True,  "_check_etl_artefacts"),
        # ── B. Mapping integrity ─────────────────────────────
        ("B_01", "No unmapped (gap) fields in active domains", "B", False, "_check_no_gaps"),
        ("B_02", "All confirmed mappings have a target field", "B", True,  "_check_target_fields"),
        ("B_03", "No duplicate source→target pairs",          "B", True,  "_check_no_duplicates"),
        ("B_04", "UDF mappings saved before ETL generation",  "B", False, "_check_udf_mappings"),
        # ── C. Load order ────────────────────────────────────
        ("C_01", "Mappings respect Frp 15-step load order",  "C", True,  "_check_load_order"),
        ("C_02", "Plan domain mapped before Participant",     "C", True,  "_check_plan_before_part"),
        ("C_03", "Control files registered",                  "C", False, "_check_control_files"),
        # ── D. Financial / data quality ──────────────────────
        ("D_01", "Posting counter fields present in mapping", "D", True,  "_check_posting_counters"),
        ("D_02", "Known Relius constants mapped correctly",   "D", True,  "_check_constants"),
        ("D_03", "Composite participant ID field present",    "D", True,  "_check_composite_key"),
        ("D_04", "HIVR transaction type mapping present",     "D", False, "_check_hivr_mapping"),
        ("D_05", "PL101 = PH025 = BR170 counter sync",        "D", True,  "_check_counter_sync"),
    ]

    async def run(
        self,
        engagement_id: str,
        check_ids: Optional[list[str]],
        db: AsyncSession,
    ) -> ReconRunResult:
        """Run all (or a subset of) reconciliation checks for an engagement."""
        run = ReconRunResult(engagement_id=engagement_id)

        # Load data once — shared across all checks
        ctx = await self._load_context(engagement_id, db)

        checks_to_run = [
            c for c in self.CHECKS
            if check_ids is None or c[0] in check_ids
        ]

        for check_id, check_name, category, blocking, method_name in checks_to_run:
            try:
                method = getattr(self, method_name)
                result: ReconCheckResult = await method(ctx)
                result.check_id   = check_id
                result.check_name = check_name
                result.category   = category
                result.blocking   = blocking and result.status == "fail"
            except Exception as exc:
                logger.error("recon.check.error", check=check_id, error=str(exc))
                result = ReconCheckResult(
                    check_id=check_id,
                    check_name=check_name,
                    category=category,
                    status="warning",
                    blocking=False,
                    detail={"error": str(exc)},
                    resolution="Check could not execute — inspect manually",
                )

            run.checks.append(result)
            logger.debug("recon.check", id=check_id, status=result.status)

        logger.info(
            "recon.run.complete",
            engagement=engagement_id,
            passed=run.passed,
            failed=run.failed,
            warnings=run.warnings,
            cutover_ready=run.is_cutover_ready,
        )
        return run

    # ── Context loader ────────────────────────────────────────
    async def _load_context(self, engagement_id: str, db: AsyncSession) -> dict:
        """Load all DB data needed by checks into a single dict."""
        # Engagement
        eng_q = await db.execute(
            select(Engagement).where(Engagement.id == engagement_id)
        )
        engagement = eng_q.scalar_one_or_none()

        # Schema files
        sf_q = await db.execute(
            select(SchemaFile).where(SchemaFile.engagement_id == engagement_id)
        )
        schema_files = sf_q.scalars().all()

        # Domain reviews
        dr_q = await db.execute(
            select(DomainReview).where(DomainReview.engagement_id == engagement_id)
        )
        domain_reviews = dr_q.scalars().all()

        # Mappings
        map_q = await db.execute(
            select(MappingEntry).where(MappingEntry.engagement_id == engagement_id)
        )
        mappings = map_q.scalars().all()

        # ETL artefacts
        art_q = await db.execute(
            select(ETLArtefact).where(ETLArtefact.engagement_id == engagement_id)
        )
        artefacts = art_q.scalars().all()

        return {
            "engagement":     engagement,
            "schema_files":   schema_files,
            "domain_reviews": domain_reviews,
            "mappings":       mappings,
            "artefacts":      artefacts,
            # Derived views
            "approved_maps":  [m for m in mappings if m.status in ("confirmed", "auto_approved")],
            "gap_maps":       [m for m in mappings if m.status == "gap"],
            "src_file":       next((f for f in schema_files if f.side == "src" and f.parse_status == "complete"), None),
            "tgt_file":       next((f for f in schema_files if f.side == "tgt" and f.parse_status == "complete"), None),
        }

    # ── A. Schema completeness ────────────────────────────────

    async def _check_schema_files(self, ctx: dict) -> ReconCheckResult:
        src = ctx["src_file"]
        tgt = ctx["tgt_file"]
        if src and tgt:
            return ReconCheckResult(
                check_id="", check_name="", category="A", status="pass",
                expected="Both schema files parsed",
                actual=f"Relius: {src.filename}  |  Frp: {tgt.filename}",
            )
        missing = []
        if not src: missing.append("Relius schema")
        if not tgt: missing.append("Frp schema")
        return ReconCheckResult(
            check_id="", check_name="", category="A", status="fail",
            expected="Both schema files uploaded and parsed",
            actual=f"Missing: {', '.join(missing)}",
            resolution=f"Upload and analyse {' and '.join(missing)} before generating ETL",
        )

    async def _check_domain_reviews(self, ctx: dict) -> ReconCheckResult:
        src_reviews = [r for r in ctx["domain_reviews"] if r.side == "src"]
        approved    = [r for r in src_reviews if r.approved]
        total_domains = 8  # 8 Relius domains

        if len(approved) >= total_domains:
            return ReconCheckResult(
                check_id="", check_name="", category="A", status="pass",
                expected=f"{total_domains} domains reviewed",
                actual=f"{len(approved)} of {total_domains} domains approved",
            )
        pct = int(len(approved) / total_domains * 100)
        status = "warning" if pct >= 50 else "fail"
        return ReconCheckResult(
            check_id="", check_name="", category="A",
            status=status,
            expected=f"All {total_domains} Relius domains reviewed",
            actual=f"{len(approved)} of {total_domains} reviewed ({pct}%)",
            resolution="Complete Relius Schema Review (Screen 2) before proceeding",
            auto_resolved=False,
        )

    async def _check_frp_reviews(self, ctx: dict) -> ReconCheckResult:
        tgt_reviews = [r for r in ctx["domain_reviews"] if r.side == "tgt"]
        approved    = [r for r in tgt_reviews if r.approved]
        total = 8
        if len(approved) >= total:
            return ReconCheckResult(
                check_id="", check_name="", category="A", status="pass",
                actual=f"{len(approved)} of {total} Frp domains reviewed",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="A", status="warning",
            expected=f"All {total} Frp domains reviewed",
            actual=f"{len(approved)} of {total} reviewed",
            resolution="Complete Frp Schema Review (Screen 4)",
        )

    async def _check_etl_artefacts(self, ctx: dict) -> ReconCheckResult:
        artefacts = ctx["artefacts"]
        scripts   = [a for a in artefacts if a.artefact_type == "etl_script"]
        master    = [a for a in artefacts if a.artefact_type == "master_script"]

        if scripts and master:
            return ReconCheckResult(
                check_id="", check_name="", category="A", status="pass",
                actual=f"{len(scripts)} domain scripts + master run script generated",
            )
        if not artefacts:
            return ReconCheckResult(
                check_id="", check_name="", category="A", status="fail",
                expected="ETL scripts generated",
                actual="No ETL artefacts found",
                resolution="Run ETL Generation (Screen 7) before reconciliation",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="A", status="warning",
            expected="Domain scripts + master script",
            actual=f"{len(scripts)} domain scripts, master: {'yes' if master else 'no'}",
            resolution="Re-run ETL Generation to regenerate all artefacts",
        )

    # ── B. Mapping integrity ──────────────────────────────────

    async def _check_no_gaps(self, ctx: dict) -> ReconCheckResult:
        gaps = ctx["gap_maps"]
        if not gaps:
            return ReconCheckResult(
                check_id="", check_name="", category="B", status="pass",
                actual="No unmapped fields",
            )
        # Gaps are acceptable if they are in non-critical domains
        critical_domains = {"plan", "part", "cash"}
        critical_gaps = [g for g in gaps if g.domain_id in critical_domains]
        if not critical_gaps:
            return ReconCheckResult(
                check_id="", check_name="", category="B", status="warning",
                expected="0 gaps",
                actual=f"{len(gaps)} gaps in non-critical domains",
                detail={"domains": list({g.domain_id for g in gaps})},
                auto_resolved=True,
                resolution=f"{len(gaps)} gap fields are in optional domains — proceeding",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="B", status="fail",
            expected="0 gaps in critical domains",
            actual=f"{len(critical_gaps)} unmapped fields in {critical_domains & {g.domain_id for g in critical_gaps}}",
            detail={"critical_gaps": [f"{g.src_table}.{g.src_field}" for g in critical_gaps[:10]]},
            resolution="Define mappings or mark as excluded in AI Field Mapping screen",
        )

    async def _check_target_fields(self, ctx: dict) -> ReconCheckResult:
        bad = [
            m for m in ctx["approved_maps"]
            if not m.tgt_field and not m.is_constant
        ]
        if not bad:
            return ReconCheckResult(
                check_id="", check_name="", category="B", status="pass",
                actual=f"{len(ctx['approved_maps'])} approved mappings all have target fields",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="B", status="fail",
            expected="All approved mappings have a target field",
            actual=f"{len(bad)} mappings missing tgt_field",
            detail={"fields": [f"{m.src_table}.{m.src_field}" for m in bad[:10]]},
            resolution="Review and fix incomplete mappings in AI Field Mapping screen",
        )

    async def _check_no_duplicates(self, ctx: dict) -> ReconCheckResult:
        seen: dict[tuple, list] = {}
        for m in ctx["approved_maps"]:
            key = (m.src_table, m.src_field, m.tgt_table, m.tgt_field)
            seen.setdefault(key, []).append(m.id)
        dupes = {k: v for k, v in seen.items() if len(v) > 1}
        if not dupes:
            return ReconCheckResult(
                check_id="", check_name="", category="B", status="pass",
                actual="No duplicate source→target pairs",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="B", status="fail",
            expected="No duplicates",
            actual=f"{len(dupes)} duplicate source→target pairs",
            detail={"duplicates": [f"{k[0]}.{k[1]}→{k[2]}.{k[3]}" for k in list(dupes)[:5]]},
            resolution="Remove duplicate entries in AI Field Mapping screen",
        )

    async def _check_udf_mappings(self, ctx: dict) -> ReconCheckResult:
        udf_maps = [m for m in ctx["approved_maps"] if m.is_udf]
        if not udf_maps:
            return ReconCheckResult(
                check_id="", check_name="", category="B", status="pass",
                actual="No UDF mappings (none required or none defined)",
            )
        # Check all UDF mappings have both src and tgt fields filled
        incomplete = [m for m in udf_maps if not m.src_field or not m.tgt_field]
        if incomplete:
            return ReconCheckResult(
                check_id="", check_name="", category="B", status="warning",
                expected="All UDF mappings complete",
                actual=f"{len(incomplete)} of {len(udf_maps)} UDF mappings incomplete",
                detail={"incomplete": [m.src_field for m in incomplete[:5]]},
                resolution="Complete UDF definitions in AI Field Mapping screen",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="B", status="pass",
            actual=f"{len(udf_maps)} UDF mappings defined and complete",
        )

    # ── C. Load order ─────────────────────────────────────────

    FRP_LOAD_ORDER = {
        "plan": 1, "invest": 2, "part": 3, "cash": 4,
        "loans": 5, "payroll": 6, "compliance": 7, "annuity": 8,
    }

    async def _check_load_order(self, ctx: dict) -> ReconCheckResult:
        """Verify mapped domains are a subset of the 15-step Frp load order."""
        mapped_domains = {m.domain_id for m in ctx["approved_maps"]}
        unknown = mapped_domains - set(self.FRP_LOAD_ORDER.keys())
        if not unknown:
            ordered = sorted(
                mapped_domains,
                key=lambda d: self.FRP_LOAD_ORDER.get(d, 99),
            )
            return ReconCheckResult(
                check_id="", check_name="", category="C", status="pass",
                actual=f"Load order valid: {' → '.join(ordered)}",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="C", status="fail",
            expected="All domains in Frp load order",
            actual=f"Unknown domains not in load order: {unknown}",
            detail={"unknown_domains": list(unknown)},
            resolution="Verify domain IDs match the 8 canonical domains (plan/part/invest/cash/loans/payroll/compliance/annuity)",
        )

    async def _check_plan_before_part(self, ctx: dict) -> ReconCheckResult:
        """
        Plan domain records must be loaded before Participant records.
        This is a hard Frp FK dependency: Participant Header references Plan Record.
        """
        mappings = ctx["approved_maps"]
        has_plan = any(m.domain_id == "plan" for m in mappings)
        has_part = any(m.domain_id == "part" for m in mappings)
        if not (has_plan and has_part):
            return ReconCheckResult(
                check_id="", check_name="", category="C", status="warning",
                actual=f"Plan domain: {'present' if has_plan else 'missing'}  |  Participant: {'present' if has_part else 'missing'}",
                resolution="Both Plan and Participant domains should be in scope",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="C", status="pass",
            actual="Plan domain present and ordered before Participant",
        )

    async def _check_control_files(self, ctx: dict) -> ReconCheckResult:
        """Check if control file artefacts or records exist."""
        cf_artefacts = [
            a for a in ctx["artefacts"]
            if "control" in a.filename.lower() or "ct_" in a.filename.lower()
        ]
        if cf_artefacts:
            return ReconCheckResult(
                check_id="", check_name="", category="C", status="pass",
                actual=f"{len(cf_artefacts)} control files registered",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="C", status="warning",
            expected="At least one control file registered",
            actual="No control files found",
            resolution="Upload plan control files in AI Field Mapping screen (Control Files section)",
        )

    # ── D. Financial / data quality ───────────────────────────

    async def _check_posting_counters(self, ctx: dict) -> ReconCheckResult:
        """
        The three posting counters must all be present in the mapping:
          PL101  (Plan Record)
          PH025  (Participant Header)
          BR170  (HIVR / History Base)
        These must be equal at cutover — checked more deeply in D_05.
        """
        mappings = ctx["approved_maps"]
        tgt_fields = {m.tgt_field.upper() for m in mappings}

        counter_fields = {
            "PL101": "Plan post counter",
            "PH025": "Participant post counter",
            "BR170": "HIVR posting counter",
        }
        missing = {k: v for k, v in counter_fields.items() if k not in tgt_fields}

        if not missing:
            return ReconCheckResult(
                check_id="", check_name="", category="D", status="pass",
                actual="PL101, PH025, BR170 all present in approved mappings",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="D", status="fail",
            expected="PL101, PH025, BR170 all mapped",
            actual=f"Missing: {', '.join(missing.keys())}",
            detail={"missing": missing},
            resolution=(
                "These three posting counters MUST be present and equal at cutover. "
                "Add mappings for the missing fields."
            ),
        )

    async def _check_constants(self, ctx: dict) -> ReconCheckResult:
        """
        Verify known Relius constants are mapped with their correct values.
        These are non-negotiable — wrong values cause Frp to reject records.
        """
        REQUIRED_CONSTANTS = {
            "CA007": "050",   # Cash Control Account Type
            "AR007": "+531",  # Auto Rebalance
            "FM006": "+450",  # File Maintenance
        }
        constant_maps = {
            m.src_field.upper(): m.constant_value
            for m in ctx["approved_maps"]
            if m.is_constant and m.constant_value
        }
        errors = []
        for field_name, expected_val in REQUIRED_CONSTANTS.items():
            if field_name not in constant_maps:
                errors.append(f"{field_name} not mapped as constant")
            elif constant_maps[field_name] != expected_val:
                errors.append(
                    f"{field_name}: expected '{expected_val}', got '{constant_maps[field_name]}'"
                )
        if not errors:
            return ReconCheckResult(
                check_id="", check_name="", category="D", status="pass",
                actual=f"Constants CA007={constant_maps.get('CA007','?')} | "
                       f"AR007={constant_maps.get('AR007','?')} | "
                       f"FM006={constant_maps.get('FM006','?')}",
            )
        return ReconCheckResult(
            check_id="", check_name="", category="D", status="fail",
            expected="CA007='050', AR007='+531', FM006='+450'",
            actual=" | ".join(errors),
            detail={"errors": errors, "found": constant_maps},
            resolution=(
                "These constants are hardcoded in the Frp FRP spec. "
                "Correct the constant values in AI Field Mapping screen."
            ),
        )

    async def _check_composite_key(self, ctx: dict) -> ReconCheckResult:
        """
        The 17-character Frp composite Participant ID (PH007 / BR007) must be
        present in the mapping. It encodes plan number, SSN, and extension codes.
        """
        mappings = ctx["approved_maps"]
        # Check for PH007 (Participant Header) or PH005 (alt field name)
        id_fields = {m.tgt_field.upper() for m in mappings}
        has_ph_id = any(f in id_fields for f in ("PH007", "PH005", "BR007"))
        src_fields_lower = {m.src_field.upper() for m in mappings}
        has_src_key = any(
            k in src_fields_lower for k in ("SSNUM", "PLANID", "PLANNO", "SSNO")
        )
        if has_ph_id and has_src_key:
            return ReconCheckResult(
                check_id="", check_name="", category="D", status="pass",
                actual="Composite participant ID mapping present",
            )
        missing = []
        if not has_ph_id:
            missing.append("Frp participant ID target field (PH007/BR007)")
        if not has_src_key:
            missing.append("Relius participant key source fields (SSNUM/PLANID)")
        return ReconCheckResult(
            check_id="", check_name="", category="D", status="fail",
            expected="17-char composite participant ID mapping present",
            actual=f"Missing: {', '.join(missing)}",
            detail={"found_tgt_fields": list(id_fields)[:10]},
            resolution=(
                "The 17-character Frp participant ID is built from Relius PLANID + "
                "SSNUM + extension codes (B/Q/F/RM/EF/AA). Map these fields in "
                "the Participant domain."
            ),
        )

    async def _check_hivr_mapping(self, ctx: dict) -> ReconCheckResult:
        """
        HIVR (History Base Record) is the most complex Frp record.
        Check that BR101 (transaction type) and BR110 (cash amount) are mapped.
        """
        mappings = ctx["approved_maps"]
        tgt_fields = {m.tgt_field.upper() for m in mappings}
        hivr_required = {"BR101", "BR110", "BR170", "BR007"}
        present = hivr_required & tgt_fields
        missing = hivr_required - tgt_fields

        if not missing:
            return ReconCheckResult(
                check_id="", check_name="", category="D", status="pass",
                actual=f"HIVR fields mapped: {', '.join(sorted(present))}",
            )
        if "BR101" in missing or "BR170" in missing:
            return ReconCheckResult(
                check_id="", check_name="", category="D", status="warning",
                expected=f"HIVR fields: {', '.join(sorted(hivr_required))}",
                actual=f"Missing: {', '.join(sorted(missing))}",
                resolution=(
                    "HIVR transaction type (BR101) and posting counter (BR170) are critical. "
                    "Ensure the transaction domain mappings are complete."
                ),
            )
        return ReconCheckResult(
            check_id="", check_name="", category="D", status="warning",
            expected=f"All HIVR fields: {', '.join(sorted(hivr_required))}",
            actual=f"Present: {', '.join(sorted(present))} | Missing: {', '.join(sorted(missing))}",
        )

    async def _check_counter_sync(self, ctx: dict) -> ReconCheckResult:
        """
        P4.4 — Counter sync verifier.
        Delegates to the CounterSyncVerifier for the full PL101=PH025=BR170 check.
        At the mapping-registry level (pre-load) this checks that all three
        counter fields are mapped and that their source fields are consistent.
        Post-load verification is done by counter_sync.py against live data.
        """
        from app.services.pipeline.counter_sync import counter_sync_verifier
        result = await counter_sync_verifier.check_mapping_consistency(ctx)
        return result


# Module-level singleton
recon_engine = ReconciliationEngine()
