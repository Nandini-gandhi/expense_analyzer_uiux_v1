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


def clean_transactions(raw_path):
    """Read a single raw CSV and return cleaned DataFrame (not saved)."""
    print(f"\nReading: {raw_path}")
    df = pd.read_csv(raw_path)

    date_col = find_column(df, ["transaction date", "date", "posted date", "post date"])
    desc_col = find_column(df, ["description", "details", "memo"])
    amt_col = find_column(df, ["amount", "transaction amount", "value"])
    bank_cat_col = find_column(df, ["category"])

    if not date_col or not desc_col or not amt_col:
        raise ValueError("Could not find required columns (date, description, amount)")

    out = df.copy()
    out["date"] = out[date_col].apply(parse_date)
    out["description"] = out[desc_col].astype(str)
    out["amount_signed"] = pd.to_numeric(out[amt_col], errors="coerce")
    out = out.dropna(subset=["date", "description", "amount_signed"]).reset_index(drop=True)
    out["amount_spend"] = (-out["amount_signed"]).clip(lower=0)
    out["amount"] = out["amount_spend"]
    if bank_cat_col:
        out["bank_category"] = out[bank_cat_col].astype(str)
    out = out.sort_values("date").reset_index(drop=True)
    return out


def clean_all(raw_dir=RAW_DIR, save_path=os.path.join(CLEAN_DIR, "transactions_clean.csv")):
    """Clean all CSVs in raw_dir, add source column, concatenate, and save."""
    csvs = [f for f in os.listdir(raw_dir) if f.endswith(".csv")]
    if not csvs:
        raise FileNotFoundError("No CSV files found in data/raw/")

    frames = []
    for fname in csvs:
        path = os.path.join(raw_dir, fname)
        try:
            cleaned = clean_transactions(path)
            cleaned["source"] = os.path.splitext(fname)[0]
            frames.append(cleaned)
        except Exception as e:
            print(f"Skipping {fname}: {e}")

    if not frames:
        raise RuntimeError("No CSVs could be cleaned successfully")

    combined = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    combined.to_csv(save_path, index=False)
    print(f"Wrote combined cleaned file with {len(combined)} rows: {save_path}")
    return combined


def main():
    """Clean all CSVs in raw folder (multi-file support)."""
    clean_all()


if __name__ == "__main__":
    main()
