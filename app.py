"""Clean, intuitive expense tracking and forecasting app with graphs."""

import os
import json
import calendar
import re
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src.plot_charts import _read_data, CLEAN_DIR
from src.categorize_transactions import categorize
from src.forecast import forecast_by_category, forecast_total_spend

OVERRIDES_JSON = "data/config/overrides.json"
ONE_OFF_CSV = "data/config/one_off_overrides.csv"

st.set_page_config(page_title="Expense Analyzer", layout="wide")
st.title("💰 Expense Analyzer")

#  matplotlib style
plt.style.use("seaborn-v0_8-darkgrid")


def normalize_merchant(merchant_name):
    """Normalize merchant name for storage."""
    m = str(merchant_name).strip().lower()
    m = re.sub(r"[\s\-_/]+", " ", m)
    m = re.sub(r"[^\w\s+]", "", m)
    return m


def _load_clean_df():
    """Load cleaned transactions."""
    path = os.path.join(CLEAN_DIR, "transactions_clean.csv")
    if not os.path.exists(path):
        st.error("Missing data/clean/transactions_clean.csv. Run `python run.py clean` first.")
        st.stop()
    df = pd.read_csv(path, parse_dates=["date"])
    return df


def _load_cat_df():
    """Load categorized transactions."""
    return _read_data(CLEAN_DIR)


def _save_cat_df(df_cat: pd.DataFrame):
    """Save categorized transactions."""
    out_path = os.path.join(CLEAN_DIR, "transactions_categorized.csv")
    df_cat.to_csv(out_path, index=False)
    return out_path


def _load_overrides():
    """Load merchant override rules."""
    if not os.path.exists(OVERRIDES_JSON):
        os.makedirs(os.path.dirname(OVERRIDES_JSON), exist_ok=True)
        with open(OVERRIDES_JSON, "w") as f:
            json.dump({}, f)
        return {}
    
    try:
        with open(OVERRIDES_JSON, "r") as f:
            data = json.load(f)
        return data
    except:
        return {}


def _save_overrides(d):
    """Save merchant override rules."""
    os.makedirs(os.path.dirname(OVERRIDES_JSON), exist_ok=True)
    with open(OVERRIDES_JSON, "w") as f:
        json.dump(d, f, indent=2)


def _load_one_off_map():
    """Load one-time transaction overrides."""
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


def _save_one_off_map(m):
    """Save one-time transaction overrides."""
    rows = [{"txn_id": k, "category": v} for k, v in m.items()]
    pd.DataFrame(rows).to_csv(ONE_OFF_CSV, index=False)


def _recompute_and_refresh():
    """Re-run categorization and refresh state."""
    clean_df = _load_clean_df()
    df_cat = categorize(clean_df)
    _save_cat_df(df_cat)
    st.session_state["df"] = df_cat
    return df_cat


if "df" not in st.session_state:
    try:
        st.session_state["df"] = _load_cat_df()
    except Exception as e:
        print(f"Error loading: {e}")
        _recompute_and_refresh()

if "mode" not in st.session_state:
    st.session_state["mode"] = "home"

if "selected_category" not in st.session_state:
    st.session_state["selected_category"] = None

if "selected_date_range" not in st.session_state:
    st.session_state["selected_date_range"] = None

df = st.session_state["df"]
all_categories = sorted([c for c in df["category"].dropna().unique() if c != "EXCLUDE"])

mode = st.session_state["mode"]
selected_category = st.session_state["selected_category"]
selected_date_range = st.session_state["selected_date_range"]

min_d = df["date"].min().date()
max_d = df["date"].max().date()


def _get_default_date_range():
    """Get current month date range. If no transactions, go back one month."""
    today = pd.Timestamp.today()
    month_start = today.replace(day=1).date()
    _, last_day = calendar.monthrange(today.year, today.month)
    month_end = today.replace(day=last_day).date()
    
    current_month_data = df[(df["date"].dt.date >= month_start) & (df["date"].dt.date <= month_end)]
    
    if len(current_month_data) > 0:
        return month_start, month_end
    
    if today.month == 1:
        prev_month = today.replace(year=today.year - 1, month=12)
    else:
        prev_month = today.replace(month=today.month - 1)
    
    prev_month_start = prev_month.replace(day=1).date()
    _, last_day = calendar.monthrange(prev_month.year, prev_month.month)
    prev_month_end = prev_month.replace(day=last_day).date()
    
    return prev_month_start, prev_month_end


if selected_date_range is None:
    st.session_state["selected_date_range"] = _get_default_date_range()
    selected_date_range = st.session_state["selected_date_range"]


if mode == "home":
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Your Spending")
    
    with col2:
        if st.button("⚙️ Settings", key="settings_btn"):
            st.session_state["mode"] = "settings"
            st.rerun()
    
    st.markdown("---")
    
    start_d, end_d = selected_date_range
    
    with st.sidebar:
        st.subheader("📅 Date Range")
        date_range = st.date_input("Pick dates", value=(start_d, end_d), label_visibility="collapsed")
        if len(date_range) == 2:
            start_d, end_d = date_range[0], date_range[1]
            st.session_state["selected_date_range"] = (start_d, end_d)
        
        st.subheader("🔍 Merchant Search")
        merchant_search = st.text_input("Search merchants:", "", key="home_merchant_search")
        
        if st.button("🔮 View Forecast", key="forecast_btn"):
            st.session_state["mode"] = "forecast"
            st.rerun()
    
    start_d = pd.to_datetime(start_d)
    end_d = pd.to_datetime(end_d)
    
    filtered_df = df[(df["date"] >= start_d) & (df["date"] <= end_d) & (df["category"] != "EXCLUDE")].copy()
    
    total_spend = filtered_df["amount_spend"].sum()
    total_txns = len(filtered_df)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Spend", f"${total_spend:,.2f}")
    col2.metric("Transactions", f"{total_txns:,}")
    col3.metric("Avg/Txn", f"${total_spend/max(total_txns, 1):,.2f}")
    
    st.markdown("---")
    
    # Merchant search results
    if merchant_search.strip():
        search_lower = merchant_search.lower()
        merchant_df = filtered_df[
            filtered_df["merchant"].str.lower().str.contains(search_lower, na=False)
        ].copy()
        
        if len(merchant_df) > 0:
            st.subheader("🔍 Search Results")
            merchant_total = merchant_df["amount_spend"].sum()
            merchant_count = merchant_df["amount_spend"].count()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Matching Spend", f"${merchant_total:,.2f}")
            col2.metric("Matching Count", f"{merchant_count}")
            col3.metric("Avg Amount", f"${merchant_total/max(merchant_count, 1):,.2f}")
            
            st.markdown("**Transactions:**")
            display = merchant_df[["date", "merchant", "amount_spend", "category", "description"]].copy()
            display = display.sort_values("amount_spend", ascending=False)
            display.columns = ["Date", "Merchant", "Amount", "Category", "Description"]
            display["Amount"] = display["Amount"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.info("No merchants match your search.")
    else:
        # Category breakdown
        cat_summary = (
            filtered_df.groupby("category")
            .agg(total=("amount_spend", "sum"), count=("amount_spend", "count"))
            .sort_values("total", ascending=False)
            .reset_index()
        )
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("💰 By Category")
            for _, row in cat_summary.iterrows():
                cat = row["category"]
                amt = row["total"]
                pct = 100 * amt / max(total_spend, 1)
                
                if st.button(f"**{cat}** · ${amt:,.0f} ({pct:.0f}%)", key=f"cat_{cat}"):
                    st.session_state["mode"] = "category_detail"
                    st.session_state["selected_category"] = cat
                    st.rerun()
        
        with col2:
            st.subheader("📊 Breakdown")
            fig, ax = plt.subplots(figsize=(8, 6))
            colors = plt.cm.Set3(range(len(cat_summary)))
            ax.pie(cat_summary["total"], labels=cat_summary["category"], autopct="%1.1f%%", 
                   colors=colors, startangle=90)
            ax.set_title("Spending by Category", fontsize=14, fontweight="bold")
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
        
        # Trend chart
        st.subheader("📈 Spending Trend")
        daily_spend = filtered_df.groupby(filtered_df["date"].dt.date)["amount_spend"].sum().reset_index()
        daily_spend.columns = ["date", "amount"]
        
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(daily_spend["date"], daily_spend["amount"], marker="o", linewidth=2, markersize=4, color="#1f77b4")
        ax.fill_between(daily_spend["date"], daily_spend["amount"], alpha=0.3, color="#1f77b4")
        ax.set_xlabel("Date", fontweight="bold")
        ax.set_ylabel("Daily Spend ($)", fontweight="bold")
        ax.set_title("Daily Spending Over Time", fontsize=14, fontweight="bold")
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)


elif mode == "category_detail":
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header(f"📊 {selected_category}")
    
    with col2:
        if st.button("← Back", key="back_btn"):
            st.session_state["mode"] = "home"
            st.session_state["selected_category"] = None
            st.rerun()
    
    st.markdown("---")
    
    start_d, end_d = selected_date_range
    
    with st.sidebar:
        st.subheader("📅 Date Range")
        date_range = st.date_input("Pick dates", value=(start_d, end_d), label_visibility="collapsed", key="detail_dates")
        if len(date_range) == 2:
            start_d, end_d = date_range[0], date_range[1]
            st.session_state["selected_date_range"] = (start_d, end_d)
        
        st.subheader("🔍 Filter & Sort")
        sort_by = st.radio("Sort by:", ["Amount (High→Low)", "Date (Newest)", "Transaction Count"], 
                          horizontal=False, key="sort_radio")
        min_amt = st.number_input("Min ($)", value=0.0, step=10.0, key="detail_min")
        max_amt = st.number_input("Max ($)", value=10000.0, step=100.0, key="detail_max")
        search = st.text_input("Merchant/Description", key="detail_search")
    
    start_d = pd.to_datetime(start_d)
    end_d = pd.to_datetime(end_d)
    
    cat_df = df[
        (df["category"] == selected_category) &
        (df["date"] >= start_d) & (df["date"] <= end_d) &
        (df["amount_spend"] >= min_amt) & (df["amount_spend"] <= max_amt)
    ].copy()
    
    if search.strip():
        s = search.lower()
        cat_df = cat_df[
            cat_df["merchant"].str.lower().str.contains(s, na=False) |
            cat_df["description"].str.lower().str.contains(s, na=False)
        ]
    
    # Apply sort
    if sort_by == "Amount (High→Low)":
        cat_df = cat_df.sort_values("amount_spend", ascending=False)
    elif sort_by == "Date (Newest)":
        cat_df = cat_df.sort_values("date", ascending=False)
    elif sort_by == "Transaction Count":
        merchant_counts = cat_df.groupby("merchant").size()
        cat_df["merchant_count"] = cat_df["merchant"].map(merchant_counts)
        cat_df = cat_df.sort_values("merchant_count", ascending=False)
    
    cat_total = cat_df["amount_spend"].sum()
    cat_count = len(cat_df)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", f"${cat_total:,.0f}")
    col2.metric("Transactions", f"{cat_count}")
    col3.metric("Average", f"${cat_total / max(cat_count, 1):,.0f}")
    col4.metric("Unique Merchants", f"{cat_df['merchant'].nunique()}")
    
    if len(cat_df) > 0:
        st.markdown("---")
        
        st.subheader("📋 Transactions")
        display = cat_df[["date", "merchant", "amount_spend", "description"]].copy()
        display.columns = ["Date", "Merchant", "Amount", "Description"]
        display["Amount"] = display["Amount"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(display, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("📊 Charts")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("💳 Top Merchants")
            top_merchants = cat_df.groupby("merchant")["amount_spend"].agg(["sum", "count"]).sort_values("sum", ascending=False).head(10)
            
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.barh(range(len(top_merchants)), top_merchants["sum"], color="#ff7f0e")
            ax.set_yticks(range(len(top_merchants)))
            ax.set_yticklabels(top_merchants.index, fontsize=9)
            ax.set_xlabel("Total Spend ($)", fontweight="bold")
            ax.set_title(f"Top Merchants in {selected_category}", fontsize=12, fontweight="bold")
            ax.invert_yaxis()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
        
        with col2:
            st.subheader("📅 Daily Trend")
            daily = cat_df.groupby(cat_df["date"].dt.date)["amount_spend"].sum()
            
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.bar(range(len(daily)), daily.values, color="#2ca02c", alpha=0.7)
            ax.set_xticks(range(0, len(daily), max(1, len(daily) // 10)))
            ax.set_xticklabels([daily.index[i] for i in range(0, len(daily), max(1, len(daily) // 10))], 
                              rotation=45, ha="right", fontsize=8)
            ax.set_ylabel("Daily Spend ($)", fontweight="bold")
            ax.set_title("Daily Breakdown", fontsize=12, fontweight="bold")
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)


elif mode == "forecast":
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🔮 Forecast")
    
    with col2:
        if st.button("← Back", key="back_forecast"):
            st.session_state["mode"] = "home"
            st.rerun()
    
    st.markdown("---")
    
    with st.sidebar:
        st.subheader("📊 Forecast Settings")
        months_lookback = st.slider("Months to analyze:", min_value=1, max_value=12, value=3, step=1)
        
        st.subheader("⏭️ Exclude Months")
        df["year_month"] = df["date"].dt.to_period("M").astype(str)
        available_months = sorted(df["year_month"].unique().tolist(), reverse=True)
        exclude_months = st.multiselect("Exclude anomaly months:", available_months, key="exclude_months")
        
        st.subheader("🚫 Exclude Categories")
        all_cats_for_exclude = sorted([c for c in df["category"].dropna().unique().tolist() if c != "EXCLUDE"])
        exclude_categories = st.multiselect("Exclude from forecast:", all_cats_for_exclude, key="exclude_categories")
    
    expenses_df = df[df["category"] != "EXCLUDE"].copy()
    
    if exclude_months:
        expenses_df = expenses_df[~expenses_df["year_month"].isin(exclude_months)]
    
    if exclude_categories:
        expenses_df = expenses_df[~expenses_df["category"].isin(exclude_categories)]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Total Spend Forecast")
        total_forecast = forecast_total_spend(expenses_df, months_lookback=months_lookback)
        
        if total_forecast:
            avg = total_forecast["avg_spend"]
            conf_low = total_forecast["confidence_low"]
            conf_high = total_forecast["confidence_high"]
            std_dev = total_forecast["std_dev"]
            num_months = total_forecast["num_months"]
            
            st.metric("Predicted Monthly Avg", f"${avg:,.0f}")
            st.caption(f"📊 Std Dev: ${std_dev:,.0f}")
            st.caption(f"📈 Range (±1σ): ${conf_low:,.0f} - ${conf_high:,.0f}")
            st.caption(f"📋 Based on {int(num_months)} months (after excluding outliers)")

            # Visualization
            fig, ax = plt.subplots(figsize=(8, 5))
            categories_vis = ["Low\n(±1σ)", "Expected", "High\n(±1σ)"]
            values = [conf_low, avg, conf_high]
            colors_vis = ["#ff7f0e", "#2ca02c", "#d62728"]
            bars = ax.bar(categories_vis, values, color=colors_vis, alpha=0.7, edgecolor="black", linewidth=2)
            ax.set_ylabel("Monthly Spend ($)", fontweight="bold")
            ax.set_title("Total Monthly Spend Forecast", fontsize=12, fontweight="bold")
            for bar, val in zip(bars, values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'${val:,.0f}', ha='center', va='bottom', fontweight='bold')
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
    
    with col2:
        st.subheader("📂 By Category Forecast")
        cat_forecast = forecast_by_category(expenses_df, months_lookback=months_lookback)
        
        if not cat_forecast.empty:
            cat_display = cat_forecast[["category", "avg_spend", "confidence_low", "confidence_high"]].copy()
            cat_display = cat_display.sort_values("avg_spend", ascending=False)
            
            # Table
            cat_table = cat_display.copy()
            cat_table.columns = ["Category", "Avg", "Low (±1σ)", "High (±1σ)"]
            cat_table["Avg"] = cat_table["Avg"].apply(lambda x: f"${x:,.0f}")
            cat_table["Low (±1σ)"] = cat_table["Low (±1σ)"].apply(lambda x: f"${x:,.0f}")
            cat_table["High (±1σ)"] = cat_table["High (±1σ)"].apply(lambda x: f"${x:,.0f}")
            st.dataframe(cat_table, use_container_width=True, hide_index=True)
            
            # Visualization
            fig, ax = plt.subplots(figsize=(8, 6))
            x_pos = range(len(cat_display))
            ax.barh(x_pos, cat_display["avg_spend"], color="#1f77b4", alpha=0.7)
            ax.set_yticks(x_pos)
            ax.set_yticklabels(cat_display["category"], fontsize=9)
            ax.set_xlabel("Avg Monthly Spend ($)", fontweight="bold")
            ax.set_title("Forecast by Category", fontsize=12, fontweight="bold")
            ax.invert_yaxis()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)


elif mode == "settings":
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("⚙️ Settings")
    
    with col2:
        if st.button("← Back", key="back_settings"):
            st.session_state["mode"] = "home"
            st.rerun()
    
    st.markdown("---")
    
    # Get current selected date range for scoping
    start_d, end_d = selected_date_range
    start_d = pd.to_datetime(start_d)
    end_d = pd.to_datetime(end_d)
    
    tab1, tab2 = st.tabs(["Merchant Rules", "One-Time Fixes"])
    
    with tab1:
        st.subheader("🔗 Apply to All Transactions (in selected month)")
        
        # Filter to selected date range and exclude credits
        recent_txns = df[(df["date"] >= start_d) & (df["date"] <= end_d) & (df["category"] != "EXCLUDE")].copy().sort_values("date", ascending=False).head(100)
        merchants = sorted(recent_txns["merchant"].dropna().unique())
        
        if len(merchants) == 0:
            st.info("No transactions in the selected date range.")
        else:
            merchant = st.selectbox("Select merchant:", merchants, key="merch_select")
            
            txns_from_merchant = recent_txns[recent_txns["merchant"] == merchant].head(3)
            if len(txns_from_merchant) > 0:
                st.write("**Recent transactions:**")
                for _, row in txns_from_merchant.iterrows():
                    st.caption(f"{row['date'].date()} · ${row['amount_spend']:.2f} · {row['description'][:50]}")
            
            current_cat = recent_txns[recent_txns["merchant"] == merchant]["category"].iloc[0] if len(txns_from_merchant) > 0 else "Unknown"
            st.info(f"Currently: **{current_cat}**")
            
            new_cat = st.selectbox("Change to:", all_categories, key="merch_cat")
            
            if st.button("✅ Apply", key="apply_merch"):
                overrides = _load_overrides()
                # use normalized merchant name for key
                norm_merchant = normalize_merchant(merchant)
                overrides[norm_merchant] = new_cat
                _save_overrides(overrides)
                _recompute_and_refresh()
                st.success(f"✅ Changed! '{merchant}' → {new_cat}")
                st.rerun()
    
    with tab2:
        st.subheader("💬 One-Time Fixes (in selected month)")
        
        # Filter to selected date range and exclude credits
        recent = df[(df["date"] >= start_d) & (df["date"] <= end_d) & (df["category"] != "EXCLUDE")].copy().sort_values("date", ascending=False).head(50)
        
        if len(recent) == 0:
            st.info("No transactions in the selected date range.")
        else:
            recent["label"] = recent.apply(
                lambda r: f"{r['date'].date()} | {r['merchant']} | ${r['amount_spend']:.2f}",
                axis=1
            )
            
            txn = st.selectbox("Select transaction:", recent["label"].tolist(), key="oneoff_select")
            
            if txn:
                matched = recent[recent["label"] == txn].iloc[0]
                old_cat = matched["category"]
                st.caption(f"Description: {matched['description']}")
                
                new_cat = st.selectbox("Change to:", all_categories, key="oneoff_cat")
                
                if st.button("✅ Apply", key="apply_oneoff"):
                    one_off = _load_one_off_map()
                    txn_id = str(matched["txn_id"])
                    one_off[txn_id] = new_cat
                    _save_one_off_map(one_off)
                    _recompute_and_refresh()
                    st.success(f"✅ Changed! '{matched['merchant']}' on {matched['date'].date()} → {new_cat}")
                    st.rerun()
