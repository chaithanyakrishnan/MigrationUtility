"""
app/api/routes/knowledge_base.py
Knowledge Base endpoints (v5 KB architecture).

The Relius KB and Frp KB are one-time, reusable catalogues that every
migration project draws on. This module owns their lifecycle:
  * GET  /knowledge-bases              — status of both (Home launchpad)
  * Relius/Frp content + save endpoints are added in later phases.
"""
from __future__ import annotations

import re
import structlog
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import (
    KnowledgeBase, KBReliusDomain, KBReliusField, AuditEvent,
    KBFrpRecord, KBFrpField, KBTransactionCard, KBTransactionCardField,
)
from app.schemas.schemas import (
    KnowledgeBaseSummary, KnowledgeBasesStatus,
    KBReliusCatalog, KBReliusDomainOut, KBReliusFieldOut, KBReliusDomainReview,
    KBFrpCatalog, KBFrpRecordOut, KBFrpFieldOut, KBFrpRecordReview,
    KBFrpTxnCatalog, KBTxnCardOut, KBTxnFieldOut, KBTxnCardReview,
)
from app.services.kb.relius_seed import RELIUS_DOMAINS, relius_stats
from app.services.kb.frp_seed import (
    FRP_RECORDS, FRP_TXN_CARDS, FRP_LOAD_ORDER, FRP_CONSTANTS, frp_stats,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/knowledge-bases")

VALID_KINDS = {"relius", "frp"}


def _parse_schema_file(filename: str, content: bytes) -> dict:
    """
    Run the real extractor + domain profiler on an uploaded schema file and
    return the parse-result dict (tables_detail / domains_detail + counts).
    This is the same pipeline the engagement upload uses — including the Relius
    'Database Layout (By Tables)' PDF parser.
    """
    from app.services.schema.extractor import extractor
    from app.services.schema.profiler import domain_profiler, build_parse_result_dict

    pr = extractor.extract(filename, content)
    profile = domain_profiler.profile(pr)
    result = build_parse_result_dict(pr, profile)
    if pr.table_count == 0 or pr.field_count == 0:
        reason = "; ".join(pr.warnings) or (
            "No tables or fields could be extracted — the file may be the wrong "
            "format or not a recognised schema."
        )
        raise HTTPException(422, reason)
    return result


def _merge_parse_results(results: list[dict]) -> dict:
    """
    Merge several parse-result dicts (one per uploaded file) into one catalogue.
    Tables are deduped by name (fields unioned by field name); domain metadata
    is carried forward from whichever file first described a domain.
    """
    tables: dict[str, dict] = {}
    domains_meta: dict[str, dict] = {}
    for r in results:
        for dm in r.get("domains_detail", []):
            domains_meta.setdefault(dm["id"], dm)
        for t in r.get("tables_detail", []):
            key = t["name"].upper()
            entry = tables.setdefault(key, {
                "name": t["name"], "domain_id": t.get("domain_id", "unknown"),
                "description": t.get("description", ""), "fields": {},
            })
            if entry["domain_id"] in (None, "", "unknown"):
                entry["domain_id"] = t.get("domain_id", entry["domain_id"])
            for f in t.get("fields", []):
                entry["fields"].setdefault(f.get("field", ""), f)
    tables_detail = [
        {"name": e["name"], "domain_id": e["domain_id"], "description": e["description"],
         "fields": list(e["fields"].values())}
        for e in tables.values()
    ]
    return {
        "tables": len(tables_detail),
        "fields": sum(len(t["fields"]) for t in tables_detail),
        "fk_count": 0,
        "domains": len(domains_meta),
        "domains_detail": list(domains_meta.values()),
        "tables_detail": tables_detail,
        "warnings": [],
    }


def _summary(kb: KnowledgeBase | None, kind: str) -> KnowledgeBaseSummary:
    if kb is None:
        return KnowledgeBaseSummary(kind=kind, status="draft", built=False, stats={})
    return KnowledgeBaseSummary(
        kind=kb.kind,
        status=kb.status,
        built=kb.status == "built",
        version=kb.version,
        stats=kb.stats or {},
        built_at=kb.built_at,
    )


async def get_kb(db: AsyncSession, kind: str) -> KnowledgeBase | None:
    """Fetch the single KB row for a kind, or None if never created."""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.kind == kind))
    return result.scalar_one_or_none()


async def get_or_create_kb(db: AsyncSession, kind: str) -> KnowledgeBase:
    """Fetch the KB row for a kind, creating a draft if it does not exist."""
    if kind not in VALID_KINDS:
        raise HTTPException(400, f"Unknown KB kind '{kind}'")
    kb = await get_kb(db, kind)
    if kb is None:
        kb = KnowledgeBase(kind=kind, status="draft", stats={})
        db.add(kb)
        await db.flush()
    return kb


@router.get("", response_model=KnowledgeBasesStatus)
async def get_knowledge_bases(db: AsyncSession = Depends(get_db)):
    """Status of both Knowledge Bases — drives the Home launchpad."""
    relius = await get_kb(db, "relius")
    frp = await get_kb(db, "frp")
    r = _summary(relius, "relius")
    o = _summary(frp, "frp")
    return KnowledgeBasesStatus(relius=r, frp=o, both_built=r.built and o.built)


# ── Relius KB ─────────────────────────────────────────────────
async def _load_relius_domains(db: AsyncSession, kb_id: str) -> list[KBReliusDomain]:
    result = await db.execute(
        select(KBReliusDomain)
        .where(KBReliusDomain.kb_id == kb_id)
        .options(selectinload(KBReliusDomain.fields))
        .order_by(KBReliusDomain.sort_order)
    )
    return list(result.scalars().all())


def _domain_out(d: KBReliusDomain) -> KBReliusDomainOut:
    fields = sorted(d.fields, key=lambda f: f.sort_order)
    return KBReliusDomainOut(
        id=d.id, domain_id=d.domain_id, name=d.name, icon=d.icon,
        table_count=d.table_count or 0, row_estimate=d.row_estimate,
        completeness=d.completeness or 0, tables=d.tables or [], approved=d.approved,
        fields=[KBReliusFieldOut.model_validate(f) for f in fields],
    )


async def _seed_relius(db: AsyncSession, kb: KnowledgeBase) -> None:
    """Populate the Relius KB from the reference catalogue (idempotent)."""
    existing = await _load_relius_domains(db, kb.id)
    if existing:
        return
    for di, dom in enumerate(RELIUS_DOMAINS):
        domain = KBReliusDomain(
            kb_id=kb.id, domain_id=dom["domain_id"], name=dom["name"], icon=dom["icon"],
            table_count=len(dom["tables"]), row_estimate=dom["row_estimate"],
            completeness=dom["completeness"], tables=dom["tables"], sort_order=di,
        )
        db.add(domain)
        await db.flush()
        for fi, f in enumerate(dom["fields"]):
            db.add(KBReliusField(
                domain_id=domain.id, table_name=f["table"], field_name=f["field"],
                display_name=f["name"], data_type=f["data_type"], description=f["description"],
                is_key=f["is_key"], included=True, approved=False, sort_order=fi,
            ))


async def _populate_relius_from_parse(db: AsyncSession, kb: KnowledgeBase, result: dict) -> None:
    """Replace the Relius KB catalogue with real parsed schema data."""
    for old in await _load_relius_domains(db, kb.id):
        await db.delete(old)
    await db.flush()

    # group parsed tables by domain
    tables_by_domain: dict[str, list[dict]] = {}
    for t in result.get("tables_detail", []):
        tables_by_domain.setdefault(t.get("domain_id", "unknown"), []).append(t)

    meta = {d["id"]: d for d in result.get("domains_detail", [])}
    # keep only domains that actually carry tables, largest first
    domain_ids = [did for did in tables_by_domain if tables_by_domain[did]]
    domain_ids.sort(key=lambda d: -len(tables_by_domain[d]))

    for di, did in enumerate(domain_ids):
        m = meta.get(did, {})
        tbls = tables_by_domain[did]
        field_total = sum(len(t.get("fields", [])) for t in tbls)
        domain = KBReliusDomain(
            kb_id=kb.id, domain_id=did, name=m.get("name", did.title()),
            icon=m.get("icon", "📁"), table_count=len(tbls),
            row_estimate=None, completeness=m.get("completeness", 0),
            tables=[t["name"] for t in tbls], sort_order=di,
        )
        db.add(domain)
        await db.flush()
        fi = 0
        for t in tbls:
            for f in t.get("fields", []):
                db.add(KBReliusField(
                    domain_id=domain.id, table_name=t["name"], field_name=f.get("field", ""),
                    display_name=f.get("field", ""), data_type=f.get("type") or "",
                    description=f.get("description") or "", is_key=bool(f.get("is_pk")),
                    included=True, approved=False, sort_order=fi,
                ))
                fi += 1


@router.post("/relius/analyze", response_model=KBReliusCatalog)
async def analyze_relius(
    file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse the Relius schema into the KB catalogue. When a file is uploaded it
    is parsed by the real extractor (SQL/JSON/XLSX/PDF/DOCX — including the Relius
    layout PDF parser). With no file, falls back to the reference seed for demos.
    """
    kb = await get_or_create_kb(db, "relius")
    parsed = False
    if file is not None:
        content = await file.read()
        result = _parse_schema_file(file.filename or "upload", content)
        await _populate_relius_from_parse(db, kb, result)
        parsed = True
        summary = (f"Relius schema parsed from '{file.filename}' — "
                   f"{result['tables']} tables · {result['fields']} fields · {result['domains']} domains")
    else:
        await _seed_relius(db, kb)
        summary = "Relius schema seeded from reference catalogue (no file uploaded)"

    db.add(AuditEvent(
        event_type="kb.relius.analyzed", actor_type="system", actor_id="system",
        summary=summary, detail={"parsed_from_upload": parsed},
    ))
    await db.commit()
    domains = await _load_relius_domains(db, kb.id)
    return KBReliusCatalog(
        kind="relius", status=kb.status, stats=kb.stats or {},
        domains=[_domain_out(d) for d in domains],
    )


@router.get("/relius", response_model=KBReliusCatalog)
async def get_relius(db: AsyncSession = Depends(get_db)):
    """Return the Relius KB catalogue (domains + fields)."""
    kb = await get_kb(db, "relius")
    if kb is None:
        return KBReliusCatalog(kind="relius", status="draft", stats={}, domains=[])
    domains = await _load_relius_domains(db, kb.id)
    return KBReliusCatalog(
        kind="relius", status=kb.status, stats=kb.stats or {},
        domains=[_domain_out(d) for d in domains],
    )


@router.patch("/relius/domains/{domain_id}", response_model=KBReliusDomainOut)
async def review_relius_domain(
    domain_id: str,
    payload: KBReliusDomainReview,
    db: AsyncSession = Depends(get_db),
):
    """Persist SME review for one Relius domain (field edits + approvals)."""
    kb = await get_kb(db, "relius")
    if kb is None:
        raise HTTPException(404, "Relius KB not initialised")
    result = await db.execute(
        select(KBReliusDomain)
        .where(KBReliusDomain.kb_id == kb.id, KBReliusDomain.domain_id == domain_id)
        .options(selectinload(KBReliusDomain.fields))
    )
    domain = result.scalar_one_or_none()
    if domain is None:
        raise HTTPException(404, f"Domain '{domain_id}' not found in Relius KB")

    edits = {e.id: e for e in payload.fields}
    for f in domain.fields:
        e = edits.get(f.id)
        if e is None:
            continue
        if e.data_type is not None:
            f.data_type = e.data_type
        if e.description is not None:
            f.description = e.description
        f.included = e.included
        f.approved = e.approved
    domain.approved = payload.approved

    db.add(AuditEvent(
        event_type="kb.relius.domain_reviewed", actor_type="sme", actor_id="dev@fis.com",
        summary=f"Relius domain '{domain.name}' reviewed",
        detail={"domain_id": domain_id, "approved": payload.approved},
    ))
    await db.commit()
    await db.refresh(domain)
    result = await db.execute(
        select(KBReliusDomain)
        .where(KBReliusDomain.id == domain.id)
        .options(selectinload(KBReliusDomain.fields))
    )
    return _domain_out(result.scalar_one())


@router.post("/relius/save", response_model=KnowledgeBaseSummary)
async def save_relius(db: AsyncSession = Depends(get_db)):
    """Mark the Relius KB as built and record headline stats from the catalogue."""
    kb = await get_or_create_kb(db, "relius")
    domains = await _load_relius_domains(db, kb.id)
    if not domains:
        await _seed_relius(db, kb)  # nothing analysed yet — seed so the KB isn't empty
        domains = await _load_relius_domains(db, kb.id)
    kb.status = "built"
    kb.stats = {
        "tables": sum(d.table_count or 0 for d in domains),
        "domains": len(domains),
        "fields": sum(len(d.fields) for d in domains),
    }
    kb.built_at = datetime.utcnow()
    db.add(AuditEvent(
        event_type="kb.relius.saved", actor_type="sme", actor_id="dev@fis.com",
        summary="Relius Knowledge Base saved", detail=kb.stats,
    ))
    await db.commit()
    await db.refresh(kb)
    return _summary(kb, "relius")


# ── Frp KB ───────────────────────────────────────────────────
async def _load_frp_records(db: AsyncSession, kb_id: str) -> list[KBFrpRecord]:
    result = await db.execute(
        select(KBFrpRecord)
        .where(KBFrpRecord.kb_id == kb_id)
        .options(selectinload(KBFrpRecord.fields))
        .order_by(KBFrpRecord.sort_order)
    )
    return list(result.scalars().all())


async def _load_txn_cards(db: AsyncSession, kb_id: str) -> list[KBTransactionCard]:
    result = await db.execute(
        select(KBTransactionCard)
        .where(KBTransactionCard.kb_id == kb_id)
        .options(selectinload(KBTransactionCard.fields))
        .order_by(KBTransactionCard.sort_order)
    )
    return list(result.scalars().all())


_CONF_CODE_RE = re.compile(r"^[A-Z]{2}\d{3}[A-Z0-9]{0,2}$")
_VOWELS = set("AEIOUaeiou")
CONF_HIGH = 80  # at/above this a field is considered cleanly extracted
CONF_LOW = 55   # below this the extraction is doubtful (likely OCR/parse damage)


def _field_confidence(
    code: str, name: str, description: str | None, legal_values: list | None
) -> tuple[int, list[str]]:
    """Heuristic 0–100 confidence for an extracted Frp data element.

    Purely derived from the parsed content so it works for freshly analysed
    uploads and already-saved catalogues alike. OCR/parse damage shows up as a
    malformed code (e.g. 'AADOS' instead of 'AA005'), a vowel-less/garbled name,
    or a missing description — each docks the score and adds a human-readable
    flag the UI surfaces.
    """
    score = 100
    flags: list[str] = []
    code = (code or "").strip()
    name = (name or "").strip()
    desc = (description or "").strip()

    # 1. Field-code shape — the strongest extraction-quality signal.
    if not _CONF_CODE_RE.match(code):
        score -= 35
        flags.append("code format unexpected")

    # 2. Name present & plausible.
    if len(name) < 2:
        score -= 30
        flags.append("name missing")
    else:
        if name.isupper() and not any(c in _VOWELS for c in name) and len(name) > 3:
            score -= 18
            flags.append("name may be garbled")
        stray = sum(1 for c in name if not (c.isalnum() or c.isspace() or c in "-/&().,'"))
        if stray > max(1, len(name) // 6):
            score -= 12
            flags.append("name has stray characters")

    # 3. Description quality.
    if not desc:
        score -= 22
        flags.append("no description")
    elif len(desc) < 15:
        score -= 10
        flags.append("description sparse")

    # 4. Legal values implied but not captured.
    hay = f"{name} {desc}".lower()
    if not legal_values and any(w in hay for w in ("legal value", "valid", "invalid", "flag", "indicator", "y/n")):
        score -= 8
        flags.append("legal values may be missing")

    return max(0, min(100, score)), flags


def _field_out(f: KBFrpField) -> KBFrpFieldOut:
    conf, flags = _field_confidence(f.code, f.name, f.description, f.legal_values)
    return KBFrpFieldOut(
        id=f.id, code=f.code, name=f.name, description=f.description,
        is_key=f.is_key, legal_values=f.legal_values, included=f.included,
        approved=f.approved, confidence=conf, confidence_flags=flags,
    )


def _record_out(r: KBFrpRecord) -> KBFrpRecordOut:
    fields = sorted(r.fields, key=lambda f: f.sort_order)
    outs = [_field_out(f) for f in fields]
    # "Needs review" = anything the extractor wasn't fully confident about
    # (below High), so the SME's focus list isn't empty on realistic data.
    low = sum(1 for o in outs if o.confidence < CONF_HIGH)
    avg = round(sum(o.confidence for o in outs) / len(outs)) if outs else 100
    return KBFrpRecordOut(
        id=r.id, record_id=r.record_id, prefix=r.prefix, name=r.name, icon=r.icon,
        category=r.category, category_color=r.category_color, description=r.description,
        approved=r.approved, fields=outs, low_conf_count=low, avg_confidence=avg,
    )


def _card_out(c: KBTransactionCard) -> KBTxnCardOut:
    fields = sorted(c.fields, key=lambda f: f.sort_order)
    return KBTxnCardOut(
        id=c.id, code=c.code, name=c.name, category=c.category, icon=c.icon,
        has_layout=c.has_layout, record_length=c.record_length or 110, note=c.note,
        approved=c.approved, selected=c.selected,
        fields=[KBTxnFieldOut.model_validate(f) for f in fields],
    )


async def _seed_frp_records(db: AsyncSession, kb: KnowledgeBase) -> None:
    if await _load_frp_records(db, kb.id):
        return
    for ri, rec in enumerate(FRP_RECORDS):
        record = KBFrpRecord(
            kb_id=kb.id, record_id=rec["record_id"], prefix=rec["prefix"], name=rec["name"],
            icon=rec["icon"], category=rec["category"], category_color=rec["category_color"],
            description=rec["description"], sort_order=ri,
        )
        db.add(record)
        await db.flush()
        for fi, f in enumerate(rec["fields"]):
            db.add(KBFrpField(
                record_id=record.id, code=f["code"], name=f["name"], description=f["description"],
                is_key=f["is_key"], legal_values=f.get("legal_values"), included=True,
                approved=False, sort_order=fi,
            ))


# ── Transaction-card layout parser ─────────────────────────────
# Frp transaction / report cards arrive as "Data Element Details" pages
# (usually image-only PDFs that we OCR). Each file is one T-code card:
#   Alternate Address Report(T960)                     <- title, clean T-code
#   Alternate Address Report (T960) Data Element Details
#   Data Element Names   Pictures   Field Type   Other <- column header
#   (T960) 055 Address Prefix  x02                      <- element: seq, name, picture
#     Label AddrPre RDBType: TX                         <- short label + data type
#   (T960) 070 Output Opt x01 Legal Values
#     Label OutputOpt RDBType: CD  0 - ... / 1 - ...    <- legal values (inline or following)
# The parser anchors on the title, on element rows (junk-paren + 3-digit seq)
# and on the very consistent "Label … RDBType" lines — tolerant of OCR noise.
_TXN_TITLE_RE = re.compile(r"^(.*?)\(\s*T\s*(\d{3,4})\s*\)", re.I)
_TXN_LABEL_RE = re.compile(
    r"^\s*Label[:;.\s]+([A-Za-z0-9_]+)\s+R[DO]B\s*Typ[ea][:;.\s]*([A-Za-z]{2})\b(.*)$", re.I)
_TXN_ELEM_RE  = re.compile(
    r"^[^0-9A-Za-z]*[\(\[]?[T\dOSIl#][\dOSTIlt#]{0,6}[\)\]]?\s*[\)\]]?\s*(\d{3})\b\s+(.+)$")
_TXN_LEGAL_RE = re.compile(r"^\s*([A-Za-z0-9]{1,14})\s*[-–]\s*(.+)$")
_TXN_INLINE_LEGAL_RE = re.compile(r"([A-Za-z0-9]{1,14})\s*[-–]\s*([A-Za-z0-9][^-\n]{1,40})")

_TXN_JUNK = "‘’'\".,:;=~-—•©*"
_TXN_STOP_WORDS = {"legal", "values", "value", "composite", "part", "of", "following", "de's", "des"}

# Ordered most-specific first. Matched on WORD BOUNDARIES so e.g. "reFUND"
# doesn't hit "fund" and "payROLL" doesn't hit "roll".
_TXN_DOMAIN_KEYWORDS = [
    ("financial",   ("check", "disbursement", "payment", "contribution", "payroll", "deposit",
                     "cash", "deduction", "fee", "refund", "amount", "money")),
    ("participant", ("participant", "demographic", "address", "beneficiary",
                     "person", "individual", "associated")),
    ("loans",       ("loan",)),
    ("plans",       ("plan", "division", "div", "sub", "activity", "roll", "base")),
    ("invest",      ("investment", "fund", "rebalance", "allocation", "equity", "share")),
    ("annuity",     ("annuity", "forecast", "actuarial", "valuation")),
    ("system",      ("system", "environment", "backup", "extract", "utility")),
]
_TXN_DOMAIN_ICON = {
    "participant": "\U0001F464", "loans": "\U0001F4B0", "plans": "\U0001F4CB",
    "invest": "\U0001F4C8", "financial": "\U0001F4B3", "annuity": "\U0001F4CA",
    "system": "⚙️", "general": "\U0001F9FE",
}


def _txn_domain(name: str) -> str:
    low = (name or "").lower()
    for domain, kws in _TXN_DOMAIN_KEYWORDS:
        if any(re.search(rf"\b{re.escape(k)}\b", low) for k in kws):
            return domain
    return "general"


def _clean_txn_name(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "").strip())
    return s.strip(" .:-|–")


def _txn_is_picture(tok: str) -> bool:
    t = tok.strip(_TXN_JUNK)
    if re.fullmatch(r"[Nn][A-Za-z0-9]{1,4}[Dd][A-Za-z0-9]{1,3}", t):   # N<int>D<dec>, OCR-lenient
        return True
    if re.fullmatch(r"[xX][A-Za-z0-9]{1,4}", t) and any(c.isdigit() for c in t):  # X(len)
        return True
    return False


def _txn_parse_elem(rest: str) -> tuple[str, str]:
    """From an element row's text, split off (element name, picture)."""
    name_toks: list[str] = []
    picture = ""
    for t in rest.split():
        if _txn_is_picture(t):
            picture = t.strip(_TXN_JUNK)
            break
        if t.strip(_TXN_JUNK).lower() in _TXN_STOP_WORDS:
            break
        name_toks.append(t)
    # drop trailing OCR noise: stray digits, symbol-only tokens, 1–2 char picture fragments
    while name_toks:
        last = name_toks[-1].strip(_TXN_JUNK)
        if (not last or last.isdigit() or len(last) <= 1
                or not any(c.isalnum() for c in last)
                or re.fullmatch(r"[xXnN][A-Za-z0-9]?", last)):
            name_toks.pop()
        else:
            break
    name = re.sub(r"^[^A-Za-z0-9]+", "", " ".join(name_toks))
    return _clean_txn_name(name), picture


def _norm_picture(pic: str) -> str:
    """Best-effort tidy of an OCR'd PICTURE token, e.g. 'x02' → 'X(2)'."""
    if not pic:
        return ""
    m = re.fullmatch(r"[xX]0*(\d+)", pic)
    if m:
        return f"X({int(m.group(1))})"
    return pic.upper()


def _parse_txn_layout(text: str) -> list[dict]:
    """Parse an Frp transaction-card 'Data Element Details' page (best-effort)."""
    lines = [l.rstrip() for l in text.splitlines()]
    card_name, code = "", ""
    for l in lines[:4]:
        m = _TXN_TITLE_RE.match(l.strip())
        if m and m.group(1).strip():
            card_name, code = _clean_txn_name(m.group(1)), "T" + m.group(2)
            break
    if not code:
        return []

    fields: list[dict] = []
    cur: dict | None = None

    def _new() -> dict:
        return {"seq": "", "name": "", "picture": "", "code": "", "rdbtype": "",
                "legal": [], "_lab": False}

    def _flush() -> None:
        nonlocal cur
        if cur and (cur["name"] or cur["code"]):
            legal = "; ".join(f"{v} = {l}" for v, l in cur["legal"][:20])
            fields.append({
                "sub_card": "01", "code": cur["code"] or _clean_txn_name(cur["name"])[:24] or "—",
                "name": cur["name"] or cur["code"], "col_range": cur["seq"],
                "picture": _norm_picture(cur["picture"]), "req_opt": "",
                "src_guess": None, "confidence": None,
                "field_type": cur["rdbtype"] or None, "note": legal or None,
            })
        cur = None

    for l in lines[1:]:
        s = l.strip()
        if not s or "data element" in s.lower():
            continue
        lm = _TXN_LABEL_RE.match(s)
        if lm:
            if cur is not None and cur["_lab"]:  # a preceding element row was missed/garbled
                _flush()
            if cur is None:
                cur = _new()
            cur["code"], cur["rdbtype"], cur["_lab"] = lm.group(1), lm.group(2).upper(), True
            for lv in _TXN_INLINE_LEGAL_RE.finditer(lm.group(3)):
                cur["legal"].append((lv.group(1), lv.group(2).strip()))
            continue
        em = _TXN_ELEM_RE.match(s)
        if em:
            _flush()
            cur = _new()
            cur["seq"] = em.group(1)
            cur["name"], cur["picture"] = _txn_parse_elem(em.group(2))
            continue
        lg = _TXN_LEGAL_RE.match(s)
        if lg and cur is not None and lg.group(1).strip(_TXN_JUNK):
            cur["legal"].append((lg.group(1), _clean_txn_name(lg.group(2))))
            continue
    _flush()

    domain = _txn_domain(card_name or code)
    return [{
        "code": code, "name": card_name or code, "category": domain,
        "icon": _TXN_DOMAIN_ICON.get(domain, _TXN_DOMAIN_ICON["general"]),
        "has_layout": bool(fields), "record_length": len(fields),
        "note": f"{len(fields)} data element(s)", "fields": fields,
    }]


async def _populate_txn_from_parse(db: AsyncSession, kb: KnowledgeBase, cards: list[dict]) -> None:
    """Replace the transaction-card catalogue with parsed layout data."""
    for old in await _load_txn_cards(db, kb.id):
        await db.delete(old)
    await db.flush()
    for ci, card in enumerate(cards):
        c = KBTransactionCard(
            kb_id=kb.id, code=card["code"], name=card["name"], category=card["category"],
            icon=card["icon"], has_layout=card["has_layout"], record_length=card["record_length"],
            note=card["note"], selected=True, sort_order=ci,
        )
        db.add(c)
        await db.flush()
        for fi, f in enumerate(card["fields"]):
            db.add(KBTransactionCardField(
                card_id=c.id, sub_card=f["sub_card"], code=f["code"], name=f["name"],
                col_range=f["col_range"], picture=f["picture"], req_opt=f["req_opt"],
                src_guess=f["src_guess"], confidence=f["confidence"], field_type=f["field_type"],
                note=f["note"], sort_order=fi,
            ))
    if kb.load_order is None:
        kb.load_order = FRP_LOAD_ORDER
    if kb.constants is None:
        kb.constants = FRP_CONSTANTS


async def _seed_txn_cards(db: AsyncSession, kb: KnowledgeBase) -> None:
    if await _load_txn_cards(db, kb.id):
        return
    for ci, card in enumerate(FRP_TXN_CARDS):
        c = KBTransactionCard(
            kb_id=kb.id, code=card["code"], name=card["name"], category=card["category"],
            icon=card["icon"], has_layout=card["has_layout"], record_length=card["record_length"],
            note=card["note"], selected=True, sort_order=ci,
        )
        db.add(c)
        await db.flush()
        for fi, f in enumerate(card["fields"]):
            db.add(KBTransactionCardField(
                card_id=c.id, sub_card=f["sub_card"], code=f["code"], name=f["name"],
                col_range=f["col_range"], picture=f["picture"], req_opt=f["req_opt"],
                src_guess=f["src_guess"], confidence=f["confidence"], field_type=f["field_type"],
                note=f["note"], sort_order=fi,
            ))
    if kb.load_order is None:
        kb.load_order = FRP_LOAD_ORDER
    if kb.constants is None:
        kb.constants = FRP_CONSTANTS


_FRP_FIELD_CODE = re.compile(r"^([A-Z]{2}\d{3}[A-Z0-9]{0,2})\s+(.*)$")


def _split_frp_field(f: dict) -> tuple[str, str, str, list[dict] | None]:
    """
    Split a parsed Frp field into (code, name, description, legal_values).
    The Frp-layout parser stores field as "AA005 Plan ID" and embeds legal
    values in the description as "… Legal values: V Valid; I Invalid".
    """
    raw = (f.get("field") or "").strip()
    desc = f.get("description") or ""
    m = _FRP_FIELD_CODE.match(raw)
    code, name = (m.group(1), m.group(2).strip()) if m else (raw, raw)

    legal: list[dict] | None = None
    if "Legal values:" in desc:
        head, _, lv = desc.partition("Legal values:")
        desc = head.strip()
        parsed = []
        for chunk in lv.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = chunk.split(None, 1)
            parsed.append({"v": parts[0], "l": parts[1] if len(parts) > 1 else ""})
        legal = parsed or None
    return code or raw, name or raw, desc, legal


async def _populate_frp_from_parse(db: AsyncSession, kb: KnowledgeBase, result: dict) -> None:
    """Replace the Frp record catalogue with real parsed schema data.
    Each parsed table becomes an Frp record; its fields become data elements."""
    for old in await _load_frp_records(db, kb.id):
        await db.delete(old)
    await db.flush()

    domain_meta = {d["id"]: d for d in result.get("domains_detail", [])}
    for ri, t in enumerate(result.get("tables_detail", [])):
        did = t.get("domain_id", "unknown")
        rec = KBFrpRecord(
            kb_id=kb.id, record_id=t["name"][:100], prefix=None, name=t["name"],
            icon=domain_meta.get(did, {}).get("icon", "📄"),
            category=domain_meta.get(did, {}).get("name", "Frp"), category_color="t",
            description=t.get("description") or "", sort_order=ri,
        )
        db.add(rec)
        await db.flush()
        for fi, f in enumerate(t.get("fields", [])):
            code, name, desc, legal = _split_frp_field(f)
            db.add(KBFrpField(
                record_id=rec.id, code=code, name=name,
                description=desc, is_key=bool(f.get("is_pk")),
                legal_values=legal, included=True, approved=False, sort_order=fi,
            ))


@router.post("/frp/analyze", response_model=KBFrpCatalog)
async def analyze_frp(
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse the Frp data dictionary into the record catalogue. Accepts one or
    more files — each is parsed by the real extractor and the results are merged
    (tables deduped by name, fields unioned). With no files, falls back to the
    reference seed for demos. (Transaction-card layouts are a separate step.)
    """
    kb = await get_or_create_kb(db, "frp")
    parsed = False
    real = [f for f in (files or []) if f is not None and f.filename]
    if real:
        results, errors = [], []
        for f in real:
            content = await f.read()
            try:
                results.append(_parse_schema_file(f.filename or "upload", content))
            except HTTPException as exc:
                errors.append(f"{f.filename}: {exc.detail}")
        if not results:
            raise HTTPException(422, "; ".join(errors) or "No parseable schema files")
        merged = _merge_parse_results(results)
        await _populate_frp_from_parse(db, kb, merged)
        parsed = True
        note = f" ({len(errors)} file(s) skipped)" if errors else ""
        summary = (f"Frp schema parsed from {len(results)} file(s){note} — "
                   f"{merged['tables']} records · {merged['fields']} data elements")
    else:
        await _seed_frp_records(db, kb)
        summary = "Frp schema seeded from reference catalogue (no file uploaded)"

    db.add(AuditEvent(
        event_type="kb.frp.analyzed", actor_type="system", actor_id="system",
        summary=summary, detail={"parsed_from_upload": parsed},
    ))
    await db.commit()
    records = await _load_frp_records(db, kb.id)
    return KBFrpCatalog(status=kb.status, stats=kb.stats or {}, records=[_record_out(r) for r in records])


@router.get("/frp", response_model=KBFrpCatalog)
async def get_frp(db: AsyncSession = Depends(get_db)):
    """Return the Frp record catalogue."""
    kb = await get_kb(db, "frp")
    if kb is None:
        return KBFrpCatalog(status="draft", stats={}, records=[])
    records = await _load_frp_records(db, kb.id)
    return KBFrpCatalog(status=kb.status, stats=kb.stats or {}, records=[_record_out(r) for r in records])


@router.patch("/frp/records/{record_id}", response_model=KBFrpRecordOut)
async def review_frp_record(
    record_id: str,
    payload: KBFrpRecordReview,
    db: AsyncSession = Depends(get_db),
):
    """Persist SME review for one Frp record."""
    kb = await get_kb(db, "frp")
    if kb is None:
        raise HTTPException(404, "Frp KB not initialised")
    result = await db.execute(
        select(KBFrpRecord)
        .where(KBFrpRecord.kb_id == kb.id, KBFrpRecord.record_id == record_id)
        .options(selectinload(KBFrpRecord.fields))
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(404, f"Record '{record_id}' not found in Frp KB")
    edits = {e.id: e for e in payload.fields}
    for f in record.fields:
        e = edits.get(f.id)
        if e is None:
            continue
        if e.description is not None:
            f.description = e.description
        f.included = e.included
        f.approved = e.approved
    record.approved = payload.approved
    db.add(AuditEvent(
        event_type="kb.frp.record_reviewed", actor_type="sme", actor_id="dev@fis.com",
        summary=f"Frp record '{record.name}' reviewed",
        detail={"record_id": record_id, "approved": payload.approved},
    ))
    await db.commit()
    result = await db.execute(
        select(KBFrpRecord).where(KBFrpRecord.id == record.id).options(selectinload(KBFrpRecord.fields))
    )
    return _record_out(result.scalar_one())


@router.post("/frp/txn/analyze", response_model=KBFrpTxnCatalog)
async def analyze_frp_txn(
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse uploaded transaction-card layout docs into the card catalogue.
    Each file's text is extracted (with OCR for image/scanned docs) and parsed
    for T-code layouts. With no files — or when nothing parseable is found —
    falls back to the reference seed for demos.
    """
    from app.services.schema.extractor import extractor

    kb = await get_or_create_kb(db, "frp")
    real = [f for f in (files or []) if f is not None and f.filename]
    parsed_cards: list[dict] = []
    warnings: list[str] = []
    for f in real:
        content = await f.read()
        text, warn = extractor.extract_text(f.filename or "upload", content)
        if warn:
            warnings.append(f"{f.filename}: {warn}")
        parsed_cards.extend(_parse_txn_layout(text))

    if parsed_cards:
        # Dedupe by T-code, keeping the richest (most fields) instance.
        best: dict[str, dict] = {}
        for c in parsed_cards:
            prev = best.get(c["code"])
            if prev is None or len(c["fields"]) > len(prev["fields"]):
                best[c["code"]] = c
        cards = list(best.values())
        await _populate_txn_from_parse(db, kb, cards)
        note = f" ({len(warnings)} warning(s))" if warnings else ""
        summary = f"Transaction layouts parsed from {len(real)} file(s){note} — {len(cards)} cards"
    else:
        await _seed_txn_cards(db, kb)
        summary = ("Transaction layouts seeded from reference catalogue"
                   + (" (uploads had no recognisable T-code layout)" if real else " (no file uploaded)"))
    db.add(AuditEvent(
        event_type="kb.frp.txn_analyzed", actor_type="system", actor_id="system",
        summary=summary, detail={"parsed_from_upload": bool(parsed_cards), "warnings": warnings},
    ))
    await db.commit()
    await db.refresh(kb)
    cards = await _load_txn_cards(db, kb.id)
    return KBFrpTxnCatalog(
        status=kb.status, cards=[_card_out(c) for c in cards],
        load_order=kb.load_order or [], constants=kb.constants or [],
    )


@router.get("/frp/txn", response_model=KBFrpTxnCatalog)
async def get_frp_txn(db: AsyncSession = Depends(get_db)):
    """Return the Frp transaction cards + load order + constants."""
    kb = await get_kb(db, "frp")
    if kb is None:
        return KBFrpTxnCatalog(status="draft", cards=[], load_order=[], constants=[])
    cards = await _load_txn_cards(db, kb.id)
    return KBFrpTxnCatalog(
        status=kb.status, cards=[_card_out(c) for c in cards],
        load_order=kb.load_order or [], constants=kb.constants or [],
    )


@router.patch("/frp/txn/cards/{code}", response_model=KBTxnCardOut)
async def review_txn_card(
    code: str,
    payload: KBTxnCardReview,
    db: AsyncSession = Depends(get_db),
):
    """Persist SME review for one transaction card layout (field-name edits + approve)."""
    kb = await get_kb(db, "frp")
    if kb is None:
        raise HTTPException(404, "Frp KB not initialised")
    result = await db.execute(
        select(KBTransactionCard)
        .where(KBTransactionCard.kb_id == kb.id, KBTransactionCard.code == code)
        .options(selectinload(KBTransactionCard.fields))
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(404, f"Transaction card '{code}' not found")
    edits = {e.id: e for e in payload.fields}
    for f in card.fields:
        e = edits.get(f.id)
        if e is not None and e.name is not None:
            f.name = e.name
    card.approved = payload.approved
    db.add(AuditEvent(
        event_type="kb.frp.txn_card_reviewed", actor_type="sme", actor_id="dev@fis.com",
        summary=f"Transaction card '{code}' reviewed", detail={"code": code, "approved": payload.approved},
    ))
    await db.commit()
    result = await db.execute(
        select(KBTransactionCard).where(KBTransactionCard.id == card.id).options(selectinload(KBTransactionCard.fields))
    )
    return _card_out(result.scalar_one())


@router.post("/frp/save", response_model=KnowledgeBaseSummary)
async def save_frp(db: AsyncSession = Depends(get_db)):
    """Mark the Frp KB as built and record headline stats from the catalogue."""
    kb = await get_or_create_kb(db, "frp")
    records = await _load_frp_records(db, kb.id)
    if not records:
        await _seed_frp_records(db, kb)
        records = await _load_frp_records(db, kb.id)
    await _seed_txn_cards(db, kb)  # transaction-card layouts remain seeded (separate upload)
    cards = await _load_txn_cards(db, kb.id)
    kb.status = "built"
    kb.stats = {
        "records": len(records),
        "elements": sum(len(r.fields) for r in records),
        "txn_count": len(cards),
        "txn_fields": sum(len(c.fields) for c in cards),
    }
    kb.built_at = datetime.utcnow()
    db.add(AuditEvent(
        event_type="kb.frp.saved", actor_type="sme", actor_id="dev@fis.com",
        summary="Frp Knowledge Base saved", detail=kb.stats,
    ))
    await db.commit()
    await db.refresh(kb)
    return _summary(kb, "frp")
