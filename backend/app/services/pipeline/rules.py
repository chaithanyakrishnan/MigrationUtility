"""
app/services/pipeline/rules.py
P3.2 — Rule Engine   +   P3.4 — Composite Key Builder

Rule Engine
-----------
Applies deterministic field-level transforms defined as YAML rules.
Rules live in a registry here (later: loaded from DB or file per engagement).
Each rule is a Python expression evaluated with a restricted namespace.

Composite Key Builder (P3.4)
-----------------------------
Builds the 17-character Frp composite Participant ID from Relius fields.

Structure of the 17-char key:
  Positions 1–9  : Plan number (PLANSTAT.PLANID, zero-padded to 9 chars)
  Positions 10–18: SSN / participant ID (PERSON.SSNUM, 9 digits, no dashes)

Extension codes appended after the base 17 chars for special participant types:
  B   Beneficiary
  Q   QDRO alternate payee
  F   Forfeiture account
  RM  Required minimum distribution
  EF  Enrolled participant
  AA  Alternate address

The resulting string is exactly 17 characters for standard participants,
longer (18–19) for participants with extension codes.
Frp validates this on import — wrong format = 100% rejection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ── P3.2 Rule Registry ────────────────────────────────────────
# rule_id → Python expression string.
# 'value' = the raw source field value.
# Additional names available: str, int, float, len, round, abs,
# datetime (from datetime module), re (regex module).

TRANSFORM_RULES: dict[str, str] = {
    # ── Date conversions ─────────────────────────────────────
    "date_to_yyyymmdd":
        "value.strftime('%Y%m%d') if hasattr(value, 'strftime') else str(value)[:10].replace('-', '')",

    "date_to_mmddyyyy":
        "value.strftime('%m%d%Y') if hasattr(value, 'strftime') else (str(value)[5:7]+str(value)[8:10]+str(value)[:4] if len(str(value))>=10 else str(value))",

    # ── String normalisation ─────────────────────────────────
    "strip_dashes":
        "re.sub(r'[\\-\\s]', '', str(value or ''))",

    "trim_upper":
        "str(value or '').strip().upper()",

    "trim_30":
        "str(value or '').strip()[:30]",

    # ── Numeric conversions ───────────────────────────────────
    "to_cents":
        "int(round(float(value or 0) * 100))",

    "pct_to_decimal":
        "round(float(value or 0) / 100, 6)",

    "decimal_to_pct":
        "round(float(value or 0) * 100, 4)",

    # ── Boolean / code conversions ───────────────────────────
    "yn_to_bool":
        "'Y' if str(value or '').upper() in ('Y', 'YES', 'TRUE', '1') else 'N'",

    "bool_to_yn":
        "'Y' if value else 'N'",

    # ── Relius-specific crosswalks ────────────────────────────
    # Marital status: Relius single char → Frp code
    "marital_status_crosswalk": (
        "{'S': 'S', 'M': 'M', 'D': 'D', 'W': 'W', 'U': 'U'}"
        ".get(str(value or '').upper()[:1], 'U')"
    ),

    # Plan type crosswalk
    "plan_type_crosswalk": (
        "{'401K': '401K', '403B': '403B', 'PROFIT': 'PSP', 'MONEY': 'MPP', "
        "'ESOP': 'ESP', '457B': '457B', '401A': '401A'}"
        ".get(str(value or '').upper()[:5].strip(), str(value or ''))"
    ),

    # Loan type: Relius code → Frp code
    "loan_type_crosswalk": (
        "{'G': 'GENERAL', 'R': 'RESIDE', 'H': 'HARDSHIP'}"
        ".get(str(value or '').upper()[:1], 'GENERAL')"
    ),

    # ── Null handling ─────────────────────────────────────────
    "null_to_empty":
        "'' if value is None else str(value)",

    "null_to_zero":
        "0 if value is None else value",

    "null_to_spaces":
        "' ' if value is None else str(value)",
}

# Restricted eval namespace — only safe builtins
_EVAL_NAMESPACE = {
    "__builtins__": {},
    "str": str, "int": int, "float": float, "bool": bool,
    "len": len, "round": round, "abs": abs, "min": min, "max": max,
    "re": re,
}
try:
    from datetime import datetime
    _EVAL_NAMESPACE["datetime"] = datetime
except ImportError:
    pass


class RuleEngine:
    """
    P3.2 — Rule Engine.
    Applies named transform rules or arbitrary rule expressions to field values.
    """

    def apply(self, value: Any, rule: str) -> Any:
        """
        Apply a transform rule to a value.
        rule can be:
          - A named rule ID from TRANSFORM_RULES (e.g. "date_to_yyyymmdd")
          - An arbitrary Python expression string (e.g. "str(value).upper()")
        """
        if not rule:
            return value

        # Look up named rule
        expression = TRANSFORM_RULES.get(rule, rule)

        try:
            ns = {**_EVAL_NAMESPACE, "value": value}
            return eval(expression, ns)  # noqa: S307
        except Exception as exc:
            logger.warning("rule_engine.apply_failed",
                           rule=rule[:40], error=str(exc))
            return value

    def apply_row(self, row: dict, rules: dict[str, str]) -> dict:
        """
        Apply a dict of {target_field: rule_expression} to a source row dict.
        Returns a new dict with transformed values.
        """
        out = {}
        for tgt_field, rule in rules.items():
            src_value = row.get(tgt_field) or row.get(tgt_field.lower())
            out[tgt_field] = self.apply(src_value, rule)
        return out

    def validate_rule(self, rule: str) -> tuple[bool, str]:
        """
        Check whether a rule expression is syntactically valid.
        Returns (is_valid, error_message).
        """
        expression = TRANSFORM_RULES.get(rule, rule)
        try:
            compile(expression, "<rule>", "eval")
            return True, ""
        except SyntaxError as e:
            return False, str(e)

    def list_rules(self) -> list[dict]:
        """Return all named rules with their expressions."""
        return [
            {"id": k, "expression": v, "description": k.replace("_", " ").title()}
            for k, v in TRANSFORM_RULES.items()
        ]


# ── P3.4 Composite Key Builder ────────────────────────────────

@dataclass
class ParticipantKey:
    plan_id: str
    ssn: str
    extension: str = ""   # B | Q | F | RM | EF | AA | ""

    @property
    def composite_id(self) -> str:
        """
        Build the 17-char Frp composite participant ID.
        Format: PPPPPPPPPXXXXXXXXX[ext]
          P = plan number, zero-padded to 9 chars
          X = SSN digits only, exactly 9 chars, zero-padded
        """
        plan_part = re.sub(r"\D", "", str(self.plan_id or "")).zfill(9)[:9]
        ssn_part  = re.sub(r"\D", "", str(self.ssn  or "")).zfill(9)[:9]
        base = plan_part + ssn_part   # exactly 17 chars
        return base + self.extension   # 17 for standard, 18-19 with extension

    @property
    def is_valid(self) -> bool:
        """
        Validate the composite ID.
        Base 17 chars must not be all zeros in either segment.
        """
        plan_part = re.sub(r"\D", "", str(self.plan_id or ""))
        ssn_part  = re.sub(r"\D", "", str(self.ssn  or ""))
        return (
            len(plan_part) >= 1
            and len(ssn_part) >= 1
            and not re.match(r"^0+$", plan_part)
            and not re.match(r"^0+$", ssn_part)
        )


class CompositeKeyBuilder:
    """
    P3.4 — Composite Key Builder.

    build(plan_id, ssn, extension) → "PPPPPPPPPXXXXXXXXX[ext]"
    validate(composite_id)         → bool
    parse(composite_id)            → ParticipantKey
    """

    VALID_EXTENSIONS = {"", "B", "Q", "F", "RM", "EF", "AA"}

    def build(
        self,
        plan_id: str,
        ssn: str,
        extension: str = "",
    ) -> str:
        """Build a composite participant ID from components."""
        if extension.upper() not in self.VALID_EXTENSIONS:
            logger.warning("composite_key.unknown_extension", ext=extension)
        key = ParticipantKey(
            plan_id=plan_id,
            ssn=ssn,
            extension=extension.upper(),
        )
        if not key.is_valid:
            logger.warning("composite_key.invalid",
                           plan_id=plan_id, ssn_len=len(ssn))
        return key.composite_id

    def validate(self, composite_id: str) -> bool:
        """Validate a composite participant ID."""
        if not composite_id or len(composite_id) < 17:
            return False
        base = composite_id[:17]
        plan_part = base[:9]
        ssn_part  = base[9:]
        if re.match(r"^0+$", plan_part) or re.match(r"^0+$", ssn_part):
            return False
        # Extension (if present) must be a known code
        ext = composite_id[17:]
        return ext in self.VALID_EXTENSIONS

    def parse(self, composite_id: str) -> Optional[ParticipantKey]:
        """Reverse-parse a composite ID into its components."""
        if not composite_id or len(composite_id) < 17:
            return None
        plan_part = composite_id[:9]
        ssn_part  = composite_id[9:17]
        extension = composite_id[17:] if len(composite_id) > 17 else ""
        return ParticipantKey(
            plan_id=plan_part.lstrip("0") or "0",
            ssn=ssn_part,
            extension=extension,
        )

    def build_batch(
        self,
        rows: list[dict],
        plan_id_field: str = "PLANID",
        ssn_field: str = "SSNUM",
        extension_field: Optional[str] = None,
    ) -> list[str]:
        """
        Build composite IDs for a batch of Relius rows.
        Used by P3.1 ETL codegen and P5.1 Frp writer.
        """
        results = []
        for row in rows:
            plan_id = str(row.get(plan_id_field) or row.get(plan_id_field.lower()) or "")
            ssn     = str(row.get(ssn_field)     or row.get(ssn_field.lower())     or "")
            ext     = str(row.get(extension_field or "", "") or "") if extension_field else ""
            results.append(self.build(plan_id, ssn, ext))
        return results


# ── Module-level singletons ───────────────────────────────────
rule_engine  = RuleEngine()
key_builder  = CompositeKeyBuilder()
