"""
read raw bank csv, standardize and save clean csv.

simple rules:
- keep bank's signed amount as amount_signed (negatives are expenses)
- make amount_spend = positive dollars for expenses only (credits become 0)
- pick a date column, also keep post_date if present
"""

import os
import pandas as pd
from dateutil import parser

RAW_DIR = "data/raw"
CLEAN_DIR = "data/clean"

POSSIBLE_DATE = ["transaction date", "date", "posted date", "post date"]
POSSIBLE_DESC = ["description", "details", "memo"]
POSSIBLE_AMT  = ["amount", "transaction amount", "value"]

def _find_col(df: pd.DataFrame, names: list[str]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None

def _parse_date(x):
    if pd.isna(x):
        return pd.NaT
    try:
        return parser.parse(str(x), fuzzy=True)
    except Exception:
        return pd.NaT

def clean_transactions(raw_path: str, save_path: str) -> pd.DataFrame:
    print(f"\nreading: {raw_path}")
    df = pd.read_csv(raw_path)

    date_col = _find_col(df, ["transaction date"]) or _find_col(df, POSSIBLE_DATE)
    post_col = _find_col(df, ["post date", "posted date"])
    desc_col = _find_col(df, POSSIBLE_DESC)
    amt_col  = _find_col(df, POSSIBLE_AMT)
    bank_cat = _find_col(df, ["category"])

    if not all([date_col, desc_col, amt_col]):
        raise ValueError("need date/description/amount columns")

    out = df.copy()

    out["date"] = out[date_col].apply(_parse_date)
    if post_col and post_col != date_col:
        out["post_date"] = out[post_col].apply(_parse_date)

    out["description"] = out[desc_col].astype(str)
    out["amount_signed"] = pd.to_numeric(out[amt_col], errors="coerce")

    out = out.dropna(subset=["date", "description", "amount_signed"]).reset_index(drop=True)

    # expenses as positive dollars
    out["amount_spend"] = (-out["amount_signed"]).clip(lower=0)
    out["amount"] = out["amount_spend"]  

    if bank_cat:
        out["bank_category"] = out[bank_cat].astype(str)

    out = out.sort_values("date").reset_index(drop=True)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    out.to_csv(save_path, index=False)
    print(f"wrote: {save_path}")
    return out

def main():
    csvs = [f for f in os.listdir(RAW_DIR) if f.endswith(".csv")]
    if not csvs:
        raise FileNotFoundError("put a csv in data/raw/")
    raw_path = os.path.join(RAW_DIR, csvs[0])
    save_path = os.path.join(CLEAN_DIR, "transactions_clean.csv")
    clean_transactions(raw_path, save_path)

if __name__ == "__main__":
    main()
