"""Unit tests for the fixed-width transaction-card export generator."""
from app.services.pipeline.txn_export import (
    build_card_line, generate_export, RECORD_LENGTH,
)


def _t813_card():
    return {
        "code": "T813", "has_layout": True,
        "fields": [
            {"sub_card": "01", "code": "TRAN-CODE", "col_range": "1-3", "field_type": "constant", "note": "Literal 'T813'"},
            {"sub_card": "01", "code": "SEQ-CODE", "col_range": "4-5", "field_type": "derived", "note": ""},
            {"sub_card": "01", "code": "DIV-SUB", "col_range": "13-16", "field_type": "direct", "note": ""},
        ],
    }


def test_build_card_line_is_fixed_width():
    line = build_card_line("T813", _t813_card()["fields"])
    assert len(line) == RECORD_LENGTH


def test_build_card_line_places_tran_code():
    line = build_card_line("T813", _t813_card()["fields"])
    # cols 1-3 carry the T-code prefix
    assert line[0:3] == "T81"


def test_generate_export_returns_line_per_subcard():
    card = {
        "code": "T022", "has_layout": True,
        "fields": [
            {"sub_card": "01", "code": "TRAN-CODE", "col_range": "1-3", "field_type": "constant", "note": "Literal 'T022'"},
            {"sub_card": "0X", "code": "MSG", "col_range": "9-15", "field_type": "constant", "note": "Msg = TOISSU1"},
        ],
    }
    lines, manifest = generate_export([card])
    assert len(lines) == 2           # one per distinct sub-card
    assert len(manifest) == 2
    assert all(len(l) == RECORD_LENGTH for l in lines)
    assert "T022 / card 01" in manifest[0]


def test_generate_export_sorted_by_code():
    a = {"code": "T039", "has_layout": True, "fields": [{"sub_card": "01", "code": "TRAN-CODE", "col_range": "1-3", "field_type": "constant", "note": "'T039'"}]}
    b = {"code": "T022", "has_layout": True, "fields": [{"sub_card": "01", "code": "TRAN-CODE", "col_range": "1-3", "field_type": "constant", "note": "'T022'"}]}
    _, manifest = generate_export([a, b])
    assert manifest[0].startswith("T022")
    assert manifest[1].startswith("T039")


def test_header_shell_flagged_in_manifest():
    card = {"code": "T104", "has_layout": False,
            "fields": [{"sub_card": "00", "code": "TRAN-CODE", "col_range": "1-3", "field_type": "constant", "note": "'T104'"}]}
    _, manifest = generate_export([card])
    assert "header shell only" in manifest[0]
