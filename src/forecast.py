"""Forecast spending based on historical data."""

import pandas as pd
import numpy as np


def remove_outliers(data, multiplier=1.5):
    """Remove outlier values using IQR method."""
    if len(data) < 4:
        return data
    
    q1 = data.quantile(0.25)
    q3 = data.quantile(0.75)
    iqr = q3 - q1
    
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    
    filtered = data[(data >= lower) & (data <= upper)]
    return filtered


def forecast_by_category(df, months_lookback=3):
    """Forecast spending by category."""
    if df.empty:
        return pd.DataFrame()
    
    # exclude transfers
    df = df[df["category"] != "Transfer"].copy()
    
    df["date"] = pd.to_datetime(df["date"])
    df["year_month"] = df["date"].dt.to_period("M")
    
    # get recent months
    unique_months = sorted(df["year_month"].unique())
    if len(unique_months) < 1:
        return pd.DataFrame()
    
    recent_months = unique_months[-months_lookback:]
    df_recent = df[df["year_month"].isin(recent_months)].copy()
    
    if df_recent.empty:
        return pd.DataFrame()
    
    # group by category and month
    monthly_by_cat = (
        df_recent.groupby(["category", "year_month"])["amount_spend"]
        .sum()
        .reset_index()
        .rename(columns={"amount_spend": "monthly_total"})
    )
    
    # calculate stats for each category
    results = []
    for cat in monthly_by_cat["category"].unique():
        cat_data = monthly_by_cat[monthly_by_cat["category"] == cat]["monthly_total"]
        
        # remove outliers
        cat_clean = remove_outliers(cat_data, multiplier=1.5)
        if len(cat_clean) == 0:
            cat_clean = cat_data
        
        avg = float(cat_clean.mean())
        std = float(cat_clean.std()) if len(cat_clean) > 1 else 0.0
        min_val = float(cat_clean.min())
        max_val = float(cat_clean.max())
        num = len(cat_clean)
        
        results.append({
            "category": cat,
            "avg_spend": avg,
            "std_dev": std,
            "min_spend": min_val,
            "max_spend": max_val,
            "num_months": num,
            "confidence_low": avg - std,
            "confidence_high": avg + std,
        })
    
    result_df = pd.DataFrame(results).sort_values("avg_spend", ascending=False)
    return result_df


def forecast_total_spend(df, months_lookback=3):
    """Forecast total spending."""
    if df.empty:
        return {}
    
    # exclude transfers
    df = df[df["category"] != "Transfer"].copy()
    
    df["date"] = pd.to_datetime(df["date"])
    df["year_month"] = df["date"].dt.to_period("M")
    
    # get monthly totals
    monthly_totals = (
        df.groupby("year_month")["amount_spend"]
        .sum()
        .reset_index()
        .rename(columns={"amount_spend": "monthly_total"})
    )
    
    monthly_totals = monthly_totals.tail(months_lookback)
    
    if len(monthly_totals) == 0:
        return {}
    
    # remove outliers
    totals_clean = remove_outliers(monthly_totals["monthly_total"], multiplier=1.5)
    if len(totals_clean) == 0:
        totals_clean = monthly_totals["monthly_total"]
    
    avg = float(totals_clean.mean())
    std = float(totals_clean.std()) if len(totals_clean) > 1 else 0.0
    
    return {
        "avg_spend": avg,
        "std_dev": std,
        "min_spend": float(totals_clean.min()),
        "max_spend": float(totals_clean.max()),
        "confidence_low": avg - std,
        "confidence_high": avg + std,
        "num_months": len(totals_clean),
    }
