"""Clean and standardize raw bank CSV files."""

import os
import pandas as pd
from dateutil import parser

RAW_DIR = "data/raw"
CLEAN_DIR = "data/clean"


def find_column(df, possible_names):
    """Find a column by checking multiple possible names (case-insensitive)."""
    col_lower = {c.lower(): c for c in df.columns}
    
    for name in possible_names:
        if name.lower() in col_lower:
            return col_lower[name.lower()]
    
    return None


def parse_date(value):
    """Try to parse a date string."""
    if pd.isna(value):
        return pd.NaT
    
    try:
        result = parser.parse(str(value), fuzzy=True)
        return result
    except:
        return pd.NaT


def clean_transactions(raw_path, save_path):
    """Read raw CSV and clean it."""
    print(f"\nReading: {raw_path}")
    df = pd.read_csv(raw_path)
    
    # find columns
    date_col = find_column(df, ["transaction date", "date", "posted date", "post date"])
    desc_col = find_column(df, ["description", "details", "memo"])
    amt_col = find_column(df, ["amount", "transaction amount", "value"])
    bank_cat_col = find_column(df, ["category"])
    
    if not date_col or not desc_col or not amt_col:
        raise ValueError("Could not find required columns (date, description, amount)")
    
    out = df.copy()
    
    # parse dates
    out["date"] = out[date_col].apply(parse_date)
    
    # description
    out["description"] = out[desc_col].astype(str)
    
    # amount - convert to numeric
    out["amount_signed"] = pd.to_numeric(out[amt_col], errors="coerce")
    
    # remove rows with missing data
    out = out.dropna(subset=["date", "description", "amount_signed"]).reset_index(drop=True)
    
    # calculate spend amount (positive)
    out["amount_spend"] = (-out["amount_signed"]).clip(lower=0)
    out["amount"] = out["amount_spend"]
    
    # include bank category if present
    if bank_cat_col:
        out["bank_category"] = out[bank_cat_col].astype(str)
    
    # sort by date
    out = out.sort_values("date").reset_index(drop=True)
    
    # save
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    out.to_csv(save_path, index=False)
    print(f"Wrote: {save_path}")
    
    return out


def main():
    """Find CSV in raw folder and clean it."""
    csvs = [f for f in os.listdir(RAW_DIR) if f.endswith(".csv")]
    if not csvs:
        raise FileNotFoundError("No CSV files found in data/raw/")
    
    raw_path = os.path.join(RAW_DIR, csvs[0])
    save_path = os.path.join(CLEAN_DIR, "transactions_clean.csv")
    clean_transactions(raw_path, save_path)


if __name__ == "__main__":
    main()
