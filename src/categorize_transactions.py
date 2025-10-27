"""
Bank category (normalized), fallback to small keyword list + fuzzy
Write categorized csv and a short text summary
"""

import os
import re
import pandas as pd
from rapidfuzz import process, fuzz

CLEAN_DIR = "data/clean"
REPORTS_DIR = "reports"

# short keyword fallback
KEYWORD_RULES = {
    # groceries
    "whole foods": "Groceries",
    "trader joe": "Groceries",
    "aldi": "Groceries",
    "kroger": "Groceries",
    "instacart": "Groceries",
    # dining / coffee
    "starbucks": "Dining",
    "dunkin": "Dining",
    "chipotle": "Dining",
    "ubereats": "Dining",
    "doordash": "Dining",
    # transport
    "uber": "Transport",
    "lyft": "Transport",
    "shell": "Transport",
    "chevron": "Transport",
    "exxon": "Transport",
    "bp": "Transport",
    # shopping
    "amazon": "Shopping",
    "target": "Shopping",
    "walmart": "Shopping",
    "ikea": "Shopping",
    # entertainment
    "netflix": "Entertainment",
    "spotify": "Entertainment",
    "hulu": "Entertainment",
}
REGEX_RULES = {}  # not used now

# fuzzy settings
FUZZY_ON = True
FUZZY_THRESH = 90
FUZZY_SCORER = fuzz.partial_ratio

# map bank labels to short names
BANK_CAT_MAP = {
    "food & drink": "Dining", "restaurants": "Dining", "dining out": "Dining", "coffee": "Dining",
    "groceries": "Groceries", "supermarkets": "Groceries",
    "bills & utilities": "Bills", "utilities": "Bills", "internet": "Bills", "mobile": "Bills",
    "transportation": "Transport", "transport": "Transport", "gas": "Transport", "fuel": "Transport", "rideshare": "Transport",
    "entertainment": "Entertainment", "subscriptions": "Entertainment", "streaming": "Entertainment",
    "shopping": "Shopping", "retail": "Shopping", "electronics": "Shopping",
    "health & wellness": "Health", "health": "Health", "pharmacy": "Health",
    "home": "Home", "rent": "Home",
    "education": "Education", "professional services": "Services", "personal": "Personal",
    "gifts & donations": "Gifts", "finance": "Finance", "fees": "Finance",
    "travel": "Travel",
}
BANK_UNKNOWN = {"", "nan", "none", "uncategorized", "unknown", "other", "misc", "miscellaneous"}

def _canon(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"[\s\-_/]+", " ", s)
    s = re.sub(r"[^\w\s+]", "", s)
    return s

def _guess_merchant(desc_norm: str) -> str:
    bad = {"purchase","pos","card","debit","credit","sale","online","payment","venmo","zelle"}
    toks = [t for t in desc_norm.split() if t not in bad]
    return " ".join(toks[:3])

def _clean_bank(ser: pd.Series) -> pd.Series:
    def f(x):
        if pd.isna(x): return ""
        raw = _canon(x)
        if raw in BANK_UNKNOWN: return ""
        return BANK_CAT_MAP.get(raw, str(x).strip())
    return ser.apply(f)

def _apply_exact(hay: str) -> str | None:
    for pat, cat in REGEX_RULES.items():
        if re.search(pat, hay, flags=re.IGNORECASE):
            return cat
    for kw, cat in KEYWORD_RULES.items():
        if kw in hay:
            return cat
    return None

def _apply_fuzzy(hay: str) -> str | None:
    if not FUZZY_ON or not KEYWORD_RULES:
        return None
    keys = list(KEYWORD_RULES.keys())
    match = process.extractOne(hay, keys, scorer=FUZZY_SCORER)
    if not match: return None
    kw, score, _ = match
    return KEYWORD_RULES[kw] if score >= FUZZY_THRESH else None

def _choose_cat(row) -> str:
    bank_cat = row.get("bank_category_clean", "")
    if bank_cat:
        return bank_cat
    hay = f"{row['description_norm']} {row['merchant']}".strip()
    return _apply_exact(hay) or _apply_fuzzy(hay) or "Other"

def categorize(df: pd.DataFrame) -> pd.DataFrame:
    need = {"date", "description", "amount_spend", "amount_signed"}
    if not need.issubset(df.columns):
        raise ValueError("run clean first")

    out = df.copy()
    out["description_norm"] = out["description"].astype(str).apply(_canon)
    out["merchant"] = out["description_norm"].apply(_guess_merchant)

    if "bank_category" in out.columns:
        out["bank_category_clean"] = _clean_bank(out["bank_category"])
    else:
        out["bank_category_clean"] = ""

    out["category"] = out.apply(_choose_cat, axis=1)

    front = [
        "date","description","merchant",
        "amount_signed","amount_spend","category",
        "bank_category","bank_category_clean","description_norm"
    ]
    cols = front + [c for c in out.columns if c not in front]
    return out[cols]

def _summ(df: pd.DataFrame) -> str:
    total_rows = len(df)
    total_spend = float(df["amount_spend"].sum())
    by_cat = (
        df.groupby("category", dropna=False)["amount_spend"]
          .agg(count="count", dollars="sum")
          .sort_values("dollars", ascending=False)
    )
    lines = [f"Total transactions: {total_rows}", f"Total spend (expenses only): ${total_spend:,.2f}", "By category:"]
    for cat, row in by_cat.iterrows():
        pct = 100.0 * row["dollars"] / total_spend if total_spend else 0.0
        lines.append(f"  - {cat}: {int(row['count'])} txns, ${row['dollars']:,.2f} ({pct:.1f}% of spend)")
    monthly = df.assign(month=df["date"].dt.to_period("M").astype(str)).groupby("month")["amount_spend"].sum().sort_index()
    lines.append("Monthly total spend (expenses only):")
    for m, v in monthly.items():
        lines.append(f"  - {m}: ${v:,.2f}")
    return "\n".join(lines)

def main():
    src = os.path.join(CLEAN_DIR, "transactions_clean.csv")
    if not os.path.exists(src):
        raise FileNotFoundError("missing data/clean/transactions_clean.csv")
    df = pd.read_csv(src, parse_dates=["date"])

    out = categorize(df)

    os.makedirs(CLEAN_DIR, exist_ok=True)
    out_path = os.path.join(CLEAN_DIR, "transactions_categorized.csv")
    out.to_csv(out_path, index=False)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    txt = _summ(out)
    with open(os.path.join(REPORTS_DIR, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(txt)

    print(f"wrote: {out_path}")
    print(txt)

if __name__ == "__main__":
    main()
