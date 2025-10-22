import streamlit as st
import pandas as pd
import sqlite3
import fetch_and_analyze as fa
from io import BytesIO
import altair as alt  # ✅ Added for better trend visualization
import os

# --- Database Path ---
DB_PATH = "crypto_data.db"

# --- Streamlit Page Setup ---
st.set_page_config(page_title="AI-Powered Crypto Dashboard", layout="wide")
st.title("📊 AI-Powered Crypto Market Dashboard")
st.subheader("Live cryptocurrency data with narrative insights")

# --- Safe database connection (fix for Streamlit Cloud / read-only env) ---
def get_connection():
    try:
        # Try to use local DB (works locally or in Railway writable container)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        # Quick test write
        conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER)")
        conn.commit()
        return conn
    except sqlite3.OperationalError:
        # Fallback to in-memory DB if write access is blocked
        st.warning("⚠️ Running in memory-only mode (no database persistence).")
        return sqlite3.connect(":memory:", check_same_thread=False)


# --- Tabs ---
tab1, tab2 = st.tabs(["Live Market", "Historical Data"])

# =============================
# 🔹 TAB 1: LIVE MARKET
# =============================
with tab1:
    # Fetch live data
    df = fa.fetch_crypto_data()

    # Add timestamp for historical tracking
    df["timestamp"] = pd.Timestamp.now()

    # Save snapshot to SQLite (with fallback handling)
    try:
        conn = get_connection()
        df.to_sql("crypto_snapshots", conn, if_exists="append", index=False)
        conn.close()
    except Exception as e:
        st.error("⚠️ Could not save snapshot to database.")
        st.write(e)

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

    # Display styled dataframe
    st.dataframe(df.style.apply(highlight_gainers_losers, axis=1))

    # Generate and display narrative insights
    insights = fa.generate_insights(df)
    st.markdown("---")
    st.subheader("🤖 Market Insights")
    st.markdown(insights)

    # Save sentiment/insights to database (safe)
    try:
        conn = get_connection()
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
    except Exception as e:
        st.error("⚠️ Could not save sentiment to database.")
        st.write(e)

# =============================
# 🔹 TAB 2: HISTORICAL DATA
# =============================
with tab2:
    try:
        conn = get_connection()
        hist_df = pd.read_sql("SELECT * FROM crypto_snapshots", conn)
        conn.close()
    except Exception as e:
        st.error("⚠️ Could not load historical data.")
        st.write(e)
        hist_df = pd.DataFrame()

    if hist_df.empty:
        st.info("No historical data found. Live data will be saved automatically when fetching.")
    else:
        st.subheader("📊 Historical Snapshot Table")
        st.dataframe(hist_df)

        # --- Trend Visualization ---
        st.subheader("📈 Multi-Coin Trend Chart")

        # Select coins to plot
        coins = st.multiselect(
            "Select Coins",
            hist_df["Name"].unique().tolist(),
            default=hist_df["Name"].unique().tolist()
        )

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
        plot_df[col_name] = (
            plot_df[col_name]
            .astype(str)
            .str.replace("%", "", regex=False)
            .astype(float)
        )

        # ✅ Use timestamp for x-axis (not snapshot)
        if "timestamp" in plot_df.columns:
            plot_df["timestamp"] = pd.to_datetime(plot_df["timestamp"])
        else:
            plot_df["timestamp"] = pd.to_datetime("now")

        # Plot with Altair (time-based)
        if not plot_df.empty:
            chart = (
                alt.Chart(plot_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("timestamp:T", title="Time"),
                    y=alt.Y(f"{col_name}:Q", title=f"{selected_timeframe} Change (%)"),
                    color=alt.Color("Name:N", title="Cryptocurrency"),
                    tooltip=["Name", col_name, "timestamp"]
                )
                .properties(height=400)
                .interactive()
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No data available for the selected coins or timeframe.")

        # --- Export Options ---
        st.subheader("💾 Export Historical Data")
        csv = hist_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name="crypto_history.csv",
            mime="text/csv"
        )

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            hist_df.to_excel(writer, index=False, sheet_name="Snapshots")
        st.download_button(
            "Download Excel",
            data=excel_buffer.getvalue(),
            file_name="crypto_history.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
