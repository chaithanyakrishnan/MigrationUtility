"""
app/services/schema/profiler.py
P1.2 — Domain Profiler

Classifies Relius tables into the 19 canonical domains and scores completeness.

Domain and table data is loaded at startup from:
  app/reference_data/relius_schema.json

That JSON is built from the authoritative Relius schema HTML reference.
To update the domain mapping: replace or update that JSON file.
No code changes required.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import structlog

from app.services.schema.extractor import ParsedTable, SchemaParseResult

logger = structlog.get_logger(__name__)
log    = logging.getLogger(__name__)

# Path to the reference data file — the ONLY source of truth for domain mappings
_REFERENCE_FILE = Path(__file__).parent.parent.parent / "reference_data" / "relius_schema.json"


@lru_cache(maxsize=1)
def _load_reference() -> dict:
    """
    Load the Relius schema reference JSON once and cache it.
    Returns the full reference dict with table_to_domain, domain_to_tables,
    domain_meta keys.
    Raises FileNotFoundError if the reference file is missing.
    """
    if not _REFERENCE_FILE.exists():
        raise FileNotFoundError(
            f"Relius schema reference not found: {_REFERENCE_FILE}\n"
            f"Expected file: app/reference_data/relius_schema.json"
        )
    with open(_REFERENCE_FILE) as f:
        data = json.load(f)
    log.info(
        "profiler.reference_loaded tables=%d domains=%d",
        data.get("tables", 0),
        data.get("domains", 0),
    )
    return data


def get_table_to_domain() -> dict[str, str]:
    """Return the table→domain mapping from the reference file."""
    return _load_reference()["table_to_domain"]


def get_valid_tables() -> frozenset:
    """
    Return the set of all known Relius table names.
    Used by the PDF parser as a parse-time whitelist.
    """
    return frozenset(_load_reference()["table_to_domain"].keys())


def get_domain_meta() -> dict[str, dict]:
    """Return domain display metadata (name, icon)."""
    return _load_reference()["domain_meta"]


# ── Domain profile data classes ───────────────────────────────

@dataclass
class DomainProfile:
    id: str
    name: str
    icon: str
    tables: list[ParsedTable] = field(default_factory=list)
    completeness: int = 0
    needs_review: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def table_count(self) -> int:
        return len(self.tables)

    @property
    def field_count(self) -> int:
        return sum(len(t.fields) for t in self.tables)


@dataclass
class ProfileResult:
    domains: list[DomainProfile] = field(default_factory=list)
    domain_map: dict[str, str] = field(default_factory=dict)  # table_name → domain_id

    def get_domain(self, domain_id: str) -> Optional[DomainProfile]:
        return next((d for d in self.domains if d.id == domain_id), None)


# ── Profiler ──────────────────────────────────────────────────

class DomainProfiler:
    """
    Classifies ParsedTable objects into domains using the reference JSON.
    No hardcoded mappings — all data comes from relius_schema.json.
    """

    def profile(self, parse_result: SchemaParseResult) -> ProfileResult:
        result = ProfileResult()

        table_to_domain = get_table_to_domain()
        domain_meta     = get_domain_meta()

        # Initialise a profile for every domain in the reference
        domains: dict[str, DomainProfile] = {
            name: DomainProfile(
                id=name,
                name=name,
                icon=meta.get("icon", "📁"),
            )
            for name, meta in domain_meta.items()
        }
        # Always have an "Other" bucket for unknown tables
        if "Other" not in domains:
            domains["Other"] = DomainProfile(id="Other", name="Other", icon="📁")

        for table in parse_result.tables:
            domain_name = table_to_domain.get(table.name.upper(), "Other")
            if domain_name not in domains:
                domains[domain_name] = DomainProfile(
                    id=domain_name, name=domain_name, icon="📁"
                )
            domains[domain_name].tables.append(table)
            result.domain_map[table.name.upper()] = domain_name

        # Score and flag
        for domain in domains.values():
            domain.completeness = self._score(domain)
            domain.needs_review = domain.completeness < 80
            if domain.needs_review and domain.table_count > 0:
                domain.warnings.append(
                    f"{domain.completeness}% complete — review recommended"
                )

        # Return only domains that have tables, sorted by table count
        result.domains = sorted(
            [d for d in domains.values() if d.table_count > 0],
            key=lambda d: (-d.table_count, d.name),
        )

        parsed_names   = {t.name.upper() for t in parse_result.tables}
        valid_names    = frozenset(get_table_to_domain().keys())
        missing_tables = sorted(valid_names - parsed_names)
        extra_tables   = sorted(parsed_names - valid_names)
        total_parsed   = sum(d.table_count for d in result.domains)

        logger.info(
            "profiler.complete",
            domains=len(result.domains),
            tables_parsed=total_parsed,
            tables_expected=len(valid_names),
            missing_count=len(missing_tables),
            extra_count=len(extra_tables),
        )
        if missing_tables:
            logger.warning(
                "profiler.missing_tables",
                count=len(missing_tables),
                tables=missing_tables[:20],
            )
        # Note: field count may differ slightly between PDF (raw) and reference
        # (curated). Extra tables are a real issue; extra fields are normal.
        if extra_tables:
            logger.info(
                "profiler.extra_tables_info",
                count=len(extra_tables),
                note="Extra tables not in reference — will be classified as Other",
            )
        return result

    def _score(self, domain: DomainProfile) -> int:
        # Normalise to the plain-dict shape the shared scorer expects so the
        # heuristic lives in exactly one place (also reused for SME edits).
        tables = [
            {"fields": [
                {"is_pk": f.is_pk, "is_fk": f.is_fk, "description": f.description}
                for f in t.fields
            ]}
            for t in domain.tables
        ]
        return score_schema_completeness(tables)


def score_schema_completeness(tables: list[dict]) -> int:
    """
    Domain completeness heuristic (0–100), shared by the profiler (parse time)
    and the review endpoint (after SME edits).

    `tables` is a list of {"fields": [{"is_pk", "is_fk", "description"}, ...]}.
    Base 20 for having tables, then +20 each for: a PK present, >30% of fields
    described, an FK present, and the domain spanning ≥3 tables.
    """
    if not tables:
        return 0
    score = 20
    if any(any(f.get("is_pk") for f in t.get("fields", [])) for t in tables):
        score += 20
    total = sum(len(t.get("fields", [])) for t in tables)
    described = sum(
        sum(1 for f in t.get("fields", []) if (f.get("description") or "").strip())
        for t in tables
    )
    if total > 0 and described / total > 0.3:
        score += 20
    if any(any(f.get("is_fk") for f in t.get("fields", [])) for t in tables):
        score += 20
    if len(tables) >= 3:
        score += 20
    return score


def build_parse_result_dict(parse_result: SchemaParseResult, profile: ProfileResult) -> dict:
    """
    Build the SchemaFile.parse_result dict from an extractor result + profile.
    Shared by the upload pipeline and the schema-library seed path so both
    produce an identical shape (tables_detail / domains_detail + counts).
    """
    tables_detail = [
        {
            "name":        table.name,
            "domain_id":   profile.domain_map.get(table.name.upper(), "unknown"),
            "description": table.description,
            "fields": [
                {
                    "field":       f.field_name,
                    "type":        f.data_type,
                    "nullable":    f.nullable,
                    "is_pk":       f.is_pk,
                    "is_fk":       f.is_fk,
                    "references":  f.references,
                    "description": f.description,
                }
                for f in table.fields
            ],
        }
        for table in parse_result.tables
    ]
    domains_detail = [
        {
            "id":           d.id,
            "name":         d.name,
            "icon":         d.icon,
            "table_count":  d.table_count,
            "field_count":  d.field_count,
            "completeness": d.completeness,
            "needs_review": d.needs_review,
            "warnings":     d.warnings,
            "tables":       [t.name for t in d.tables],
        }
        for d in profile.domains
    ]
    return {
        "tables":         parse_result.table_count,
        "fields":         parse_result.field_count,
        "fk_count":       parse_result.fk_count,
        "domains":        len([d for d in profile.domains if d.table_count > 0]),
        "warnings":       parse_result.warnings,
        "domains_detail": domains_detail,
        "tables_detail":  tables_detail,
    }


# Module-level singleton
domain_profiler = DomainProfiler()
