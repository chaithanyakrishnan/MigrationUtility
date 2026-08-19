"""
app/services/pipeline/txn_export.py
Fixed-width Frp transaction-card export.

Ports the v5 prototype's buildCardLine / generateTxnExportLines to Python. Each
card sub-layout becomes one 110-char fixed-width line; TRAN-CODE occupies cols
1–3 and SEQ-CODE cols 4–5, with every catalogued field placed at its column
range using a representative sample value.
"""
from __future__ import annotations

import re
from datetime import date

RECORD_LENGTH = 110


def _col_bounds(col_range: str) -> tuple[int, int]:
    parts = (col_range or "").split("-")
    try:
        start = int(parts[0])
        end = int(parts[1]) if len(parts) > 1 else start
    except (ValueError, IndexError):
        return (0, 0)
    return (start, end)


def _today() -> str:
    d = date.today()
    return f"{d.year:04d}{d.month:02d}{d.day:02d}"


def _sample_value(field: dict, length: int) -> str:
    """A representative fixed-width value for a card field."""
    name_up = f"{field.get('code', '')} {field.get('name', '')}".upper()
    ftype = field.get("field_type")
    note = field.get("note") or ""
    if "DATE" in name_up:
        return _today().ljust(length)[:length] if length >= 8 else "0" * length
    if ftype == "constant":
        m = re.search(r"'([^']+)'", note)
        return (m.group(1) if m else "").ljust(length)[:length]
    if re.search(r"AMT|AMOUNT|RATE|NUM|SEQ|-ID$", field.get("code", "")):
        return ("0" * length)[:length]
    return " " * length


def build_card_line(code: str, fields: list[dict]) -> str:
    """Build one fixed-width record line for a card sub-layout."""
    buf = [" "] * RECORD_LENGTH

    def place(start: int, end: int, value: str) -> None:
        for i in range(start, min(end, RECORD_LENGTH) + 1):
            idx = i - start
            buf[i - 1] = value[idx] if idx < len(value) else " "

    place(1, 3, code[:3])
    place(4, 5, "01")
    for f in fields:
        start, end = _col_bounds(f.get("col_range", ""))
        if start == 0:
            continue
        length = end - start + 1
        place(start, end, _sample_value(f, length))
    return "".join(buf)


def generate_export(cards: list[dict]) -> tuple[list[str], list[str]]:
    """
    Given the in-scope cards (each: {code, fields:[{sub_card,col_range,...}]}),
    return (lines, manifest). One line per sub-card, ordered by code then sub-card.
    """
    lines: list[str] = []
    manifest: list[str] = []
    for card in sorted(cards, key=lambda c: c["code"]):
        code = card["code"]
        by_sub: dict[str, list[dict]] = {}
        for f in card.get("fields", []):
            by_sub.setdefault(f.get("sub_card", "01"), []).append(f)
        for sub in sorted(by_sub):
            lines.append(build_card_line(code, by_sub[sub]))
            has_layout = card.get("has_layout", False)
            manifest.append(
                f"{code} / card {sub} ({len(by_sub[sub])} fields"
                + ("" if has_layout else ", header shell only") + ")"
            )
    return lines, manifest
