import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from src.plot_charts import _read_data, CLEAN_DIR, BUDGET_MONTHLY 

st.set_page_config(page_title="Expense Analyzer — Week 5", layout="wide")
st.title("Expense Analyzer — Week 5")

df = _read_data(CLEAN_DIR)

# sidebar
months = sorted(df["date"].dt.to_period("M").astype(str).unique())
month = st.sidebar.selectbox("Month", months, index=len(months)-1)
budget = st.sidebar.number_input("Monthly budget ($)", value=float(BUDGET_MONTHLY), min_value=0.0, step=100.0)
top_n = st.sidebar.slider("Top merchants (N)", 5, 20, 12)

# filter
m = df[df["month"] == month]
total = float(m["amount_spend"].sum())

c1, c2, c3 = st.columns(3)
c1.metric("Total spend", f"${total:,.2f}")
c2.metric("Budget", f"${budget:,.0f}")
c3.metric("Remaining", f"${max(budget-total, 0):,.2f}")

# spend by category
cat = m.groupby("category")["amount_spend"].sum().sort_values()
fig1, ax1 = plt.subplots(figsize=(7,4))
cat.plot(kind="barh", ax=ax1)
ax1.set_title(f"Spend by Category — {month}")
ax1.set_xlabel("Dollars")
st.pyplot(fig1)

# top merchants
top = m.groupby("merchant")["amount_spend"].sum().sort_values(ascending=False).head(top_n).iloc[::-1]
fig2, ax2 = plt.subplots(figsize=(7,4))
top.plot(kind="barh", ax=ax2)
ax2.set_title(f"Top {top_n} Merchants — {month}")
ax2.set_xlabel("Dollars")
st.pyplot(fig2)

# heatmap across months
pivot = df.pivot_table(values="amount_spend", index="category", columns="month", aggfunc="sum", fill_value=0.0).sort_index()
fig3, ax3 = plt.subplots(figsize=(9,6))
im = ax3.imshow(pivot.values, aspect="auto", interpolation="nearest")
ax3.set_title("Category × Month Heatmap (expenses only)")
ax3.set_xlabel("Month"); ax3.set_ylabel("Category")
ax3.set_xticks(range(len(pivot.columns))); ax3.set_xticklabels(pivot.columns, rotation=45, ha="right")
ax3.set_yticks(range(len(pivot.index)));  ax3.set_yticklabels(pivot.index)
fig3.colorbar(im, ax=ax3, label="Dollars")
st.pyplot(fig3)

# table
st.subheader("Transactions")
cols = ["date","merchant","category","amount_spend","description"]
st.dataframe(m.sort_values("date")[cols].rename(columns={"amount_spend":"spend"}))
