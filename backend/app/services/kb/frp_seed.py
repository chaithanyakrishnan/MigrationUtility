"""
app/services/kb/frp_seed.py
Reference catalogue for the Frp Knowledge Base.

Ported from the v5 prototype: Frp record definitions (FRP_RECORDS), confirmed
transaction-card fixed-width layouts (TXN_CARD_FIELDS), the Frp load order and
the constants registry. Seeds the KB so the flow is always populated; uploaded
data-dictionary / transaction-layout docs augment this later.
"""
from __future__ import annotations

# ── Frp records (record groups + data elements) ──────────────
FRP_RECORDS: list[dict] = [
    {
        "record_id": "addr", "prefix": "AA", "name": "Alternate Address Record", "icon": "📬",
        "category": "Participant", "category_color": "t",
        "description": "Stores alternate mailing addresses for participants, beneficiaries, and non-participant entities.",
        "fields": [
            {"code": "AA005", "name": "Plan ID", "is_key": True, "description": "Plan ID and part of the record key. Alphanumeric, cannot be file maintained."},
            {"code": "AA007", "name": "Address Prefix", "is_key": True, "description": "User-defined alphanumeric. Part of record key. Blank Address ID = non-participant address."},
            {"code": "AA008", "name": "Address ID", "is_key": True, "description": "Alphanumeric. Part of record key. Blank prefix + valued ID = participant address using PH008."},
            {"code": "AA010", "name": "Sequence Number", "is_key": True, "description": "Sequence number per address record per Plan/Address ID/Address Prefix."},
            {"code": "AA220", "name": "Address Flag", "is_key": False, "description": "Indicates whether Address record is valid or invalid.",
             "legal_values": [{"v": "V", "l": "Valid"}, {"v": "I", "l": "Invalid"}]},
            {"code": "AA225", "name": "Address Type", "is_key": False, "description": "Indicates domestic or foreign. Written to RS06 interface.",
             "legal_values": [{"v": "D", "l": "Domestic"}, {"v": "F", "l": "Foreign"}]},
            {"code": "AA300", "name": "Address Line 1", "is_key": False, "description": "First line of street address."},
            {"code": "AA320", "name": "City", "is_key": False, "description": "City portion of the address."},
            {"code": "AA325", "name": "State", "is_key": False, "description": "State abbreviation in first two positions."},
            {"code": "AA330", "name": "Zip", "is_key": False, "description": "Zip code portion of the address."},
        ],
    },
    {
        "record_id": "se", "prefix": "SE", "name": "System Environment Record", "icon": "⚙️",
        "category": "System", "category_color": "gr",
        "description": "System environment configuration record within the Frp DC file set.",
        "fields": [
            {"code": "SE010", "name": "Record Type", "is_key": True, "description": 'Type of record being built. Valid value is "SENV".'},
            {"code": "SE020", "name": "File Set", "is_key": False, "description": "The file set for which the Environment Record will affect."},
            {"code": "SE030", "name": "File Name", "is_key": False, "description": "Name of the file within the file set."},
        ],
    },
    {
        "record_id": "ck_cd", "prefix": "CK/CD", "name": "Check Header / Check Detail Record", "icon": "💳",
        "category": "Financial", "category_color": "g",
        "description": "Check Header (CK) records deposit-level info for reserve account checks. Check Detail (CD) tracks line items.",
        "fields": [
            {"code": "CD006", "name": "Plan Number", "is_key": True, "description": "Plan Number — key identifier for each plan and Check Detail record."},
            {"code": "CD010", "name": "Check Number", "is_key": True, "description": "Check number associated with the Check Detail record."},
            {"code": "CD200", "name": "Amount", "is_key": False, "description": "Amount deposited in the Reserve Account Plan account for a particular plan."},
            {"code": "CD220", "name": "Reversed Flag", "is_key": False, "description": "Indicates whether transactions for a specific deposit have been reversed.",
             "legal_values": [{"v": "Y", "l": "Reversed"}, {"v": "N", "l": "Not reversed"}]},
            {"code": "CK010", "name": "Check Number", "is_key": True, "description": "Check number associated with the Check Header record."},
            {"code": "CK220", "name": "Status Flag", "is_key": False, "description": "Status of the deposit.",
             "legal_values": [{"v": "Blank", "l": "Deposit is good"}, {"v": "B", "l": "Bounced"}, {"v": "V", "l": "Void"}]},
            {"code": "CK280", "name": "Type Flag", "is_key": False, "description": "Type of funds deposited.",
             "legal_values": [{"v": "C", "l": "Cash"}, {"v": "Q", "l": "Check"}, {"v": "D", "l": "EFT/DDI"}, {"v": "R", "l": "Redeposit"}, {"v": "U", "l": "Unknown"}]},
        ],
    },
    {
        "record_id": "am", "prefix": "AM", "name": "Annuity Master Record", "icon": "📊",
        "category": "Annuity", "category_color": "a",
        "description": "Master record for annuities — one per annuity created for a participant. Created by Annuity Add (T530).",
        "fields": [
            {"code": "AM050", "name": "Annuity Plan", "is_key": True, "description": "Annuity Plan Number that associates annuities by processing parameters."},
            {"code": "AM052", "name": "Annuitant ID", "is_key": True, "description": "Annuitant social security number."},
            {"code": "AM105", "name": "Annuity Option", "is_key": False, "description": "Annuity Option selected during creation.",
             "legal_values": [{"v": "SL", "l": "Single life"}, {"v": "JL", "l": "Joint life"}, {"v": "FP", "l": "Fixed period"}]},
            {"code": "AM110", "name": "Annuity Type", "is_key": False, "description": "Fixed or variable annuity.",
             "legal_values": [{"v": "F", "l": "Fixed"}, {"v": "V", "l": "Variable"}]},
            {"code": "AM120", "name": "Effective Date", "is_key": False, "description": "Effective date entered when annuity was created."},
            {"code": "AM600", "name": "Federal Withholding Use", "is_key": False, "description": "Controls whether federal tax withholding applies."},
        ],
    },
    {
        "record_id": "anap", "prefix": "AP", "name": "Annuity Pointer (ANAP) Record", "icon": "🔗",
        "category": "Annuity", "category_color": "a",
        "description": "Annuity Pointer record linking annuity processing structures.",
        "fields": [
            {"code": "AP000", "name": "Fileset Indicator", "is_key": True, "description": "X01 — RDB: OAP_FILESET_CD. Key Field RDBNUM 001."},
            {"code": "AP005", "name": "Plan Number", "is_key": True, "description": "X06 — Key Field RDBNUM 002."},
            {"code": "AP010", "name": "View Indicator", "is_key": True, "description": "X01 — RDB: OAP_VIEW_IND. Key Field RDBNUM 004."},
            {"code": "AP020", "name": "View Key", "is_key": True, "description": "X35 — Key Field RDBNUM 005."},
            {"code": "AP027", "name": "Rec Type", "is_key": True, "description": "X02 — Constant Value. Key Field RDBNUM 006."},
        ],
    },
    {
        "record_id": "fr", "prefix": "FR", "name": "Forecasting Annuity Header Record", "icon": "📈",
        "category": "Annuity", "category_color": "a",
        "description": "Header record for annuity forecasting. Created by Forecast Projection (T563) or Contribution Estimate (T564).",
        "fields": [
            {"code": "FR006", "name": "Plan Number", "is_key": True, "description": "Plan ID Number under which the transaction was processed."},
            {"code": "FR008", "name": "Participant Number", "is_key": True, "description": "Participant nine-character participant number."},
            {"code": "FR050", "name": "Forecast Date", "is_key": True, "description": "Date the T563 or T564 transaction was added or last changed."},
            {"code": "FR105", "name": "Reporting Option", "is_key": False, "description": "Type of report to be generated.",
             "legal_values": [{"v": "P", "l": "Projection"}, {"v": "A", "l": "Application for Benefits"}, {"v": "B", "l": "Benefit Statement"}]},
            {"code": "FR110", "name": "Estimate Type", "is_key": False, "description": "Type of forecast.",
             "legal_values": [{"v": "C", "l": "Contribution estimate"}, {"v": "P", "l": "Projection estimate"}]},
        ],
    },
    {
        "record_id": "bh_bf", "prefix": "BH/BF", "name": "Backup Header / Footer Record", "icon": "💾",
        "category": "System", "category_color": "gr",
        "description": "Each Frp DC backup file contains one header and one footer record. Accessed via BABKUT.",
        "fields": [
            {"code": "BH006", "name": "Backup Header Date", "is_key": True, "description": "Date of the backup file header."},
            {"code": "BH008", "name": "Backup Header System Release", "is_key": False, "description": "System release version recorded in backup header."},
            {"code": "BF006", "name": "Backup Trailer Date", "is_key": True, "description": "Date of the backup file trailer/footer record."},
            {"code": "BF009", "name": "Backup Trailer Records", "is_key": False, "description": "Total number of records in the backup file."},
        ],
    },
]

# ── Transaction cards with confirmed fixed-width layouts ───────
# Each field: sub_card, code, name, col_range, picture, req_opt, src_guess, confidence, field_type, note
FRP_TXN_CARDS: list[dict] = [
    {
        "code": "T813", "name": "Participant Header Maintenance", "category": "participant", "icon": "👤",
        "has_layout": True, "record_length": 110, "note": "Cards 00 (overview) · 01 · 02–99",
        "fields": [
            {"sub_card": "01", "code": "TRAN-CODE", "name": "Tran-Code", "col_range": "1-3", "picture": "X(3)", "req_opt": "Req", "src_guess": "CONST", "confidence": 100, "field_type": "constant", "note": "Literal 'T813'"},
            {"sub_card": "01", "code": "SEQ-CODE", "name": "Seq-Code", "col_range": "4-5", "picture": "X(2)", "req_opt": "Req", "src_guess": "DERIVED", "confidence": 60, "field_type": "derived", "note": "System sequence"},
            {"sub_card": "01", "code": "DIV-SUB", "name": "Div-Sub (Div/Sub)", "col_range": "13-16", "picture": "X(4)", "req_opt": "Opt", "src_guess": "PLANLOCDIVISION.DIVID", "confidence": 88, "field_type": "direct", "note": ""},
            {"sub_card": "01", "code": "VALIDATE-OVERRIDE", "name": "Validate Override", "col_range": "17", "picture": "X", "req_opt": "Opt", "src_guess": "CONST", "confidence": 92, "field_type": "constant", "note": ""},
            {"sub_card": "01", "code": "DENUM", "name": "Denum (Data Elements: DE#)", "col_range": "28-30", "picture": "X(3)", "req_opt": "Opt", "src_guess": "PLANLOANLOAN.DENOM_CD", "confidence": 79, "field_type": "crosswalk", "note": ""},
            {"sub_card": "01", "code": "VAL-INTERNAL", "name": "Val-Internal (Value)", "col_range": "31-110", "picture": "X(80)", "req_opt": "Opt", "src_guess": "PLANLOANLOAN.DENOM_VAL", "confidence": 68, "field_type": "transform", "note": "80-char internal value payload"},
        ],
    },
    {
        "code": "T022", "name": "Loan Utility", "category": "loans", "icon": "🏦",
        "has_layout": True, "record_length": 110, "note": "Card 01 · Card 0X (TOISSU1)",
        "fields": [
            {"sub_card": "01", "code": "TRAN-CODE", "name": "Tran-Code", "col_range": "1-3", "picture": "X(3)", "req_opt": "Req", "src_guess": "CONST", "confidence": 100, "field_type": "constant", "note": "Literal 'T022'"},
            {"sub_card": "01", "code": "SEQ-CODE", "name": "Seq-Code", "col_range": "4-5", "picture": "X(2)", "req_opt": "Req", "src_guess": "DERIVED", "confidence": 60, "field_type": "derived", "note": "System sequence"},
            {"sub_card": "01", "code": "LOAN-NUM", "name": "Loan-Num", "col_range": "29-31", "picture": "X(3)", "req_opt": "Req", "src_guess": "EELOAN.LOANNUM", "confidence": 98, "field_type": "direct", "note": "Required"},
            {"sub_card": "0X", "code": "MSG", "name": "Msg = TOISSU1", "col_range": "9-15", "picture": "X(7)", "req_opt": "Opt", "src_guess": "CONST", "confidence": 100, "field_type": "constant", "note": "Literal sub-card identifier"},
            {"sub_card": "0X", "code": "TAKEOVER-AMOUNT", "name": "Takeover-Amount", "col_range": "32-42", "picture": "9(9)V99", "req_opt": "Req", "src_guess": "EELOAN.CURRBALAMT", "confidence": 85, "field_type": "direct", "note": "Required"},
            {"sub_card": "0X", "code": "PMT-AMT", "name": "Pmt-Amt (Payment Amount)", "col_range": "43-53", "picture": "9(9)V99", "req_opt": "Req", "src_guess": "EELOAN.PMTAMT", "confidence": 93, "field_type": "direct", "note": "Required"},
            {"sub_card": "0X", "code": "INT-RATE", "name": "Int-Rate (Interest Rate)", "col_range": "54-60", "picture": "9V9(6)", "req_opt": "Req", "src_guess": "EELOAN.INTRSTRATEPCT", "confidence": 95, "field_type": "direct", "note": "Required"},
        ],
    },
    {
        "code": "T035", "name": "Activity Roll", "category": "plans", "icon": "📋",
        "has_layout": True, "record_length": 110, "note": "Card 01 — loan interest reset flags",
        "fields": [
            {"sub_card": "01", "code": "TRAN-CODE", "name": "Tran-Code", "col_range": "1-3", "picture": "X(3)", "req_opt": "Req", "src_guess": "CONST", "confidence": 100, "field_type": "constant", "note": "Literal 'T035'"},
            {"sub_card": "01", "code": "SEQ-CODE", "name": "Seq-Code", "col_range": "4-5", "picture": "X(2)", "req_opt": "Req", "src_guess": "DERIVED", "confidence": 60, "field_type": "derived", "note": "System sequence"},
            {"sub_card": "01", "code": "ROLL-LOAN-CYINT", "name": "Roll-Loan-Cyint", "col_range": "14", "picture": "X", "req_opt": "Opt", "src_guess": "CONST", "confidence": 92, "field_type": "constant", "note": "Reset Calendar Year Loan Interest to Zero"},
            {"sub_card": "01", "code": "ACCUM-INT-DEEMED", "name": "Accum-Int-Deemed", "col_range": "22", "picture": "X", "req_opt": "Opt", "src_guess": "CONST", "confidence": 90, "field_type": "constant", "note": "Accumulate Interest for Deemed Distributed Loans"},
        ],
    },
    {
        "code": "T039", "name": "Investment Action Utility", "category": "invest", "icon": "📉",
        "has_layout": True, "record_length": 110, "note": "Cards 01 · 02 · 03",
        "fields": [
            {"sub_card": "01", "code": "TRAN-CODE", "name": "Tran-Code", "col_range": "1-3", "picture": "X(3)", "req_opt": "Req", "src_guess": "CONST", "confidence": 100, "field_type": "constant", "note": "Literal 'T039'"},
            {"sub_card": "01", "code": "SEQ-CODE", "name": "Seq-Code", "col_range": "4-5", "picture": "X(2)", "req_opt": "Req", "src_guess": "DERIVED", "confidence": 60, "field_type": "derived", "note": "System sequence"},
            {"sub_card": "01", "code": "PRICEID", "name": "PriceID", "col_range": "9-23", "picture": "X(15)", "req_opt": "Req", "src_guess": "FUND.FUNDID", "confidence": 97, "field_type": "direct", "note": "Required"},
            {"sub_card": "01", "code": "RECORD-DATE", "name": "Record Date", "col_range": "24-31", "picture": "9(8)", "req_opt": "Req", "src_guess": "FUNDHIST.FUNDVALDATE", "confidence": 95, "field_type": "direct", "note": "Required"},
            {"sub_card": "02", "code": "TRAN-CODE", "name": "Tran-Code", "col_range": "1-3", "picture": "X(3)", "req_opt": "Req", "src_guess": "CONST", "confidence": 100, "field_type": "constant", "note": "Literal 'T039'"},
            {"sub_card": "02", "code": "DISTRIBUTED-DOLLARS", "name": "Distributed Dollars", "col_range": "34-48", "picture": "S9(13)V9(2)", "req_opt": "Opt", "src_guess": "FUNDHIST.DISTDOLLARS", "confidence": 80, "field_type": "direct", "note": ""},
        ],
    },
]

# ── Frp load order (record-level; business-critical) ──────────
FRP_LOAD_ORDER: list[dict] = [
    {"seq": 1, "record": "Plan Record (PL)", "type": "Plan", "reason": "Root — all records reference Plan ID"},
    {"seq": 2, "record": "Division/Subsidiary (DS)", "type": "Plan", "reason": "Plan-level org structure"},
    {"seq": 3, "record": "Fund Control / Price ID", "type": "Invest", "reason": "Investment defs before participant funds"},
    {"seq": 4, "record": "Share Account / Source", "type": "Plan", "reason": "Source defs before participant sources"},
    {"seq": 5, "record": "Person — Participant Header", "type": "Person", "reason": "Person must exist before participant"},
    {"seq": 6, "record": "Part. Fund / Source / AI", "type": "Part", "reason": "Participant FK must exist first"},
    {"seq": 7, "record": "Cash Control Account", "type": "Cash", "reason": "Cash before transaction history"},
    {"seq": 8, "record": "History Base / HIVR (BR)", "type": "Trans", "reason": "Atomic: participant + plan summary"},
    {"seq": 9, "record": "Disbursement / Rollover", "type": "Trans", "reason": "References HIVR share sales"},
    {"seq": 10, "record": "Loan Header — Fund — Pmts", "type": "Loan", "reason": "Header before fund before payments"},
    {"seq": 11, "record": "Compensation / Salary", "type": "Comp", "reason": "Compliance after core load"},
]

# ── Constants registry ────────────────────────────────────────
FRP_CONSTANTS: list[dict] = [
    {"code": "CA007", "record": "Cash Control Account", "required_value": "'050'", "status": "valid"},
    {"code": "AR007", "record": "Auto Rebalance", "required_value": "'+531'", "status": "valid"},
    {"code": "FM006", "record": "File Maintenance", "required_value": "'+450'", "status": "valid"},
    {"code": "PH007 pos 1–9", "record": "Participant Header", "required_value": "⚠ all zeros", "status": "valid"},
    {"code": "AI027", "record": "Associated Individual", "required_value": "'AI'", "status": "valid"},
    {"code": "EQ027", "record": "Equity Wash", "required_value": "'EQ'", "status": "valid"},
]


def frp_stats() -> dict[str, int]:
    """Headline stats for the Frp KB summary."""
    elements = sum(len(r["fields"]) for r in FRP_RECORDS)
    txn_fields = sum(len(c["fields"]) for c in FRP_TXN_CARDS)
    return {
        "records": len(FRP_RECORDS),
        "elements": elements,
        "txn_count": len(FRP_TXN_CARDS),
        "txn_fields": txn_fields,
    }
