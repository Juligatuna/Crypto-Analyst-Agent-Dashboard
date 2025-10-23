import streamlit as st
import pandas as pd
import sqlite3
import fetch_and_analyze as fa
from io import BytesIO
import altair as alt
import os

# --- Database Path ---
DB_PATH = "crypto_data.db"

# --- Streamlit Page Setup ---
st.set_page_config(page_title="AI-Powered Crypto Dashboard", layout="wide")
st.title("📊 AI-Powered Crypto Market Dashboard")
st.subheader("Live cryptocurrency data with narrative insights")

# --- Safe Database Connection ---
def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER)")
        conn.commit()
        return conn
    except sqlite3.OperationalError:
        st.warning("⚠️ Running in memory-only mode (no database persistence).")
        return sqlite3.connect(":memory:", check_same_thread=False)

# --- Tabs ---
tab1, tab2 = st.tabs(["Live Market", "Historical Data"])

# =============================
# 🔹 TAB 1: LIVE MARKET
# =============================
with tab1:
    df = fa.fetch_crypto_data()

    # Add snapshot timestamp for tracking
    df["snapshot"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save snapshot to SQLite
    try:
        conn = get_connection()
        df.to_sql("crypto_snapshots", conn, if_exists="append", index=False)
        conn.close()
    except Exception as e:
        st.error("⚠️ Could not save snapshot to database.")
        st.write(e)

    # Identify biggest 24h gainer/loser safely
    if "📉 24h Change" in df.columns:
        df_clean = df[df["📉 24h Change"] != "N/A"].copy()
        df_clean["24h_val"] = pd.to_numeric(df_clean["📉 24h Change"].str.replace("%", ""), errors="coerce")
        gainer_idx = df_clean["24h_val"].idxmax() if not df_clean.empty else None
        loser_idx = df_clean["24h_val"].idxmin() if not df_clean.empty else None
    else:
        gainer_idx = loser_idx = None

    # Style function
    def highlight_gainers_losers(row):
        style = [""] * len(row)
        for i, col in enumerate(row.index):
            if col.startswith("📈") or col.startswith("📉") or col.startswith("📆"):
                val = row[col]
                if val != "N/A":
                    try:
                        f = float(val.replace("%", ""))
                        style[i] = "color: green" if f > 0 else "color: red" if f < 0 else ""
                    except:
                        style[i] = ""
            if row.name == gainer_idx:
                style[i] += "; background-color: #d4edda"
            if row.name == loser_idx:
                style[i] += "; background-color: #f8d7da"
        return style

    # ✅ Hide internal tracking columns before display
    display_df = df.drop(columns=["timestamp", "snapshot"], errors="ignore")

    # Display styled table
    st.dataframe(display_df.style.apply(highlight_gainers_losers, axis=1))

    # Market insights
    insights = fa.generate_insights(df)
    st.markdown("---")
    st.subheader("🤖 Market Insights")
    st.markdown(insights)

    # Save sentiment
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crypto_sentiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot DATETIME DEFAULT CURRENT_TIMESTAMP,
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

        # ✅ Use correct columns and types for Altair
        alt.data_transformers.disable_max_rows()

        # Check basic columns
        name_col = "Name" if "Name" in hist_df.columns else "Coin"
        price_col = "💰 Price" if "💰 Price" in hist_df.columns else "Price"

        # Ensure timestamp/snapshot exists
        if "snapshot" not in hist_df.columns and "Timestamp" in hist_df.columns:
            hist_df["snapshot"] = hist_df["Timestamp"]
        hist_df["snapshot"] = pd.to_datetime(hist_df["snapshot"], errors="coerce")

        # Clean data
        hist_df[price_col] = pd.to_numeric(hist_df[price_col], errors="coerce")
        hist_df = hist_df.dropna(subset=["snapshot", price_col, name_col])

        # User selects coins
        coins = hist_df[name_col].unique().tolist()
        selected_coins = st.multiselect("Select Coins", coins, default=coins[:3])

        plot_df = hist_df[hist_df[name_col].isin(selected_coins)]

        if not plot_df.empty:
            chart = (
                alt.Chart(plot_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("snapshot:T", title="Snapshot Time"),
                    y=alt.Y(f"{price_col}:Q", title="Price (USD)", scale=alt.Scale(zero=False)),
                    color=alt.Color(f"{name_col}:N", title="Cryptocurrency"),
                    tooltip=[name_col, price_col, "snapshot"]
                )
                .properties(height=400, title="Multi-Coin Price Trend")
                .interactive()
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("⚠️ No data available for selected coins or timeframe.")

        # --- Export Options ---
        st.subheader("💾 Export Historical Data")
        csv = hist_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv, file_name="crypto_history.csv", mime="text/csv")

        # ✅ Safer Excel Export
        excel_buffer = BytesIO()
        try:
            with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
                hist_df.to_excel(writer, index=False, sheet_name="Snapshots")
        except ModuleNotFoundError:
            with pd.ExcelWriter(excel_buffer) as writer:  # fallback to openpyxl
                hist_df.to_excel(writer, index=False, sheet_name="Snapshots")

        st.download_button(
            "Download Excel",
            data=excel_buffer.getvalue(),
            file_name="crypto_history.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
