"""Unit tests for the Frp transaction-card 'Data Element Details' parser."""
from app.api.routes.knowledge_base import _parse_txn_layout, _txn_domain, _norm_picture

# Mirrors the OCR'd shape of the real sample PDFs (noise intentionally included).
SAMPLE = """Alternate Address Report(T960)
Alternate Address Report (7960) Data Element Details
Data Element Names Pictures! Field Type Other
(T3960)055 Address Prefix x02
Label AddrPre ROBType: TX
(T9360) 065 Usage Filter x20
Label UsageFilt ROBType: TX
(T9360) 070 Output Opt x01 Legal Values
Label OutputOpt ROBType: CD 0 - Only This
1 - All
"""


def test_card_identity_from_title():
    (card,) = _parse_txn_layout(SAMPLE)
    assert card["code"] == "T960"
    assert card["name"] == "Alternate Address Report"
    assert card["category"] == "participant"     # "address"
    assert card["has_layout"] is True


def test_elements_seq_name_label_type():
    (card,) = _parse_txn_layout(SAMPLE)
    assert len(card["fields"]) == 3
    f0 = card["fields"][0]
    assert f0["col_range"] == "055"          # sequence
    assert f0["name"] == "Address Prefix"
    assert f0["code"] == "AddrPre"           # short label
    assert f0["field_type"] == "TX"          # RDBType
    assert f0["picture"] == "X(2)"           # normalised from 'x02'


def test_legal_values_captured():
    (card,) = _parse_txn_layout(SAMPLE)
    output = next(f for f in card["fields"] if f["code"] == "OutputOpt")
    assert output["field_type"] == "CD"
    assert "Only This" in (output["note"] or "")
    assert "All" in (output["note"] or "")


def test_missing_title_returns_nothing():
    assert _parse_txn_layout("just some text with no T-code header") == []


def test_norm_picture():
    assert _norm_picture("x02") == "X(2)"
    assert _norm_picture("X15") == "X(15)"
    assert _norm_picture("NOSDO0") == "NOSDO0"   # numeric picts left as-is


def test_domain_classifier():
    assert _txn_domain("Cash Transactions") == "financial"
    assert _txn_domain("Div-Sub Maintenance") == "plans"
    assert _txn_domain("Actuarial Valuation Extract") == "annuity"
    assert _txn_domain("Associated Individual Maint") == "participant"
