# dashboard.py

import streamlit as st
import pandas as pd
import sqlite3
import fetch_and_analyze as fa
from io import BytesIO

DB_PATH = "crypto_data.db"

st.set_page_config(page_title="AI-Powered Crypto Dashboard", layout="wide")
st.title("📊 AI-Powered Crypto Market Dashboard")
st.subheader("Live cryptocurrency data with narrative insights")

# --- Tabs ---
tab1, tab2 = st.tabs(["Live Market", "Historical Data"])

# --- LIVE MARKET TAB ---
with tab1:
    # Fetch live data
    df = fa.fetch_crypto_data()

    # Save snapshot to SQLite
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("crypto_snapshots", conn, if_exists="append", index=False)
    conn.close()

    # Identify biggest 24h gainer and loser
    df_clean = df[df["📉 24h Change"] != "N/A"].copy()
    df_clean["24h_val"] = pd.to_numeric(df_clean["📉 24h Change"].str.replace("%", ""), errors="coerce")
    gainer_idx = df_clean["24h_val"].idxmax() if not df_clean.empty else None
    loser_idx = df_clean["24h_val"].idxmin() if not df_clean.empty else None

    # Color coding function
    def highlight_gainers_losers(row):
        style = [""] * len(row)
        for i, col in enumerate(row.index):
            if col in ["📈 1h Change", "📉 24h Change", "📆 7d Change", "📆 14d Change", "📆 30d Change"]:
                val = row[col]
                if val != "N/A":
                    try:
                        f = float(val.replace("%", ""))
                        style[i] = "color: green" if f > 0 else "color: red" if f < 0 else ""
                    except:
                        style[i] = ""
            # Highlight biggest gainer/loser
            if row.name == gainer_idx:
                style[i] += "; background-color: #d4edda"
            if row.name == loser_idx:
                style[i] += "; background-color: #f8d7da"
        return style

    st.dataframe(df.style.apply(highlight_gainers_losers, axis=1))

    # Generate and display narrative insights
    insights = fa.generate_insights(df)
    st.markdown("---")
    st.subheader("🤖 Market Insights")
    st.markdown(insights)

    # Save sentiment to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crypto_sentiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            sentiment TEXT
        )
    """)
    cursor.execute("INSERT INTO crypto_sentiments (sentiment) VALUES (?)", (insights,))
    conn.commit()
    conn.close()

# --- HISTORICAL DATA TAB ---
with tab2:
    conn = sqlite3.connect(DB_PATH)
    hist_df = pd.read_sql("SELECT * FROM crypto_snapshots", conn)
    conn.close()

    if hist_df.empty:
        st.info("No historical data found. Live data will be saved automatically when fetching.")
    else:
        st.subheader("📊 Historical Snapshot Table")
        st.dataframe(hist_df)

        # --- Trend Visualization ---
        st.subheader("📈 Multi-Coin Trend Chart")

        # Select coins to plot
        coins = st.multiselect("Select Coins", hist_df["Name"].unique().tolist(), default=hist_df["Name"].unique().tolist())

        # Select timeframe
        timeframe_map = {
            "1h": "📈 1h Change",
            "24h": "📉 24h Change",
            "7d": "📆 7d Change",
            "14d": "📆 14d Change",
            "30d": "📆 30d Change"
        }
        selected_timeframe = st.selectbox("Select Timeframe", list(timeframe_map.keys()))
        col_name = timeframe_map[selected_timeframe]

        # Prepare data for plotting
        plot_df = hist_df[hist_df["Name"].isin(coins)].copy()
        for coin in coins:
            mask = plot_df["Name"] == coin
            plot_df.loc[mask, col_name] = pd.to_numeric(plot_df.loc[mask, col_name].str.replace("%", ""), errors="coerce")
        plot_df["Snapshot"] = range(1, len(plot_df) + 1)

        # Pivot and plot
        st.line_chart(plot_df.pivot(index="Snapshot", columns="Name", values=col_name))

        # --- Export Options ---
        st.subheader("💾 Export Historical Data")
        csv = hist_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv, file_name="crypto_history.csv", mime="text/csv")

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            hist_df.to_excel(writer, index=False, sheet_name="Snapshots")
        st.download_button("Download Excel", data=excel_buffer.getvalue(), file_name="crypto_history.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
