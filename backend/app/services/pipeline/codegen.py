"""
app/services/pipeline/codegen.py
P3.1 — ETL Code Generator

Reads approved MappingEntry rows for an engagement and generates:
  1. Per-domain Python extraction scripts (Jinja2 templates)
  2. Fixed-length format specification documents
  3. A master run script that orchestrates all domains in load order

The generator has two modes:
  - template_only  : pure Jinja2 rendering — fast, deterministic, no LLM call
  - ai_enhanced    : Jinja2 + Claude reviews and improves the generated code
                     (handles edge cases, adds business-rule comments, improves
                     transform_rule expressions for complex crosswalks)

Frp load order (P4.5) — enforced in master script:
  Plan → Division → Fund Control → Share Account → Plan Locator → Person →
  Participant Header → Participant Fund/Source/AI → Cash Control →
  HIVR (atomic) → Disbursement → Loans → Compensation → Auto Rebalance →
  File Maintenance
"""
from __future__ import annotations

import hashlib
import json
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

logger = structlog.get_logger(__name__)

# Frp load order — domain ID → position (lower = earlier)
FRP_LOAD_ORDER: dict[str, int] = {
    "plan":       1,
    "invest":     2,
    "part":       3,
    "cash":       4,
    "loans":      5,
    "payroll":    6,
    "compliance": 7,
    "annuity":    8,
}

# Frp target field → fixed-length spec defaults
# width, type (AN/N/D/B), align (left/right)
FIELD_WIDTH_DEFAULTS: dict[str, tuple[int, str, str]] = {
    "CHAR(17)":      (17,  "AN", "left"),
    "CHAR(10)":      (10,  "AN", "left"),
    "CHAR(5)":       (5,   "AN", "left"),
    "CHAR(3)":       (3,   "AN", "left"),
    "CHAR(1)":       (1,   "AN", "left"),
    "VARCHAR":       (30,  "AN", "left"),
    "VARCHAR2":      (30,  "AN", "left"),
    "DATE":          (8,   "D",  "left"),
    "INTEGER":       (10,  "N",  "right"),
    "BIGINT":        (13,  "N",  "right"),
    "DECIMAL":       (13,  "N",  "right"),
    "DECIMAL(13,2)": (13,  "N",  "right"),
    "DECIMAL(7,5)":  (9,   "N",  "right"),
    "DECIMAL(6,4)":  (8,   "N",  "right"),
    "DECIMAL(5,2)":  (6,   "N",  "right"),
    "BOOLEAN":       (1,   "B",  "left"),
    "NUMBER":        (13,  "N",  "right"),
}


@dataclass
class FieldSpec:
    src_field: str
    tgt_field: str
    data_type: str
    mapping_type: str
    transform_rule: str = ""
    is_constant: bool = False
    constant_value: str = ""
    is_multi_source: bool = False
    multi_sources: list[dict] = field(default_factory=list)
    description: str = ""
    width: int = 30
    field_type: str = "AN"
    align: str = "left"


@dataclass
class TableSpec:
    name: str
    domain_id: str
    fields: list[FieldSpec] = field(default_factory=list)
    pk_fields: list[str] = field(default_factory=list)
    where_clause: str = ""
    row_estimate: Optional[int] = None

    @property
    def tgt_fields(self) -> list[str]:
        return [f.tgt_field for f in self.fields]

    @property
    def total_width(self) -> int:
        return sum(f.width for f in self.fields)


@dataclass
class GeneratedArtefact:
    filename: str
    content: str
    artefact_type: str           # "etl_script" | "format_spec" | "master_script"
    domain_id: Optional[str]
    content_hash: str = ""

    def __post_init__(self):
        self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


class ETLCodegen:
    """
    P3.1 — ETL Code Generator.

    generate(engagement_id, mappings, config, db) → list[GeneratedArtefact]
    """

    TEMPLATE_DIR = Path(__file__).parent / "templates"

    def __init__(self):
        self._jinja = Environment(
            loader=FileSystemLoader(str(self.TEMPLATE_DIR)),
            autoescape=select_autoescape(enabled_extensions=()),  # no HTML escaping for Python code
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        # Add tojson filter (same as json.dumps)
        self._jinja.filters["tojson"] = lambda v, **kw: json.dumps(v, **kw)
        self._jinja.filters["ljust"] = lambda s, w: str(s).ljust(w)
        self._jinja.filters["truncate"] = self._truncate

    # ── Main entry point ──────────────────────────────────────
    async def generate(
        self,
        engagement_id: str,
        mappings: list,          # list of MappingEntry ORM objects
        config: "ETLGenerateConfig",
        ai_enhanced: bool = True,
    ) -> list[GeneratedArtefact]:
        """
        Generate all ETL artefacts for an engagement.
        Returns a list of GeneratedArtefact objects ready to persist.
        """
        logger.info("codegen.start", engagement=engagement_id,
                    mappings=len(mappings), format=config.output_format)

        # Group approved mappings by domain then table
        domain_tables = self._group_mappings(mappings)

        if not domain_tables:
            logger.warning("codegen.no_mappings", engagement=engagement_id)
            return []

        artefacts: list[GeneratedArtefact] = []
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Sort domains by Frp load order
        ordered_domains = sorted(
            domain_tables.keys(),
            key=lambda d: FRP_LOAD_ORDER.get(d, 99),
        )

        for domain_id in ordered_domains:
            tables = domain_tables[domain_id]
            domain_name = domain_id.replace("_", " ").title()

            # ── Extract script ────────────────────────────────
            script_name = f"extract_{domain_id}.py"
            extract_ctx = self._build_extract_context(
                engagement_id=engagement_id,
                domain_id=domain_id,
                domain_name=domain_name,
                script_name=script_name,
                tables=tables,
                config=config,
                generated_at=now_str,
            )
            extract_code = self._render("extract_script.py.j2", extract_ctx)

            # AI enhancement: Claude reviews and improves the generated code
            if ai_enhanced:
                extract_code = await self._ai_enhance_script(
                    extract_code, domain_name, config.output_format
                )

            artefacts.append(GeneratedArtefact(
                filename=script_name,
                content=extract_code,
                artefact_type="etl_script",
                domain_id=domain_id,
            ))

            # ── Format spec (fixed-length only) ──────────────
            if config.output_format == "fixed":
                spec_name = f"format_spec_{domain_id}.py"
                ffl_spec_ctx = self._build_format_spec_context(
                    engagement_id=engagement_id,
                    domain_id=domain_id,
                    domain_name=domain_name,
                    tables=tables,
                    config=config,
                    generated_at=now_str,
                )
                spec_code = self._render("format_spec.py.j2", ffl_spec_ctx)
                artefacts.append(GeneratedArtefact(
                    filename=spec_name,
                    content=spec_code,
                    artefact_type="format_spec",
                    domain_id=domain_id,
                ))

        # ── Master run script ─────────────────────────────────
        master = self._generate_master_script(
            engagement_id=engagement_id,
            ordered_domains=ordered_domains,
            config=config,
            generated_at=now_str,
        )
        artefacts.append(master)

        # ── Mapping summary JSON ──────────────────────────────
        summary = self._generate_mapping_summary(engagement_id, mappings, ordered_domains, now_str)
        artefacts.append(summary)

        logger.info("codegen.complete", engagement=engagement_id, artefacts=len(artefacts))
        return artefacts

    # ── Context builders ──────────────────────────────────────
    def _group_mappings(self, mappings: list) -> dict[str, list[TableSpec]]:
        """Group MappingEntry ORM rows into domain → [TableSpec] structure."""
        domain_tables: dict[str, dict[str, TableSpec]] = {}

        for m in mappings:
            # Only include confirmed/auto_approved mappings
            if m.status not in ("confirmed", "auto_approved"):
                continue

            domain_id = m.domain_id
            table_name = m.src_table

            if domain_id not in domain_tables:
                domain_tables[domain_id] = {}
            if table_name not in domain_tables[domain_id]:
                domain_tables[domain_id][table_name] = TableSpec(
                    name=table_name,
                    domain_id=domain_id,
                )

            tbl = domain_tables[domain_id][table_name]

            # Derive field width from target data type
            width, ftype, align = self._field_dimensions(m.data_type if hasattr(m, "data_type") else "VARCHAR")

            fspec = FieldSpec(
                src_field=m.src_field,
                tgt_field=m.tgt_field,
                data_type=getattr(m, "data_type", "VARCHAR") or "VARCHAR",
                mapping_type=m.mapping_type or "direct",
                transform_rule=m.transform_rule or "",
                is_constant=m.is_constant or False,
                constant_value=m.constant_value or "",
                is_multi_source=m.is_multi_source or False,
                multi_sources=m.multi_sources or [],
                description=m.note or "",
                width=width,
                field_type=ftype,
                align=align,
            )
            tbl.fields.append(fspec)

            # Mark PK fields (heuristic: field ending in ID or containing PLANID, SSNUM)
            if any(pk in m.src_field.upper() for pk in ["PLANID", "SSNUM", "_ID", "PLANNO"]):
                if m.src_field not in tbl.pk_fields:
                    tbl.pk_fields.append(m.src_field)

        # Flatten to domain → [TableSpec]
        return {
            domain: list(tables.values())
            for domain, tables in domain_tables.items()
        }

    def _build_extract_context(
        self,
        engagement_id: str,
        domain_id: str,
        domain_name: str,
        script_name: str,
        tables: list[TableSpec],
        config: "ETLGenerateConfig",
        generated_at: str,
    ) -> dict:
        # Build FFL spec dict for template
        ffl_spec = {}
        for tbl in tables:
            for f in tbl.fields:
                ffl_spec[f.tgt_field] = {
                    "width": f.width,
                    "type": f.field_type,
                    "align": f.align,
                }
        return {
            "script_name": script_name,
            "engagement_id": engagement_id,
            "domain_id": domain_id,
            "domain_name": domain_name,
            "generated_at": generated_at,
            "output_format": config.output_format,
            "encoding": config.encoding,
            "null_indicator": config.null_indicator,
            "date_format": config.date_format,
            "tables": tables,
            "ffl_spec": ffl_spec,
        }

    def _build_format_spec_context(
        self,
        engagement_id: str,
        domain_id: str,
        domain_name: str,
        tables: list[TableSpec],
        config: "ETLGenerateConfig",
        generated_at: str,
    ) -> dict:
        return {
            "engagement_id": engagement_id,
            "domain_id": domain_id,
            "domain_name": domain_name,
            "generated_at": generated_at,
            "encoding": config.encoding,
            "null_indicator": config.null_indicator,
            "date_format": config.date_format,
            "tables": tables,
        }

    # ── Master run script ─────────────────────────────────────
    def _generate_master_script(
        self,
        engagement_id: str,
        ordered_domains: list[str],
        config: "ETLGenerateConfig",
        generated_at: str,
    ) -> GeneratedArtefact:
        """
        Generate a master orchestrator script that runs all domain extracts
        in the correct Frp load order.
        """
        lines = [
            '#!/usr/bin/env python3',
            f'"""',
            f'MigrateIQ — Master ETL Run Script',
            f'Engagement : {engagement_id}',
            f'Generated  : {generated_at}',
            f'Load order : {" → ".join(ordered_domains)}',
            f'',
            f'Runs all domain extract scripts in Frp load order (P4.5).',
            f'Usage: python run_migration.py [--output-dir ./output] [--dry-run]',
            f'"""',
            'import argparse',
            'import logging',
            'import sys',
            'from pathlib import Path',
            '',
            'logging.basicConfig(level=logging.INFO,',
            '    format="%(asctime)s [%(levelname)s] %(message)s")',
            'log = logging.getLogger("migrateiq.master")',
            '',
            '# Import domain extract modules',
        ]
        for domain in ordered_domains:
            lines.append(f'import extract_{domain}')
        lines += [
            '',
            '',
            'LOAD_ORDER = [',
        ]
        for domain in ordered_domains:
            lines.append(f'    ("extract_{domain}", extract_{domain}.main),  '
                         f'# Frp load position: {FRP_LOAD_ORDER.get(domain, 99)}')
        lines += [
            ']',
            '',
            '',
            'def main():',
            '    parser = argparse.ArgumentParser(description="MigrateIQ ETL runner")',
            '    parser.add_argument("--output-dir", default="output", help="Output directory")',
            '    parser.add_argument("--dry-run", action="store_true",',
            '                        help="Validate setup without writing files")',
            '    parser.add_argument("--domain", default=None,',
            '                        help="Run only this domain (default: all)")',
            '    args = parser.parse_args()',
            '',
            '    out_dir = Path(args.output_dir)',
            '    out_dir.mkdir(parents=True, exist_ok=True)',
            '',
            '    if args.dry_run:',
            '        log.info("DRY RUN — no files will be written")',
            '',
            '    total_rows = 0',
            '    for module_name, extract_fn in LOAD_ORDER:',
            '        if args.domain and not module_name.endswith(args.domain):',
            '            continue',
            '        log.info(f"Running {module_name}…")',
            '        try:',
            '            if not args.dry_run:',
            '                rows = extract_fn(str(out_dir))',
            '                total_rows += rows',
            '                log.info(f"  {module_name}: {rows} rows")',
            '            else:',
            '                log.info(f"  {module_name}: [dry run — skipped]")',
            '        except Exception as exc:',
            '            log.error(f"  {module_name} FAILED: {exc}")',
            '            sys.exit(1)',
            '',
            '    log.info(f"Migration complete. Total rows extracted: {total_rows}")',
            '',
            '',
            'if __name__ == "__main__":',
            '    main()',
        ]
        return GeneratedArtefact(
            filename="run_migration.py",
            content="\n".join(lines) + "\n",
            artefact_type="master_script",
            domain_id=None,
        )

    # ── Mapping summary JSON ──────────────────────────────────
    def _generate_mapping_summary(
        self,
        engagement_id: str,
        mappings: list,
        ordered_domains: list[str],
        generated_at: str,
    ) -> GeneratedArtefact:
        """JSON summary of all mappings used in this ETL generation run."""
        summary = {
            "engagement_id": engagement_id,
            "generated_at": generated_at,
            "total_mappings": len(mappings),
            "load_order": ordered_domains,
            "by_domain": {},
        }
        for m in mappings:
            domain = m.domain_id
            if domain not in summary["by_domain"]:
                summary["by_domain"][domain] = {"confirmed": 0, "auto_approved": 0, "skipped": 0}
            if m.status == "confirmed":
                summary["by_domain"][domain]["confirmed"] += 1
            elif m.status == "auto_approved":
                summary["by_domain"][domain]["auto_approved"] += 1
            else:
                summary["by_domain"][domain]["skipped"] += 1

        content = json.dumps(summary, indent=2)
        return GeneratedArtefact(
            filename="mapping_summary.json",
            content=content,
            artefact_type="mapping_summary",
            domain_id=None,
        )

    # ── AI enhancement (Claude) ───────────────────────────────
    async def _ai_enhance_script(
        self,
        script_code: str,
        domain_name: str,
        output_format: str,
    ) -> str:
        """
        Ask Claude to review and improve a generated ETL script.
        Specifically: improve transform_rule expressions, add business-rule
        comments, flag any potential data quality issues.

        If the LLM call fails, returns the original template-rendered code unchanged.
        """
        from app.core.config import get_settings
        settings = get_settings()

        prompt = textwrap.dedent(f"""
            You are reviewing a generated Python ETL script for a pension data migration
            (Relius → Frp / FRP). The domain is: {domain_name}.
            Output format: {output_format}.

            Review the script below and:
            1. Fix any obviously incorrect transform_rule expressions
            2. Add brief inline comments explaining the business meaning of
               non-obvious transforms (date conversions, crosswalks, composite keys)
            3. Flag (via # WARNING:) any fields where data truncation is likely
            4. Do NOT change the structure, imports, function signatures, or template variables

            Return ONLY the improved Python script — no preamble, no markdown fences.

            SCRIPT:
            {script_code[:4000]}
        """).strip()

        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            msg = await client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            enhanced = msg.content[0].text.strip()
            # Sanity check: must still contain def main and def transform_row
            if "def main" in enhanced and "def transform_row" in enhanced:
                logger.info("codegen.ai_enhanced", domain=domain_name)
                return enhanced
            logger.warning("codegen.ai_enhancement_invalid", domain=domain_name)
            return script_code

        except Exception as exc:
            logger.warning("codegen.ai_enhancement_failed", domain=domain_name, error=str(exc))
            return script_code

    # ── Helpers ───────────────────────────────────────────────
    def _render(self, template_name: str, context: dict) -> str:
        tmpl = self._jinja.get_template(template_name)
        return tmpl.render(**context)

    @staticmethod
    def _field_dimensions(data_type: str) -> tuple[int, str, str]:
        """Return (width, field_type, align) for a given data type string."""
        dt = (data_type or "VARCHAR").upper().strip()
        # Exact match
        if dt in FIELD_WIDTH_DEFAULTS:
            return FIELD_WIDTH_DEFAULTS[dt]
        # Prefix match
        for prefix, dims in FIELD_WIDTH_DEFAULTS.items():
            if dt.startswith(prefix.rstrip(")")):
                return dims
        # Fallback
        return (30, "AN", "left")

    @staticmethod
    def _truncate(s: str, length: int = 255, end: str = "...", leeway: int = 0) -> str:
        s = str(s)
        if len(s) <= length + leeway:
            return s
        return s[:length - len(end)] + end


@dataclass
class ETLGenerateConfig:
    """Configuration for a single ETL generation run."""
    output_format: str = "fixed"     # fixed | csv | json
    extraction_mode: str = "full"    # full | incremental | delta
    encoding: str = "UTF-8"
    null_indicator: str = ""
    date_format: str = "YYYYMMDD"


# Module-level singleton
etl_codegen = ETLCodegen()
