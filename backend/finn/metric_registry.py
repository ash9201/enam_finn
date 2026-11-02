"""Financial vocabulary and deterministic intent. Recognition is not calculation support."""

import re
from dataclasses import dataclass, replace

VERSION = "financial-intent-v1"


def normalise(text):
    return " ".join(re.sub(r"[^a-z0-9%]+", " ", text.casefold()).split())


@dataclass(frozen=True)
class Metric:
    id: str
    name: str
    aliases: tuple[str, ...]
    category: str
    unit_kind: str = "money"
    formula: str | None = None
    inputs: tuple[str, ...] = ()
    applicable: str = "all"
    source_requirement: str = "Explicitly labelled primary-source value, period, entity and basis."
    restriction: str = "No inferred table columns, units, accounting bases or adjusted definitions."

    @property
    def support(self):
        if self.id.startswith("unspecified_"):
            return "needs_clarification"
        return (
            "dated_reported_only"
            if self.category == "valuation"
            else "reported_or_calculated"
            if self.formula
            else "reported_only"
        )


# id | display name | aliases. Separate definitions remain separate metrics.
VOCABULARY = {
    "profitability": """
revenue|Revenue from operations|revenue;sales;turnover;revenue from operations;net sales
total_income|Total income|total income
revenue_growth|Revenue growth|revenue growth;sales growth;turnover growth
revenue_cagr|Revenue CAGR|revenue cagr;sales cagr
profit_cagr|Profit CAGR|profit cagr;earnings cagr
unspecified_cagr|CAGR (base metric unspecified)|cagr
unspecified_growth|Growth (base metric unspecified)|qoq growth;yoy growth;growth rate
gross_profit|Gross profit|gross profit
gross_margin|Gross profit margin|gross margin;gross profit margin
ebit|EBIT|ebit;profit before interest and tax;earnings before interest and tax
operating_profit|Operating profit|operating profit
operating_margin|Operating profit margin|operating profit margin;operating margin
ebit_margin|EBIT margin|ebit margin
ebitda|EBITDA|ebitda;earnings before interest tax depreciation and amortization
ebitda_margin|EBITDA margin|ebitda margin
adjusted_ebitda|Adjusted EBITDA|adjusted ebitda;underlying ebitda;ebitda adjusted;ebitda underlying;ebitda excluding exceptional items;ebitda before exceptional items
pbt|Profit before tax|pbt;profit before tax;profit before taxation
pat|Profit after tax|pat;net profit;net income;profit after tax;profit for the year;profit for the period
profit_owners|Profit attributable to owners|profit attributable to owners;profit attributable to equity holders;profit attributable to owners of the company;profit attributable to owners of company
net_margin|Net profit margin|net profit margin;pat margin;net margin
operating_expenses|Operating expenses|operating expenses;opex
employee_expenses|Employee expenses|employee expenses;employee benefit expenses;employee benefits expense
finance_cost|Finance costs|finance costs;finance cost
interest_expense|Interest expense|interest expense;interest expenses;interest on borrowings;interest cost
depreciation|Depreciation and amortisation|depreciation and amortisation;depreciation and amortization;d&a
eps|Basic EPS|eps;basic eps;earnings per share;basic earnings per share
diluted_eps|Diluted EPS|diluted eps;diluted earnings per share
profit_growth|Profit growth|profit growth;earnings growth;net profit growth;pat growth
tax_expense|Income tax expense|income tax expense;tax expense;total tax expense
effective_tax_rate|Effective tax rate|effective tax rate
segment_revenue|Segment revenue|segment revenue;segment sales
segment_profit|Segment profit|segment profit;segment result;segment results
segment_margin|Segment margin|segment margin;segment margins
segment_contribution|Segment contribution|segment contribution;segment contributions
""",
    "leverage": """
debt|Total borrowings|total debt;total borrowings;gross debt;borrowings;debt
short_debt|Short-term borrowings|short term debt;short term borrowings;current borrowings
long_debt|Long-term borrowings|long term debt;long term borrowings;non current borrowings
net_debt|Net debt|net debt
equity|Shareholders' equity|shareholders equity;shareholder equity;shareholders funds;net worth;total equity;total equity attributable to owners of the company;equity attributable to owners of the company
debt_equity|Debt-to-equity ratio|debt to equity;debt equity;debt to equity ratio;debt equity ratio;d/e;d/e ratio
net_debt_equity|Net-debt-to-equity ratio|net debt to equity;net debt equity ratio
debt_assets|Debt-to-assets ratio|debt to assets;debt assets ratio
debt_capital|Debt-to-capital ratio|debt to capital;debt capital ratio
liabilities_equity|Liabilities-to-equity ratio|total liabilities to equity;liabilities to equity
equity_ratio|Equity ratio|equity ratio
debt_ebitda|Debt-to-EBITDA ratio|debt to ebitda;debt ebitda
net_debt_ebitda|Net-debt-to-EBITDA ratio|net debt to ebitda;net debt ebitda
interest_coverage|Interest coverage|interest coverage;interest coverage ratio
interest_service_coverage|Interest service coverage ratio|interest service coverage;interest service coverage ratio;iscr
dscr|Debt-service coverage ratio|dscr;debt service coverage;debt service coverage ratio
gearing|Capital gearing|capital gearing;gearing ratio
cash|Cash and cash equivalents|cash and cash equivalents;cash equivalents
net_cash|Net cash position|net cash;net cash position
total_assets|Total assets|total assets
total_liabilities|Total liabilities|total liabilities
""",
    "liquidity": """
current_ratio|Current ratio|current ratio
quick_ratio|Quick ratio|quick ratio;acid test ratio
cash_ratio|Cash ratio|cash ratio
working_capital|Working capital|working capital;net working capital
current_assets|Current assets|current assets;total current assets
current_liabilities|Current liabilities|current liabilities;total current liabilities
inventory|Inventory|inventory;inventories
receivables|Trade receivables|trade receivables;accounts receivable
payables|Trade payables|trade payables;accounts payable
inventory_turnover|Inventory turnover|inventory turnover;inventory turnover ratio
receivables_turnover|Receivables turnover|receivables turnover;receivable turnover;trade receivable turnover
payables_turnover|Payables turnover|payables turnover;payable turnover;trade payable turnover
dso|Days sales outstanding|dso;days sales outstanding;receivable days
dio|Days inventory outstanding|dio;days inventory outstanding;inventory days
dpo|Days payable outstanding|dpo;days payable outstanding;payable days
cash_cycle|Cash conversion cycle|cash conversion cycle
ocf_ratio|Operating cash flow ratio|operating cash flow ratio
""",
    "returns": """
roe|Return on equity|roe;return on equity;return on average equity;return on avg equity;roae
ronw|Return on net worth|ronw;return on net worth
roa|Return on assets|roa;return on assets
roce|Return on capital employed|roce;return on capital employed
roic|Return on invested capital|roic;return on invested capital
asset_turnover|Asset turnover|asset turnover;total asset turnover
fixed_asset_turnover|Fixed asset turnover|fixed asset turnover
working_capital_turnover|Working capital turnover|working capital turnover;net capital turnover
capex|Capital expenditure|capex;capital expenditure;capital expenditures
cash_capex|Cash purchases of PPE and intangibles|cash capital expenditure;purchase of property plant equipment and intangible assets;purchase of property plant and equipment and intangible assets
cfo|Operating cash flow|operating cash flow;cash flow from operations;cfo;net cash from operating activities;net cash generated from operating activities;net cash used in operating activities;cash from operating activity
cfi|Investing cash flow|investing cash flow;net cash used in investing activities;net cash from investing activities
cff|Financing cash flow|financing cash flow;net cash used in financing activities;net cash from financing activities
fcf|Free cash flow|free cash flow;fcf
cash_conversion|Operating cash flow to net income|cash flow from operations to net income;operating cash flow to net income
dps|Dividend per share|dps;dividend per share
payout|Dividend payout ratio|dividend payout;dividend payout ratio
dividend_coverage|Dividend coverage|dividend coverage
book_value|Book value per share|book value per share;bvps
""",
    "valuation": """
pe|Price-to-earnings ratio|p/e;pe;pe ratio;price to earnings;price earnings ratio
forward_pe|Forward P/E|forward p/e;forward pe;forward price earnings;p/e forward;pe forward;estimated p/e;expected p/e
pb|Price-to-book ratio|p/b;pb ratio;price to book
ps|Price-to-sales ratio|p/s;ps ratio;price to sales
ev|Enterprise value|enterprise value;ev
ev_ebitda|EV/EBITDA|ev/ebitda;enterprise value to ebitda
ev_revenue|EV/revenue|ev/revenue;ev to revenue;enterprise value to revenue
market_cap|Market capitalisation|market cap;market capitalization;market capitalisation
dividend_yield|Dividend yield|dividend yield
earnings_yield|Earnings yield|earnings yield
shares|Shares outstanding|shares outstanding;number of shares outstanding
price|Share price|market price;share price;stock price
peg|PEG ratio|peg ratio;price earnings growth ratio
""",
    "banking": """
nii|Net interest income|nii;net interest income
nim|Net interest margin|nim;net interest margin
casa|CASA ratio|casa;casa ratio
gnpa|Gross NPA|gross npa;gross non performing assets
gnpa_ratio|Gross NPA ratio|gross npa ratio;gnpa ratio
nnpa|Net NPA|net npa;net non performing assets
nnpa_ratio|Net NPA ratio|net npa ratio;nnpa ratio
provision_coverage|Provision coverage ratio|provision coverage ratio;pcr
credit_cost|Credit cost|credit cost;credit costs
car|Capital adequacy ratio|capital adequacy ratio;crar;car ratio
cet1|CET1 ratio|cet1;cet1 ratio
lcr|Liquidity coverage ratio|lcr;liquidity coverage ratio
cost_income|Cost-to-income ratio|cost to income;cost income ratio
credit_deposit|Credit-to-deposit ratio|credit to deposit;credit deposit ratio
advances|Advances|total advances;advances
deposits|Deposits|total deposits;deposits
deposit_growth|Deposit growth|deposit growth
""",
    "insurance": """
gwp|Gross written premium|gwp;gross written premium
nwp|Net written premium|nwp;net written premium
ape|Annualised premium equivalent|ape;annualised premium equivalent;annualized premium equivalent
vnb|Value of new business|vnb;value of new business
vnb_margin|VNB margin|vnb margin
combined_ratio|Combined ratio|combined ratio
claims_ratio|Claims ratio|claims ratio;loss ratio
solvency|Solvency ratio|solvency ratio
persistency|Persistency ratio|persistency ratio
aum|Assets under management|aum;assets under management
aum_growth|AUM growth|aum growth;assets under management growth
fee_income|Management fee income|management fee income
""",
    "operating": """
arpu|Average revenue per user|arpu;average revenue per user
subscriber_growth|Subscriber growth|subscriber growth
churn|Churn|churn;churn rate
capacity|Generation capacity|generation capacity;power generation capacity
plf|Plant load factor|plf;plant load factor
grm|Gross refining margin|grm;gross refining margin
production_volume|Production volume|production volume
sales_volume|Sales volume|sales volume
utilisation|Capacity utilisation|capacity utilisation;capacity utilization
order_book|Order book|order book
order_inflow|Order inflow|order inflow;order intake
order_growth|Order-book growth|order book growth
occupancy|Occupancy|occupancy;occupancy rate
arr|Average revenue per room|average revenue per room;average room rate
""",
}

PERCENT = set(
    "revenue_growth revenue_cagr profit_cagr unspecified_cagr unspecified_growth gross_margin operating_margin ebit_margin ebitda_margin net_margin profit_growth effective_tax_rate roe roa roce roic payout dividend_yield earnings_yield nim casa gnpa_ratio nnpa_ratio provision_coverage credit_cost car cet1 lcr cost_income credit_deposit deposit_growth vnb_margin combined_ratio claims_ratio persistency aum_growth subscriber_growth churn plf utilisation order_growth occupancy".split()
)
RATIOS = set(
    "debt_equity net_debt_equity debt_assets debt_capital liabilities_equity equity_ratio debt_ebitda net_debt_ebitda interest_coverage dscr gearing current_ratio quick_ratio cash_ratio inventory_turnover receivables_turnover payables_turnover ocf_ratio asset_turnover fixed_asset_turnover working_capital_turnover cash_conversion dividend_coverage pe forward_pe pb ps ev_ebitda ev_revenue peg solvency".split()
)
PERCENT.add("ronw")
RATIOS.add("interest_service_coverage")

FORMULAS = {
    "debt": ("sum_debt", ("short_debt", "long_debt")),
    "net_debt": ("subtract", ("debt", "cash")),
    "net_cash": ("subtract", ("cash", "debt")),
    "debt_equity": ("ratio", ("debt", "equity")),
    "net_debt_equity": ("ratio", ("net_debt", "equity")),
    "current_ratio": ("ratio", ("current_assets", "current_liabilities")),
    "working_capital": ("subtract", ("current_assets", "current_liabilities")),
    "interest_coverage": ("ratio", ("ebit", "interest_expense")),
    "gross_margin": ("percent", ("gross_profit", "revenue")),
    "ebit_margin": ("percent", ("ebit", "revenue")),
    "operating_margin": ("percent", ("operating_profit", "revenue")),
    "ebitda_margin": ("percent", ("ebitda", "revenue")),
    "net_margin": ("percent", ("pat", "revenue")),
    "effective_tax_rate": ("percent", ("tax_expense", "pbt")),
    "roe": ("average_return", ("profit_owners", "equity")),
    "roce": ("average_roce", ("ebit", "total_assets", "current_liabilities")),
    "fcf": ("cash_flow", ("cfo", "cash_capex")),
    "revenue_growth": ("growth", ("revenue",)),
    "profit_growth": ("growth", ("pat",)),
}


def _registry():
    result = {}
    for category, rows in VOCABULARY.items():
        for row in rows.strip().splitlines():
            key, name, aliases = row.split("|")
            formula, inputs = FORMULAS.get(key, (None, ()))
            result[key] = Metric(
                key,
                name,
                tuple(aliases.split(";")),
                category,
                "percent"
                if key in PERCENT
                else "times"
                if key in RATIOS
                else "per_share"
                if key in {"eps", "diluted_eps", "dps", "book_value", "price", "arpu", "arr"}
                else "days"
                if key in {"dso", "dio", "dpo"}
                else "reported"
                if category == "operating" or key == "shares"
                else "money",
                formula,
                inputs,
                category if category in {"banking", "insurance", "operating"} else "all",
                restriction="Annual average balances required for computed returns; no annualisation or YTD subtraction."
                if key in {"roe", "roce"}
                else "Dated primary disclosure only; no live market value or forecasts inferred."
                if category == "valuation"
                else Metric.restriction,
            )
    return result


REGISTRY = _registry()
# Calculation scope and sector provenance are part of the inspectable registry.
INDUSTRIES = {
    "arpu": "telecom",
    "subscriber_growth": "telecom",
    "churn": "telecom",
    "capacity": "power",
    "plf": "power",
    "grm": "refining",
    "production_volume": "manufacturing",
    "sales_volume": "manufacturing",
    "utilisation": "manufacturing",
    "order_book": "manufacturing/infrastructure",
    "order_inflow": "manufacturing/infrastructure",
    "order_growth": "manufacturing/infrastructure",
    "occupancy": "hospitality",
    "arr": "hospitality",
    "aum": "asset management/financial services",
    "aum_growth": "asset management/financial services",
    "fee_income": "asset management/financial services",
}
for _key, _metric in list(REGISTRY.items()):
    REGISTRY[_key] = replace(
        _metric,
        applicable=INDUSTRIES.get(_key, _metric.applicable),
        restriction=_metric.restriction
        + (
            " Computations apply to non-financial companies only; direct sector disclosures remain distinct."
            if _metric.formula
            else ""
        ),
    )


def metric_matches(text):
    clean = normalise(text)
    matches = []
    for metric in REGISTRY.values():
        for alias in metric.aliases:
            for m in re.finditer(r"(?<!\w)" + re.escape(normalise(alias)) + r"(?!\w)", clean):
                matches.append((m.start(), m.end(), metric.id))
    selected = []
    for start, end, key in sorted(matches, key=lambda m: (-(m[1] - m[0]), m[0], m[2])):
        if not any(start < b and end > a for a, b, _ in selected):
            selected.append((start, end, key))
    return list(dict.fromkeys(m[2] for m in sorted(selected)))


@dataclass(frozen=True)
class FinancialIntent:
    metrics: tuple[str, ...]
    basis: str | None = None
    years: tuple[int, ...] = ()
    frequency: str | None = None
    growth_basis: str = "yoy"
    period_ends: tuple[str, ...] = ()
    unsupported_variants: tuple[str, ...] = ()


def financial_intent(question):
    clean = normalise(question)
    conceptual = re.search(
        r"\b(?:what does .+ mean|definition|define|meaning of|difference between|how (?:is|are) .+ calculated)\b",
        clean,
    )
    if conceptual and not re.search(r"\b(?:actual|value|latest|numerical)\b", clean):
        return None
    if re.search(r"\bexplain\b", clean) and not re.search(
        r"\b(?:of|for|their|company|value|actual|latest|current|interpret)\b", clean
    ):
        return None
    metrics = metric_matches(question)
    if re.search(r"\bwho\b|chief financial officer|employee turnover|staff turnover", clean):
        return None
    if re.search(r"\bcfo\s+(?:said|say|comment\w*|resign\w*|appoint\w*)\b", clean):
        metrics = [m for m in metrics if m != "cfo"]
    if re.search(r"\b(?:how profitable|financial health|financially healthy)\b", clean):
        extra = (
            ["debt_equity", "current_ratio", "net_margin", "roe", "cfo"]
            if re.search(r"financial health|financially healthy", clean)
            else ["net_margin", "roe", "roce"]
        )
        metrics = list(dict.fromkeys(metrics + extra))
    if not metrics:
        return None
    if (
        metrics == ["debt"]
        and re.search(r"\b(?:manag\w*|strategy|rating|risk)\b", clean)
        and not re.search(r"\b(?:how much|amount|total|level|value)\b", clean)
    ):
        return None
    if (
        set(metrics) <= {"revenue", "total_income", "cfo"}
        and re.search(
            r"business model|revenue (?:model|streams)|sources of revenue|how.*(?:generate|earn|make).*revenue|strategy",
            clean,
        )
        and not re.search(r"how much|value|amount|actual|ratio", clean)
    ):
        return None
    years = list(map(int, re.findall(r"\b(?:fy\s*)?(20\d{2})\b", clean)))
    for year, end in re.findall(r"\b(?:fy\s*)?(20\d{2})\s*[-/]\s*(\d{2})\b", question, re.I):
        years = [y for y in years if y != int(year)] + [int(year[:2] + end)]
    for short in re.findall(r"\bfy\s*(\d{2})\b", clean):
        years.append(2000 + int(short))
    basis = (
        "consolidated"
        if "consolidated" in clean.split()
        else "standalone"
        if "standalone" in clean.split()
        else None
    )
    if "consolidated" in clean and ("standalone" in clean or "stand alone" in clean):
        basis = "both"
    elif "stand alone" in clean:
        basis = "standalone"
    from finn.financial_tables import parse_date

    ends = []
    for raw in re.findall(
        r"\b\d{1,2}\s+[A-Za-z]+\s+20\d{2}\b|\b[A-Za-z]+\s+\d{1,2},?\s+20\d{2}\b|\b\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}\b",
        question,
    ):
        date = parse_date(raw)
        if date:
            ends.append(date)
    q = re.search(r"\bq([1-4])\s*(?:fy\s*)?(20\d{2}|\d{2})\b", question, re.I)
    if q:
        year = int(q[2])
        year = year + 2000 if year < 100 else year
        quarter = int(q[1])
        ends.append(
            f"{year if quarter == 4 else year - 1}-{['06-30', '09-30', '12-31', '03-31'][quarter - 1]}"
        )
    variants = []
    modifier = r"(?:adjusted|underlying|normalised|normalized|non gaap)"
    for key in metrics:
        if key.startswith("adjusted_") or key == "ebitda" and "adjusted_ebitda" in metrics:
            continue
        for alias in REGISTRY[key].aliases:
            a = re.escape(normalise(alias))
            if re.search(
                r"\b" + modifier + r"\s+" + a + r"\b|\b" + a + r"\s+" + modifier + r"\b", clean
            ):
                variants.append(key)
                break
    return FinancialIntent(
        tuple(metrics),
        basis,
        tuple(sorted(set(years))),
        "quarter"
        if q or re.search(r"\b(?:quarter\w*|qoq|q[1-4])\b", clean)
        else "year"
        if re.search(r"\b(?:annual|fy\s*\d+|year\w*)\b", clean)
        else None,
        "qoq" if "qoq" in clean else "yoy",
        tuple(sorted(set(ends))),
        tuple(sorted(set(variants))),
    )
