"""
Make and save week-5 charts to reports/plots
"""

import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

CLEAN_DIR = "data/clean"
REPORTS_DIR = "reports"
PLOTS_DIR = "plots"
BUDGET_MONTHLY = 2000

def _ensure_out() -> str:
    out = os.path.join(REPORTS_DIR, PLOTS_DIR)
    os.makedirs(out, exist_ok=True)
    return out

def _read_data(clean_dir: str = CLEAN_DIR) -> pd.DataFrame:
    path = os.path.join(clean_dir, "transactions_categorized.csv")
    if not os.path.exists(path):
        raise FileNotFoundError("run categorize first")
    df = pd.read_csv(path, parse_dates=["date"])
    if "amount_spend" not in df.columns:
        df["amount_spend"] = df.get("amount", 0.0)
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return df

def _pick_month(df: pd.DataFrame, month: str | None) -> str:
    return month or df["month"].sort_values().iloc[-1]

def plot_monthly_totals(df: pd.DataFrame, out_dir: str) -> str:
    s = df.groupby("month")["amount_spend"].sum().sort_index()
    fig, ax = plt.subplots(figsize=(9,4.5))
    s.plot(kind="bar", ax=ax)
    ax.set_title("Monthly Total Spend (expenses only)")
    ax.set_xlabel("Month"); ax.set_ylabel("Dollars")
    ax.grid(axis="y", linestyle=":", linewidth=0.5)
    fig.tight_layout()
    path = os.path.join(out_dir, "monthly_totals.png"); fig.savefig(path, dpi=150); plt.close(fig); return path

def plot_spend_by_category(df: pd.DataFrame, out_dir: str) -> str:
    s = df.groupby("category")["amount_spend"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(9,5))
    s.plot(kind="bar", ax=ax)
    ax.set_title("Spend by Category (expenses only)")
    ax.set_xlabel("Category"); ax.set_ylabel("Dollars")
    ax.grid(axis="y", linestyle=":", linewidth=0.5)
    fig.tight_layout()
    path = os.path.join(out_dir, "spend_by_category.png"); fig.savefig(path, dpi=150); plt.close(fig); return path

def plot_cumulative_vs_budget(df: pd.DataFrame, out_dir: str, month: str, budget: float) -> str:
    mdf = df[df["month"] == month].copy()
    if mdf.empty: raise ValueError(f"no data for {month}")
    daily = mdf.assign(day=mdf["date"].dt.date).groupby("day")["amount_spend"].sum().sort_index()
    cumu = daily.cumsum()
    fig, ax = plt.subplots(figsize=(9,4.5))
    cumu.plot(ax=ax, label="Cumulative spend")
    x = np.arange(1, len(cumu)+1)
    ax.plot(cumu.index, (budget/max(len(cumu),1))*x, label=f"Pro-rata budget (${budget:,.0f})")
    ax.set_title(f"Cumulative Spend vs Budget — {month}")
    ax.set_xlabel("Date"); ax.set_ylabel("Dollars"); ax.legend()
    ax.grid(True, linestyle=":", linewidth=0.5)
    fig.tight_layout()
    path = os.path.join(out_dir, f"cumulative_{month}.png"); fig.savefig(path, dpi=150); plt.close(fig); return path

def plot_category_month_heatmap(df: pd.DataFrame, out_dir: str) -> str:
    pivot = df.pivot_table(values="amount_spend", index="category", columns="month", aggfunc="sum", fill_value=0.0).sort_index()
    fig, ax = plt.subplots(figsize=(10,6))
    im = ax.imshow(pivot.values, aspect="auto", interpolation="nearest")
    ax.set_title("Category × Month Heatmap (expenses only)")
    ax.set_xlabel("Month"); ax.set_ylabel("Category")
    ax.set_xticks(np.arange(len(pivot.columns))); ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)));  ax.set_yticklabels(pivot.index)
    fig.colorbar(im, ax=ax, label="Dollars")
    fig.tight_layout()
    path = os.path.join(out_dir, "cat_by_month_heatmap.png"); fig.savefig(path, dpi=150); plt.close(fig); return path

def plot_top_merchants(df: pd.DataFrame, out_dir: str, top_n: int = 12) -> str:
    s = df.groupby("merchant")["amount_spend"].sum().sort_values(ascending=False).head(top_n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9,6))
    s.plot(kind="barh", ax=ax)
    ax.set_title(f"Top {top_n} Merchants by Spend (expenses only)")
    ax.set_xlabel("Dollars"); ax.set_ylabel("Merchant")
    ax.grid(axis="x", linestyle=":", linewidth=0.5)
    fig.tight_layout()
    path = os.path.join(out_dir, "top_merchants.png"); fig.savefig(path, dpi=150); plt.close(fig); return path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=None)
    args = parser.parse_args()

    out_dir = _ensure_out()
    df = _read_data(CLEAN_DIR)
    month = _pick_month(df, args.month)
    budget = float(BUDGET_MONTHLY)

    p1 = plot_monthly_totals(df, out_dir)
    p2 = plot_spend_by_category(df, out_dir)
    p3 = plot_cumulative_vs_budget(df, out_dir, month, budget)
    p4 = plot_category_month_heatmap(df, out_dir)
    p5 = plot_top_merchants(df, out_dir)

    print("saved charts:")
    for p in [p1,p2,p3,p4,p5]:
        print(" -", p)

if __name__ == "__main__":
    main()
