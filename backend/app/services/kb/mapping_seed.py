"""
app/services/kb/mapping_seed.py
Reference AI-proposed mapping catalogue for migration projects.

Ported from the v5 prototype (MAPPINGS + MAPPINGS_EXTRA). Each row is a Relius
source → Frp target proposal with a confidence and domain; the T-code is
derived the same way the prototype does. Filtered to the project's selected
tables when a mapping run is seeded.
"""
from __future__ import annotations

# frp=record, src=table, field, tgt=target display, conf, type, dom, note
MAPPING_CATALOGUE: list[dict] = [
    {"frp": "Participant Header", "src": "PLANEE", "field": "PLANNO", "tgt": "PH005 Plan ID", "conf": 99, "type": "direct", "dom": "part", "note": "Primary key — cannot be file maintained"},
    {"frp": "Participant Header", "src": "PLANEESTAT", "field": "PARTSTATCD", "tgt": "PH Participant Status", "conf": 88, "type": "crosswalk", "dom": "part", "note": "A=Active, T=Terminated, R=Retired, D=Deceased"},
    {"frp": "Participant Header", "src": "PLANEEVEST", "field": "VESTPCT", "tgt": "PH Vested Percent", "conf": 92, "type": "direct", "dom": "part", "note": "0.00–100.00 range validation required"},
    {"frp": "Participant Header", "src": "PERSON", "field": "BIRTHDATE", "tgt": "PH200 Date of Birth", "conf": 96, "type": "direct", "dom": "part", "note": "Format: YYYYMMDD"},
    {"frp": "Participant Header", "src": "PLANEE", "field": "ENTDATE", "tgt": "PH250 Participation Entry Date", "conf": 92, "type": "direct", "dom": "part", "note": ""},
    {"frp": "Participant Header", "src": "PLANEE2", "field": "TERMDATE", "tgt": "PH220 Termination Date", "conf": 88, "type": "direct", "dom": "part", "note": "00000000 if null"},
    {"frp": "Participant Header", "src": "PERSON", "field": "MARSTATCD", "tgt": "PH300 Marital Status", "conf": 79, "type": "crosswalk", "dom": "part", "note": "M→01, S→02, D→03, W→04"},
    {"frp": "Participant Source", "src": "PLANEECONTRPCT", "field": "CONTRPCT", "tgt": "PS200 Deferral Rate", "conf": 84, "type": "transform", "dom": "part", "note": "0.00–100.00 only"},
    {"frp": "Plan Record", "src": "PLANSTAT", "field": "PLANNAM", "tgt": "PL100 Plan Name", "conf": 96, "type": "direct", "dom": "plan", "note": ""},
    {"frp": "Plan Record", "src": "PLANDYN", "field": "YRBEGDATE", "tgt": "PL300 Plan Year Begin", "conf": 89, "type": "direct", "dom": "plan", "note": ""},
    {"frp": "Plan Record", "src": "PLANDYN", "field": "VESTYRSMETHODCD", "tgt": "PL Vesting Method", "conf": 72, "type": "transform", "dom": "plan", "note": "Code crosswalk required"},
    {"frp": "Plan Record", "src": "PLANDYN", "field": "PSTCNT", "tgt": "PL101 Posting Counter", "conf": 88, "type": "direct", "dom": "plan", "note": "🔴 Must equal last BR170"},
    {"frp": "History Base (HIVR)", "src": "TRANSLED", "field": "TRANSTYPECD", "tgt": "BR101 Transaction Code", "conf": 58, "type": "complex", "dom": "trans", "note": "⚠ Per tx-type catalogue"},
    {"frp": "History Base (HIVR)", "src": "TRANSLED", "field": "TOTALDOLAMT", "tgt": "BR (cash/value — tx-type dep)", "conf": 55, "type": "complex", "dom": "trans", "note": "⚠ Field meaning varies by TRANSTYPECD"},
    {"frp": "History Base (HIVR)", "src": "TRANSLED", "field": "NUMOFUNITSNUM", "tgt": "BR111 Shares", "conf": 65, "type": "complex", "dom": "trans", "note": "Only when CashShare/UnitCode=Y"},
    {"frp": "Loan Header", "src": "EELOAN", "field": "INITLOANAMT", "tgt": "LH Original Loan Amount", "conf": 93, "type": "direct", "dom": "loans", "note": ""},
    {"frp": "Loan Header", "src": "EELOAN", "field": "INTRSTRATEPCT", "tgt": "LH Interest Rate", "conf": 91, "type": "direct", "dom": "loans", "note": ""},
    {"frp": "Loan Header", "src": "EELOAN", "field": "CURRBALAMT", "tgt": "LH Current Balance", "conf": 90, "type": "direct", "dom": "loans", "note": "Must not exceed INITLOANAMT"},
    {"frp": "Loan Header", "src": "EELOAN", "field": "NEXTPAYDATE", "tgt": "LH Next Payment Date", "conf": 88, "type": "direct", "dom": "loans", "note": ""},
    {"frp": "Loan Fund", "src": "EELOANACCT", "field": "LOANACTIONAMT", "tgt": "LF Fund Loan Amount", "conf": 87, "type": "direct", "dom": "loans", "note": ""},
    {"frp": "Loan Payments", "src": "LOANTRANSHIST", "field": "PMTPRNCPLAMT", "tgt": "LP Principal Payment", "conf": 89, "type": "direct", "dom": "loans", "note": ""},
    {"frp": "Loan Payments", "src": "LOANTRANSHIST", "field": "PMTINTRSTAMT", "tgt": "LP Interest Payment", "conf": 89, "type": "direct", "dom": "loans", "note": "Separate from HIVR share repurchase"},
    {"frp": "Fund Control", "src": "PLANINVEST", "field": "FUNDID", "tgt": "FC Fund ID", "conf": 95, "type": "direct", "dom": "invest", "note": ""},
    {"frp": "Fund Control", "src": "FUND", "field": "FUNDNAM", "tgt": "FC Fund Name", "conf": 94, "type": "direct", "dom": "invest", "note": ""},
    {"frp": "Daily Price Rate", "src": "FUNDHIST", "field": "FUNDVAL", "tgt": "DP NAV Price", "conf": 92, "type": "direct", "dom": "invest", "note": "MAX(FUNDVALDATE) per fund only"},
    {"frp": "Compensation Rec.", "src": "PLANEE", "field": "ADJ415COMPAMT", "tgt": "CM105 Plan Compensation", "conf": 81, "type": "transform", "dom": "comp", "note": ""},
    {"frp": "Vesting", "src": "PLANEEVEST", "field": "VESTEDPCT", "tgt": "Vested Percent", "conf": 92, "type": "direct", "dom": "comp", "note": ""},
    {"frp": "Salary Record", "src": "PAYROLL", "field": "SALAMT", "tgt": "SL Salary Amount", "conf": 88, "type": "direct", "dom": "payroll", "note": ""},
    {"frp": "Salary Record", "src": "PAYROLL", "field": "DEFERAMT", "tgt": "SL Deferral Amount", "conf": 85, "type": "direct", "dom": "payroll", "note": ""},
    # multi-source / extra
    {"frp": "Participant Header", "src": "PERSON", "field": "FIRSTNAM + MIDNAM + LASTNAM", "tgt": "PH (composite Full Name)", "conf": 91, "type": "derived", "dom": "part", "note": "Multi-source: First+Mid+Last → composite name", "multi": True},
    {"frp": "Alternate Address", "src": "PERSON", "field": "CITYADDR + STATEADDR + ZIPADDR", "tgt": "AA City/State/Zip", "conf": 93, "type": "direct", "dom": "part", "note": "Multi-source: City+State+Zip → AA components", "multi": True},
    {"frp": "Participant Header", "src": "PERSON", "field": "EMAILADDR", "tgt": "PH425 Email Address", "conf": 85, "type": "direct", "dom": "part", "note": ""},
    {"frp": "Associated Indiv.", "src": "BENEFICIARY", "field": "BENPCT", "tgt": "AI200 Beneficiary Pct", "conf": 88, "type": "direct", "dom": "part", "note": "0–100%"},
    {"frp": "Plan Record", "src": "PLANSTAT", "field": "PLANID", "tgt": "PL005 Plan ID", "conf": 99, "type": "direct", "dom": "plan", "note": "Primary key"},
    {"frp": "Plan Record", "src": "PLANDYN", "field": "PLANTYPE", "tgt": "PL200 Plan Type", "conf": 85, "type": "crosswalk", "dom": "plan", "note": "401K→K, 403B→B, 457→7"},
    {"frp": "Salary Record", "src": "PAYROLL", "field": "W2AMT", "tgt": "SL W2 Amount", "conf": 84, "type": "direct", "dom": "payroll", "note": ""},
    {"frp": "History Base (HIVR)", "src": "TRANSLED", "field": "POSTNO", "tgt": "BR170 Posting Counter", "conf": 92, "type": "direct", "dom": "trans", "note": "🔴 Drives PL101 & PH025 sync"},
    {"frp": "History Base (HIVR)", "src": "TRANSLED", "field": "TRANSDATE", "tgt": "BR320 Origination Date", "conf": 90, "type": "direct", "dom": "trans", "note": "YYYYMMDD"},
    {"frp": "Disbursement", "src": "TRANSPAYEE", "field": "PAYEEAMT", "tgt": "DB120 Percent of Split", "conf": 75, "type": "transform", "dom": "trans", "note": "Convert $ to % of total"},
    {"frp": "Participant Fund", "src": "PARTALLODET", "field": "ALLOPCT", "tgt": "PF Election Percent", "conf": 88, "type": "direct", "dom": "invest", "note": ""},
    {"frp": "Daily Price Rate", "src": "FUNDHIST", "field": "FUNDVALDATE", "tgt": "DP Trade Date", "conf": 96, "type": "direct", "dom": "invest", "note": "MAX per fund only"},
    {"frp": "Price ID", "src": "FUND", "field": "FUNDCLASS", "tgt": "PI Asset Class", "conf": 82, "type": "crosswalk", "dom": "invest", "note": "EQ/FI/MM/RE crosswalk"},
]


def derive_txn_code(m: dict) -> str | None:
    """
    Assign an Frp transaction card to a mapping. Follows the prototype's intent
    but matches keywords against the Frp record name (not the domain string) so
    'payroll' no longer collides with the 'roll' keyword.
    """
    frp = (m.get("frp") or "").lower()
    dom = m.get("dom")
    if "loan" in frp or dom == "loans":
        return "T022"
    if dom == "part" or "particip" in frp:
        return "T813"
    if any(k in frp for k in ("activity", "hivr", "history", "roll")):
        return "T035"
    if dom == "invest" or any(k in frp for k in ("fund", "invest", "price", "dividend")):
        return "T039"
    return None
