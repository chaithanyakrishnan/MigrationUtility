"""
app/services/pipeline/constants.py
P1.4 — Constants Registry

Pre-populates the mapping registry with known Relius field constants.
These values are hardcoded in the Frp FRP spec and never require SME review.
Emitted directly to mapping_registry at 100% confidence, status=auto_approved.

Known constants:
  CA007 = '050'   Cash Control Account Type — standard cash
  AR007 = '+531'  Auto Rebalance activity code
  FM006 = '+450'  File Maintenance activity code

These must be exactly right — a wrong value causes Frp to reject all
records of that type for the entire plan.
"""
from __future__ import annotations
from typing import Optional, List

import structlog
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import MappingEntry, AuditEvent

logger = structlog.get_logger(__name__)

# The complete set of known constants.
# Format: (src_table, src_field, tgt_table, tgt_field, constant_value, domain_id, description)
RELIUS_CONSTANTS: list[tuple] = [
    # Cash Control
    ("TRANSLED", "CA007", "CASH_CONTROL", "CA007",
     "050", "cash",
     "Cash Control Account Type — constant '050' for standard cash transactions"),

    # Auto Rebalance
    ("PLANINVEST", "AR007", "AUTO_REBALANCE", "AR007",
     "+531", "invest",
     "Auto Rebalance activity/sub-activity code — constant '+531'"),

    # File Maintenance
    ("PLANSTAT", "FM006", "FILE_MAINT", "FM006",
     "+450", "plan",
     "File Maintenance activity code — constant '+450'"),

    # Plan sequence constants (from prototype analysis)
    ("PLANSTAT", "CA007_PLAN", "PLAN_RECORD", "CA007",
     "050", "plan",
     "Plan-level Cash Control Account Type constant"),
]


async def seed_constant_mappings(
    engagement_id: str,
    db: AsyncSession,
) -> int:
    """
    Insert constant mappings into the mapping registry for an engagement.
    Safe to call multiple times — deletes and re-inserts each constant.
    Returns the number of constants seeded.
    """
    count = 0
    for src_table, src_field, tgt_table, tgt_field, value, domain_id, desc in RELIUS_CONSTANTS:
        # Remove existing entry for this field (idempotent)
        await db.execute(
            delete(MappingEntry).where(
                MappingEntry.engagement_id == engagement_id,
                MappingEntry.src_table == src_table,
                MappingEntry.src_field == src_field,
                MappingEntry.is_constant == True,
            )
        )
        entry = MappingEntry(
            engagement_id=engagement_id,
            domain_id=domain_id,
            src_table=src_table,
            src_field=src_field,
            src_display=f"{src_table}.{src_field}",
            tgt_table=tgt_table,
            tgt_field=tgt_field,
            tgt_display=f"{tgt_table} {tgt_field}",
            confidence=100,
            mapping_type="constant",
            is_constant=True,
            constant_value=value,
            note=desc,
            status="auto_approved",
        )
        db.add(entry)
        count += 1
        logger.debug("constants.seeded", field=src_field, value=value)

    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="constants.seeded",
        actor_type="system",
        actor_id="system",
        summary=f"P1.4 constants registry: {count} constants pre-populated at 100% confidence",
        detail={
            "constants": [
                {"field": r[1], "value": r[4], "domain": r[5]}
                for r in RELIUS_CONSTANTS
            ]
        },
    ))
    await db.commit()
    logger.info("constants.seed_complete", engagement=engagement_id, count=count)
    return count


def get_constant_value(field_name: str) -> Optional[str]:
    """Look up a constant value by Relius field name. Returns None if not a constant."""
    field_upper = field_name.upper()
    for _, src_field, _, _, value, _, _ in RELIUS_CONSTANTS:
        if src_field == field_upper:
            return value
    return None


def is_constant_field(field_name: str) -> bool:
    """Return True if the given Relius field is a known constant."""
    return get_constant_value(field_name) is not None
