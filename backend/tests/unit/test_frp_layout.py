"""Unit tests for the Frp record-layout parser + KB field splitting."""
from app.services.schema.extractor import extractor
from app.api.routes.knowledge_base import _split_frp_field, _field_confidence, CONF_LOW

SAMPLE = """ADDRESS RECORD
AA005 Plan ID
Description
This field contains the Plan ID and is part of the record key.
AA220 Address Flag
Description
Indicates whether the Address record is valid or invalid.
Legal Values
V Valid
I Invalid
Associated Individuals Record
AI005 Plan ID
Description
Plan identifier for the associated individual record.
AI030 Gender
Description
The gender of the associated individual.
Legal Values
M Male
F Female
"""


def test_detects_frp_layout():
    assert extractor._looks_like_frp_layout(SAMPLE) is True


def test_groups_fields_into_records_by_prefix():
    r = extractor._parse_frp_layout(SAMPLE)
    names = {t.name for t in r.tables}
    assert names == {"Alternate Address", "Associated Individuals"}
    assert r.field_count == 4


def test_field_codes_preserved():
    r = extractor._parse_frp_layout(SAMPLE)
    codes = [f.field_name.split()[0] for t in r.tables for f in t.fields]
    assert codes == ["AA005", "AA220", "AI005", "AI030"]


def test_record_header_does_not_pollute_legal_values():
    r = extractor._parse_frp_layout(SAMPLE)
    aa220 = next(f for t in r.tables for f in t.fields if f.field_name.startswith("AA220"))
    _, _, _, legal = _split_frp_field({"field": aa220.field_name, "description": aa220.description})
    assert legal == [{"v": "V", "l": "Valid"}, {"v": "I", "l": "Invalid"}]


def test_split_frp_field_extracts_code_name_legal():
    code, name, desc, legal = _split_frp_field({
        "field": "AA225 Address Type",
        "description": "Indicates domestic or foreign.  Legal values: D Domestic; F Foreign",
    })
    assert code == "AA225"
    assert name == "Address Type"
    assert "domestic or foreign" in desc.lower()
    assert legal == [{"v": "D", "l": "Domestic"}, {"v": "F", "l": "Foreign"}]


def test_is_header_rejects_prose():
    assert extractor._is_frp_header("Associated Individuals Record") is True
    assert extractor._is_frp_header("ADDRESS RECORD") is True
    assert extractor._is_frp_header("This field identifies the record.") is False


def test_confidence_high_for_clean_field():
    score, flags = _field_confidence(
        "AA005", "Plan ID",
        "This field contains the Plan ID and is part of the record key.", None,
    )
    assert score == 100
    assert flags == []


def test_confidence_low_for_garbled_ocr_field():
    # OCR damage: code should be AA005, name has no description.
    score, flags = _field_confidence("AADOS", "Plsn ID", "", None)
    assert score < CONF_LOW
    assert "code format unexpected" in flags
    assert "no description" in flags


def test_confidence_docks_missing_description_but_stays_medium():
    score, flags = _field_confidence("AR110", "Rebalance Frequency", "freq", None)
    assert CONF_LOW <= score < 100
    assert "description sparse" in flags
