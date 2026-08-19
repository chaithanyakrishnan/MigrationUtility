"""Unit tests for the migration-project mapping catalogue + T-code derivation."""
from app.services.kb.mapping_seed import MAPPING_CATALOGUE, derive_txn_code
from app.services.kb.relius_seed import RELIUS_DOMAINS, relius_stats
from app.services.kb.frp_seed import FRP_RECORDS, FRP_TXN_CARDS, frp_stats


def test_derive_txn_code_loan_wins():
    assert derive_txn_code({"frp": "Loan Header", "dom": "loans"}) == "T022"


def test_derive_txn_code_participant():
    assert derive_txn_code({"frp": "Participant Header", "dom": "part"}) == "T813"


def test_derive_txn_code_history_roll():
    assert derive_txn_code({"frp": "History Base (HIVR)", "dom": "trans"}) == "T035"


def test_derive_txn_code_investment():
    assert derive_txn_code({"frp": "Fund Control", "dom": "invest"}) == "T039"


def test_derive_txn_code_unassigned():
    assert derive_txn_code({"frp": "Salary Record", "dom": "payroll"}) is None


def test_every_catalogue_row_is_well_formed():
    for m in MAPPING_CATALOGUE:
        assert m["src"] and m["field"] and m["frp"] and m["tgt"]
        assert 0 <= m["conf"] <= 100


def test_relius_stats_match_catalogue():
    stats = relius_stats()
    assert stats["domains"] == len(RELIUS_DOMAINS)
    assert stats["fields"] == sum(len(d["fields"]) for d in RELIUS_DOMAINS)


def test_frp_stats_match_catalogue():
    stats = frp_stats()
    assert stats["records"] == len(FRP_RECORDS)
    assert stats["txn_count"] == len(FRP_TXN_CARDS)
    assert stats["txn_fields"] == sum(len(c["fields"]) for c in FRP_TXN_CARDS)
