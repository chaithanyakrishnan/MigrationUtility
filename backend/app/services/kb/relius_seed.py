"""
app/services/kb/relius_seed.py
Reference catalogue for the Relius Knowledge Base.

Ported from the v5 prototype (DOMAINS + DOMAIN_REVIEW_FIELDS). Seeds the KB with
a known Relius schema so the KB flow is always populated; real schema extraction
(services/schema/extractor.py) can augment/replace this later.
"""
from __future__ import annotations

# One entry per business domain. `fields` are the detailed, SME-reviewable
# columns; `tables` is the full table list for the domain.
RELIUS_DOMAINS: list[dict] = [
    {
        "domain_id": "plan", "name": "Plan Management", "icon": "📋",
        "row_estimate": "12K", "completeness": 91,
        "tables": ["PLANSTAT", "PLANDYN", "PLANDYN2", "PLANCOMP", "PLANHRS", "PLANSRCE",
                   "PLANSRCEELIG", "PLANSRCEALLOFORMULA", "PLANLIM", "PLANLOCAL",
                   "PLANANNUFORM", "PLANLOANLOAN", "PLANKMTEST", "PLANDESC", "PLANDISTR",
                   "PLANAUDIT", "PLANSHARACCT", "PLANLOCDIVISION"],
        "fields": [
            {"table": "PLANSTAT", "field": "PLANID", "name": "Plan ID", "data_type": "CHAR(6)", "is_key": True, "description": "Primary plan identifier. Cannot be changed after creation."},
            {"table": "PLANSTAT", "field": "PLANNAM", "name": "Plan Name", "data_type": "VARCHAR(50)", "is_key": False, "description": "Full legal name of the plan as registered."},
            {"table": "PLANDYN", "field": "PLANTYPE", "name": "Plan Type", "data_type": "CHAR(3)", "is_key": False, "description": "401K, 403B, 457 — determines regulatory treatment."},
            {"table": "PLANDYN", "field": "YRBEGDATE", "name": "Plan Year Begin Date", "data_type": "N8D00", "is_key": False, "description": "First day of the plan year. YYYYMMDD format."},
            {"table": "PLANDYN", "field": "PSTCNT", "name": "Post Counter", "data_type": "INTEGER", "is_key": False, "description": "🔴 Critical — must equal last BR170 after migration load."},
            {"table": "PLANDYN", "field": "VESTYRSMETHODCD", "name": "Vesting Method", "data_type": "CHAR(3)", "is_key": False, "description": "Vesting schedule code — crosswalk required for Frp."},
            {"table": "PLANSRCE", "field": "SRCECD", "name": "Source Code", "data_type": "CHAR(6)", "is_key": True, "description": "Identifies the contribution source (ER, EE, Match, etc.)."},
            {"table": "PLANSRCE", "field": "DEFLIMITAMT", "name": "Deferral Limit", "data_type": "N15D02", "is_key": False, "description": "IRS annual deferral limit for this source."},
            {"table": "PLANLOCDIVISION", "field": "DIVID", "name": "Division ID", "data_type": "CHAR(4)", "is_key": True, "description": "4-char division identifier. Maps to DS007 in Frp."},
            {"table": "PLANLOCDIVISION", "field": "DIVNAM", "name": "Division Name", "data_type": "VARCHAR(30)", "is_key": False, "description": "Primary name of the division or subsidiary."},
        ],
    },
    {
        "domain_id": "part", "name": "Participant", "icon": "👤",
        "row_estimate": "840K", "completeness": 94,
        "tables": ["PERSON", "PLANEE", "PLANEE2", "PLANEESTAT", "PLANEEVEST", "PLANEESRCEYR",
                   "PLANEESRCEELIG", "PLANEEEKMTEST", "PLANEECONTRPCT", "BENEFICIARY",
                   "DEPENDENT", "PARTALLOMSTR"],
        "fields": [
            {"table": "PERSON", "field": "SSNUM", "name": "SSN", "data_type": "CHAR(9)", "is_key": True, "description": "Social Security Number. Positions 1–9 of 17-char Frp participant ID."},
            {"table": "PERSON", "field": "LASTNAM", "name": "Last Name", "data_type": "VARCHAR(30)", "is_key": False, "description": "Participant last name. RPAD to 30 chars in fixed-length output."},
            {"table": "PERSON", "field": "FIRSTNAM", "name": "First Name", "data_type": "VARCHAR(20)", "is_key": False, "description": "Participant first name."},
            {"table": "PERSON", "field": "MIDNAM", "name": "Middle Name", "data_type": "VARCHAR(20)", "is_key": False, "description": "Middle name — combined with first/last for Frp name composite."},
            {"table": "PERSON", "field": "BIRTHDATE", "name": "Date of Birth", "data_type": "DATE", "is_key": False, "description": "Converted to YYYYMMDD (N8D00) for Frp PH200."},
            {"table": "PLANEE", "field": "ENTDATE", "name": "Plan Entry Date", "data_type": "DATE", "is_key": False, "description": "Date participant entered the plan. Maps to PH250."},
            {"table": "PLANEE2", "field": "TERMDATE", "name": "Termination Date", "data_type": "DATE", "is_key": False, "description": "Null if active. Output as 00000000 when null."},
            {"table": "PERSON", "field": "MARSTATCD", "name": "Marital Status", "data_type": "CHAR(1)", "is_key": False, "description": "M/S/D/W — crosswalk required: M→MA, S→SN, D→DV, W→WD."},
            {"table": "PERSON", "field": "STREET1ADDR", "name": "Address Line 1", "data_type": "VARCHAR(60)", "is_key": False, "description": "Primary street address. RPAD to 60 chars."},
            {"table": "PERSON", "field": "CITYADDR", "name": "City", "data_type": "VARCHAR(30)", "is_key": False, "description": "City. RPAD to 30 chars."},
            {"table": "PERSON", "field": "STATEADDR", "name": "State", "data_type": "CHAR(2)", "is_key": False, "description": "2-char state code. Maps to PH415."},
            {"table": "BENEFICIARY", "field": "BENPCT", "name": "Beneficiary Pct", "data_type": "DECIMAL(5,2)", "is_key": False, "description": "Percentage allocated to this beneficiary. Must sum to 100%."},
        ],
    },
    {
        "domain_id": "payroll", "name": "Payroll & Salary", "icon": "💵",
        "row_estimate": "95K", "completeness": 88,
        "tables": ["PAYROLL", "PAYROLLADJ", "PLANPAYROLLHIST", "USERPAYROLL", "PLANEECUSTOMDATA",
                   "DIV", "ERADDRESS", "EMPLOYER", "PLANEEHRS"],
        "fields": [
            {"table": "PAYROLL", "field": "SSNUM", "name": "SSN", "data_type": "CHAR(9)", "is_key": True, "description": "Links payroll record to participant."},
            {"table": "PAYROLL", "field": "SALAMT", "name": "Salary Amount", "data_type": "DECIMAL(13,2)", "is_key": False, "description": "Gross salary for this pay period."},
            {"table": "PAYROLL", "field": "DEFERAMT", "name": "Deferral Amount", "data_type": "DECIMAL(13,2)", "is_key": False, "description": "Employee deferral contribution for this period."},
            {"table": "PAYROLL", "field": "W2AMT", "name": "W2 Amount", "data_type": "DECIMAL(13,2)", "is_key": False, "description": "W-2 reportable compensation amount."},
            {"table": "PAYROLL", "field": "PAYPERIOD", "name": "Pay Period", "data_type": "CHAR(2)", "is_key": True, "description": "Pay period identifier (01–26 for bi-weekly, etc.)."},
            {"table": "PAYROLLADJ", "field": "ADJAMT", "name": "Adjustment Amount", "data_type": "DECIMAL(13,2)", "is_key": False, "description": "Payroll correction/adjustment amount."},
            {"table": "PLANEEHRS", "field": "HOURSQTY", "name": "Hours of Service", "data_type": "DECIMAL(7,2)", "is_key": False, "description": "Hours worked — used for vesting calculations."},
        ],
    },
    {
        "domain_id": "invest", "name": "Investments", "icon": "📈",
        "row_estimate": "180K", "completeness": 95,
        "tables": ["PLANINVEST", "FUND", "FUNDHIST", "FUNDPERFHIST", "PLANACCT", "ACCTBAL",
                   "PARTALLODET", "PLANSHRMGMT"],
        "fields": [
            {"table": "FUND", "field": "FUNDID", "name": "Fund ID", "data_type": "CHAR(12)", "is_key": True, "description": "Global fund identifier. Maps to Price ID in Frp."},
            {"table": "FUND", "field": "FUNDNAM", "name": "Fund Name", "data_type": "VARCHAR(40)", "is_key": False, "description": "Full fund name. Maps to PI Long Name."},
            {"table": "FUND", "field": "FUNDCLASS", "name": "Asset Class", "data_type": "CHAR(3)", "is_key": False, "description": "EQ/FI/MM/RE — crosswalk required for Frp PI."},
            {"table": "FUNDHIST", "field": "FUNDVAL", "name": "NAV Price", "data_type": "DECIMAL(10,6)", "is_key": False, "description": "Daily fund price (NAV). Only MAX(FUNDVALDATE) migrated per fund."},
            {"table": "FUNDHIST", "field": "FUNDVALDATE", "name": "Price Date", "data_type": "DATE", "is_key": True, "description": "Valuation date. YYYYMMDD format in output."},
            {"table": "PLANINVEST", "field": "TRANSALLOW", "name": "Transfer Allow", "data_type": "CHAR(1)", "is_key": False, "description": "Maps to FC063 Transfer Eligibility Flag — 9 legal values."},
            {"table": "PARTALLODET", "field": "ALLOPCT", "name": "Allocation Pct", "data_type": "DECIMAL(5,2)", "is_key": False, "description": "Participant fund election percentage. Must sum to 100%."},
        ],
    },
    {
        "domain_id": "loans", "name": "Loans", "icon": "🏦",
        "row_estimate": "48K", "completeness": 83,
        "tables": ["EELOAN", "EELOANACCT", "LOANTRANSHIST", "LOANPAYROLL", "PLANLOANLOAN"],
        "fields": [
            {"table": "EELOAN", "field": "LOANNUM", "name": "Loan Number", "data_type": "CHAR(6)", "is_key": True, "description": "Unique loan identifier per participant. Maps to LH Loan Seq."},
            {"table": "EELOAN", "field": "INITLOANAMT", "name": "Original Amount", "data_type": "DECIMAL(11,2)", "is_key": False, "description": "Loan principal at origination. Cannot exceed plan limits."},
            {"table": "EELOAN", "field": "CURRBALAMT", "name": "Current Balance", "data_type": "DECIMAL(11,2)", "is_key": False, "description": "Outstanding balance. Validated: must not exceed INITLOANAMT."},
            {"table": "EELOAN", "field": "INTRSTRATEPCT", "name": "Interest Rate", "data_type": "DECIMAL(5,4)", "is_key": False, "description": "Annual interest rate. Multiply ×10000 for Frp format."},
            {"table": "EELOAN", "field": "NEXTPAYDATE", "name": "Next Payment Date", "data_type": "DATE", "is_key": False, "description": "Next scheduled payment date. 00000000 if null."},
            {"table": "EELOAN", "field": "LOANDURTYPECD", "name": "Loan Type", "data_type": "CHAR(1)", "is_key": False, "description": "P=Personal→PR, R=Residential→RE."},
            {"table": "EELOANACCT", "field": "LOANACTIONAMT", "name": "Fund Loan Amt", "data_type": "DECIMAL(11,2)", "is_key": False, "description": "Amount sourced from this fund at origination. Sums to principal."},
            {"table": "LOANTRANSHIST", "field": "PMTPRNCPLAMT", "name": "Principal Paid", "data_type": "DECIMAL(11,2)", "is_key": False, "description": "Principal portion of payment. Separate from HIVR share repurchase."},
        ],
    },
    {
        "domain_id": "comp", "name": "Compliance", "icon": "⚖️",
        "row_estimate": "95K", "completeness": 78,
        "tables": ["PLANKMTEST", "PLANEEEKMTEST", "PLANPAYROLLHIST", "GBLVESTSCHMSTR",
                   "GBLVESTSCHDET", "PLANCOMP", "PLANLIM"],
        "fields": [
            {"table": "PLANKMTEST", "field": "CM005", "name": "Plan Num", "data_type": "X(6)", "is_key": True, "description": "Plan identifier — part of the compliance test record key."},
            {"table": "PLANKMTEST", "field": "CM007", "name": "Participant ID", "data_type": "X(17)", "is_key": True, "description": "17-char composite participant ID. Sub-plan and extension optional."},
            {"table": "PLANKMTEST", "field": "CM011", "name": "Effective Date", "data_type": "N8D00", "is_key": True, "description": "Effective date — defines the test year boundary."},
            {"table": "PLANKMTEST", "field": "CM105", "name": "Plan Compensation", "data_type": "N15D02", "is_key": False, "description": "Total plan compensation for 415 testing. Includes all eligible pay."},
            {"table": "PLANKMTEST", "field": "CM110", "name": "Social Security Comp", "data_type": "N15D02", "is_key": False, "description": "Social security compensation for ACP/ADP testing purposes."},
            {"table": "PLANEEEKMTEST", "field": "SL005", "name": "Plan ID", "data_type": "X(6)", "is_key": True, "description": "Plan identifier for the salary record."},
            {"table": "PLANEEEKMTEST", "field": "SL007", "name": "Participant ID", "data_type": "X(17)", "is_key": True, "description": "17-char composite. Positions 1–9 SSN required."},
        ],
    },
    {
        "domain_id": "annuity", "name": "Annuity", "icon": "📉",
        "row_estimate": "8K", "completeness": 61,
        "tables": ["ANMASTER", "ANPOINTER", "ANFORECAST", "ANBENEF"],
        "fields": [
            {"table": "ANMASTER", "field": "AM005", "name": "Plan ID", "data_type": "CHAR(6)", "is_key": True, "description": "Primary key — identifies the plan. Cannot be file maintained."},
            {"table": "ANMASTER", "field": "AM007", "name": "Plan Sequence Number", "data_type": "N3D00", "is_key": True, "description": "Constant value used for record sorting. Part of the record key."},
            {"table": "ANMASTER", "field": "AM010", "name": "Participant ID", "data_type": "X(17)", "is_key": True, "description": "17-char composite: positions 1–9 SSN, 10–15 Sub Plan, 16–17 Extension."},
            {"table": "ANMASTER", "field": "AM600", "name": "Federal Withholding Use", "data_type": "X(1)", "is_key": False, "description": "Controls whether federal tax withholding applies to annuity distributions."},
            {"table": "ANPOINTER", "field": "AP005", "name": "Plan Number", "data_type": "X(6)", "is_key": True, "description": "Part of 6-field key structure linking annuity views to master records."},
            {"table": "ANFORECAST", "field": "FR006", "name": "Plan Number", "data_type": "X(6)", "is_key": True, "description": "Forecast Header — identifies the plan for this forecasting run."},
            {"table": "ANBENEF", "field": "FB060", "name": "Beneficiary Part. No.", "data_type": "X(9)", "is_key": True, "description": "Participant number of the designated beneficiary for this forecast run."},
        ],
    },
    {
        "domain_id": "trans", "name": "Transactions", "icon": "🔄",
        "row_estimate": "1.2M", "completeness": 88,
        "tables": ["TRANSLED", "TRANS", "TRANSPAYEE", "TRANSLED2", "PLANDISTR", "LOANTRANSHIST",
                   "CASHOFFSET", "TATRANS", "AUDIT_TRAIL", "CENAUDIT", "PLANAUDIT",
                   "PARTALLOMSTR", "PARTALLODET", "USERPAYROLL"],
        "fields": [
            {"table": "TRANSLED", "field": "PLANID", "name": "Plan ID", "data_type": "CHAR(6)", "is_key": True, "description": "Plan identifier for this transaction."},
            {"table": "TRANSLED", "field": "SSNUM", "name": "SSN", "data_type": "CHAR(9)", "is_key": True, "description": "Participant SSN. Padded to 17-char composite for Frp BR007."},
            {"table": "TRANSLED", "field": "TRANSTYPECD", "name": "Transaction Type", "data_type": "CHAR(4)", "is_key": False, "description": "⚠ Maps to BR101. Field meanings (cash/shares/value) differ per type."},
            {"table": "TRANSLED", "field": "TOTALDOLAMT", "name": "Transaction Amount", "data_type": "DECIMAL(13,2)", "is_key": False, "description": "Maps to BR cash OR value depending on TRANSTYPECD — per tx-type catalogue."},
            {"table": "TRANSLED", "field": "TRANSDATE", "name": "Transaction Date", "data_type": "DATE", "is_key": True, "description": "Maps to BR320 Transaction Origination Date."},
            {"table": "TRANSLED", "field": "POSTNO", "name": "Post Number", "data_type": "INTEGER", "is_key": False, "description": "🔴 Maps to BR170 Posting Counter. Drives PL101 and PH025 sync."},
            {"table": "TRANSPAYEE", "field": "PAYEEAMT", "name": "Payee Amount", "data_type": "DECIMAL(11,2)", "is_key": False, "description": "Maps to DB120 Percent of Split. Convert $ to % of total disbursement."},
        ],
    },
]


def relius_stats() -> dict[str, int]:
    """Headline stats for the Relius KB summary, matching the prototype."""
    tables = sum(len(d["tables"]) for d in RELIUS_DOMAINS)
    fields = sum(len(d["fields"]) for d in RELIUS_DOMAINS)
    return {"tables": tables, "domains": len(RELIUS_DOMAINS), "fields": fields}
