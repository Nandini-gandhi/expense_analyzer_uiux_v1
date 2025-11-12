"""Command-line runner for data pipeline: clean, categorize, and query transactions."""

import argparse
import os
import pandas as pd
from src.clean_transactions import main as do_clean
from src.categorize_transactions import main as do_categorize


def _print_top(args):
    """Query and display top transactions with optional filters."""
    path = os.path.join("data", "clean", "transactions_categorized.csv")
    if not os.path.exists(path):
        raise FileNotFoundError("run: python run.py categorize")
    df = pd.read_csv(path, parse_dates=["date"])

    if args.category:
        df = df[df["category"].str.lower() == args.category.lower()]
    if args.start:
        df = df[df["date"] >= pd.to_datetime(args.start)]
    if args.end:
        df = df[df["date"] <= pd.to_datetime(args.end)]
    if args.min is not None:
        df = df[df["amount_spend"] >= float(args.min)]
    if args.max is not None:
        df = df[df["amount_spend"] <= float(args.max)]
    if args.search:
        s = args.search.lower()
        df = df[df["description"].str.lower().str.contains(s) | df["merchant"].str.lower().str.contains(s)]

    df = df.sort_values(["amount_spend", "date"], ascending=[False, False]).head(args.limit)
    cols = ["date", "merchant", "category", "amount_spend", "category_source", "description"]
    print(df[cols].to_string(index=False))


def main():
    """Parse arguments and run pipeline command."""
    p = argparse.ArgumentParser(description="expense-coach runner")
    p.add_argument("cmd", choices=["clean", "categorize", "top"])
    p.add_argument("--category", help="Filter by category")
    p.add_argument("--limit", type=int, default=10, help="Number of results")
    p.add_argument("--start", help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", help="End date (YYYY-MM-DD)")
    p.add_argument("--min", type=float, help="Minimum amount")
    p.add_argument("--max", type=float, help="Maximum amount")
    p.add_argument("--search", help="Search merchant/description")

    args = p.parse_args()

    if args.cmd == "clean":
        do_clean()
    elif args.cmd == "categorize":
        do_categorize()
    elif args.cmd == "top":
        _print_top(args)


if __name__ == "__main__":
    main()
