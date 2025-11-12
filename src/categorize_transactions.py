"""Categorize transactions based on keywords and user rules."""

import os
import re
import json
import hashlib
import pandas as pd
from rapidfuzz import process, fuzz

CLEAN_DIR = "data/clean"
OVERRIDES_JSON = "data/config/overrides.json"
ONE_OFF_CSV = "data/config/one_off_overrides.csv"

# keyword to category mapping
KEYWORD_RULES = {
    "whole foods": "Groceries", "trader joe": "Groceries", "aldi": "Groceries",
    "kroger": "Groceries", "instacart": "Groceries",
    "starbucks": "Dining", "dunkin": "Dining", "chipotle": "Dining",
    "ubereats": "Dining", "doordash": "Dining",
    "uber": "Travel", "lyft": "Travel", "shell": "Travel",
    "chevron": "Travel", "exxon": "Travel", "bp": "Travel",
    "amazon": "Shopping", "target": "Shopping", "walmart": "Shopping", "ikea": "Shopping",
    "netflix": "Entertainment", "spotify": "Entertainment", "hulu": "Entertainment",
}

# bank provided categories map
BANK_CAT_MAP = {
    "food  drink": "Dining", "restaurants": "Dining", "dining out": "Dining", "coffee": "Dining",
    "groceries": "Groceries", "supermarkets": "Groceries",
    "bills  utilities": "Bills", "utilities": "Bills", "internet": "Bills", "mobile": "Bills",
    "transportation": "Travel", "transport": "Travel", "gas": "Travel", "fuel": "Travel", "rideshare": "Travel",
    "entertainment": "Entertainment", "subscriptions": "Entertainment", "streaming": "Entertainment",
    "shopping": "Shopping", "retail": "Shopping", "electronics": "Shopping",
    "health  wellness": "Health", "health": "Health", "pharmacy": "Health",
    "home": "Home", "rent": "Home",
    "education": "Education", "professional services": "Bills", "personal": "Personal",
    "gifts  donations": "Shopping", "finance": "Finance", "fees": "Finance",
    "travel": "Travel",
}

BANK_UNKNOWN = {"", "nan", "none", "uncategorized", "unknown", "other", "misc", "miscellaneous"}


def clean_string(s):
    """Make string lowercase and remove special characters."""
    s = str(s).strip().lower()
    s = re.sub(r"[\s\-_/]+", " ", s)
    s = re.sub(r"[^\w\s+]", "", s)
    return s


def get_merchant_name(desc):
    """Try to extract merchant from description."""
    words_to_skip = {"purchase", "pos", "card", "debit", "credit", "sale", "online", "payment", "venmo", "zelle"}
    tokens = [t for t in desc.split() if t not in words_to_skip]
    
    # remove numbers
    tokens_clean = []
    for t in tokens:
        clean_t = re.sub(r"\d+", "", t)
        tokens_clean.append(clean_t)
    
    result = " ".join(tokens_clean).strip()
    # just take first 3 words
    parts = result.split()[:3]
    return " ".join(parts)


def clean_bank_category(bank_cat):
    """Clean bank category."""
    if pd.isna(bank_cat):
        return ""
    
    cleaned = clean_string(bank_cat)
    if cleaned in BANK_UNKNOWN:
        return ""
    
    if cleaned in BANK_CAT_MAP:
        return BANK_CAT_MAP[cleaned]
    
    return str(bank_cat).strip()


def match_keyword(text):
    """Check if text matches any keyword rule."""
    text_lower = text.lower()
    for keyword, category in KEYWORD_RULES.items():
        if keyword in text_lower:
            return category
    return None


def fuzzy_match(text):
    """Try fuzzy matching against keywords."""
    keywords = list(KEYWORD_RULES.keys())
    if not keywords:
        return None
    
    match = process.extractOne(text, keywords, scorer=fuzz.partial_ratio)
    if match is None:
        return None
    
    keyword, score, _ = match
    if score >= 90:
        return KEYWORD_RULES[keyword]
    return None


def make_txn_id(row):
    """Create unique ID for transaction."""
    date_str = pd.to_datetime(row["date"]).strftime("%Y-%m-%d")
    amt_str = f"{float(row['amount_signed']):.2f}"
    desc = clean_string(row.get("description", ""))
    
    combined = f"{date_str}|{amt_str}|{desc}"
    hashed = hashlib.sha1(combined.encode("utf-8")).hexdigest()
    return hashed


def load_overrides():
    """Load merchant override rules from JSON file."""
    if not os.path.exists(OVERRIDES_JSON):
        os.makedirs(os.path.dirname(OVERRIDES_JSON), exist_ok=True)
        with open(OVERRIDES_JSON, "w") as f:
            json.dump({}, f)
        return {}
    
    try:
        with open(OVERRIDES_JSON, "r") as f:
            data = json.load(f)
        
        # canonicalize keys when loading
        result = {}
        for k, v in data.items():
            clean_k = clean_string(k)
            result[clean_k] = v
        return result
    except:
        return {}


def load_one_off():
    """Load one-time overrides from CSV."""
    if not os.path.exists(ONE_OFF_CSV):
        os.makedirs(os.path.dirname(ONE_OFF_CSV), exist_ok=True)
        pd.DataFrame({"txn_id": [], "category": []}).to_csv(ONE_OFF_CSV, index=False)
        return {}
    
    try:
        df = pd.read_csv(ONE_OFF_CSV)
        result = {}
        for _, row in df.iterrows():
            result[str(row["txn_id"])] = str(row["category"])
        return result
    except:
        return {}


def check_merchant_override(merchant, override_map):
    """Check if merchant has an override rule."""
    if merchant in override_map:
        return override_map[merchant]
    
    # check if merchant contains override key
    for key, cat in override_map.items():
        if key and key in merchant:
            return cat
    
    return None


def decide_category(row, one_off_map, merchant_map):
    """Decide what category this transaction should be."""
    txn_id = row["txn_id"]
    
    # check if it's a credit (positive amount) - exclude these
    try:
        amt = float(row.get("amount_signed") or 0)
        if amt > 0:
            return "EXCLUDE", "credit"
    except:
        pass
    
    # check one-off overrides first
    if txn_id in one_off_map:
        return one_off_map[txn_id], "one_off"
    
    # check merchant override
    merchant = row["merchant"]
    hit = check_merchant_override(merchant, merchant_map)
    if hit:
        return hit, "merchant"
    
    # check bank category
    bank_cat = row.get("bank_category_clean", "")
    if bank_cat:
        if str(bank_cat).lower() == "health":
            return "Groceries", "bank"
        return bank_cat, "bank"
    
    # try keyword match
    text = f"{row['description_norm']} {row['merchant']}".strip()
    cat = match_keyword(text)
    if cat:
        return cat, "rule"
    
    # try fuzzy match
    cat = fuzzy_match(text)
    if cat:
        return cat, "fuzzy"
    
    # default
    return "Other", "other"


def categorize(df):
    """Add category to transactions."""
    # need these columns
    needed = {"date", "description", "amount_spend", "amount_signed"}
    if not needed.issubset(df.columns):
        raise ValueError("missing required columns - run clean first")
    
    out = df.copy()
    
    # normalize descriptions
    out["description_norm"] = out["description"].astype(str).apply(clean_string)
    
    # extract merchant
    out["merchant"] = out["description_norm"].apply(get_merchant_name)
    
    # clean bank category
    if "bank_category" in out.columns:
        out["bank_category_clean"] = out["bank_category"].apply(clean_bank_category)
    else:
        out["bank_category_clean"] = ""
    
    # create transaction id
    out["txn_id"] = out.apply(make_txn_id, axis=1)
    
    # load overrides
    merchant_map = load_overrides()
    one_off_map = load_one_off()
    
    # decide category for each row
    categories = []
    sources = []
    for _, row in out.iterrows():
        cat, source = decide_category(row, one_off_map, merchant_map)
        categories.append(cat)
        sources.append(source)
    
    out["category"] = categories
    out["category_source"] = sources
    
    # reorder columns - put important ones first
    first_cols = [
        "date", "description", "merchant", "txn_id",
        "amount_signed", "amount_spend", "category", "category_source",
        "bank_category", "bank_category_clean", "description_norm"
    ]
    other_cols = [c for c in out.columns if c not in first_cols]
    final_cols = first_cols + other_cols
    
    return out[final_cols]


def main():
    """Run categorization on clean data."""
    clean_path = os.path.join(CLEAN_DIR, "transactions_clean.csv")
    cat_path = os.path.join(CLEAN_DIR, "transactions_categorized.csv")
    
    df = pd.read_csv(clean_path, parse_dates=["date"])
    df_cat = categorize(df)
    df_cat.to_csv(cat_path, index=False)
    print(f"Categorized {len(df_cat)} transactions")


if __name__ == "__main__":
    main()
