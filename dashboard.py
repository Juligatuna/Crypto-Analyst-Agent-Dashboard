import streamlit as st
import pandas as pd
import sqlite3
import fetch_and_analyze as fa
from sentiment_rss import fetch_crypto_news, analyze_sentiment
from openai import OpenAI
from io import BytesIO
import altair as alt
import datetime
import os
from dotenv import load_dotenv
load_dotenv()

# =========================================================
# 🔧 CONFIG
# =========================================================
DB_PATH = "crypto_data.db"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="💹 Crypto Analyst Agent Dashboard", layout="wide")
st.title("💹 Crypto Analyst Agent Dashboard")
st.caption("Empower your investment strategy with real-time analytics and historical trend visualization across multiple cryptocurrencies.")

# =========================================================
# 🧠 GPT Market Summary Helper
# =========================================================
def generate_gpt_market_summary(df):
    """Generate a natural language market summary using GPT-4o-mini."""
    try:
        # Ensure required columns exist
        available_cols = [c for c in ["Name", "📉 24h Change", "Price"] if c in df.columns]
        if not available_cols:
            raise ValueError("Required columns not found in DataFrame.")

        data_preview = df[available_cols].head(10).to_string(index=False)

        prompt = f"""
        You are a seasoned crypto market analyst.
        Analyze the following crypto data and produce a short, clear professional summary (3–5 sentences):
        - Mention general market trend.
        - Identify top gainers and losers.
        - Reference key coins (Bitcoin, Ethereum, etc.).
        - Include macro sentiment or investor tone if implied.

        Here is the data:
        {data_preview}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional crypto market analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=200
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"⚠️ GPT summary generation failed: {e}"

# =========================================================
# 🧩 TABS
# =========================================================
tab1, tab2 = st.tabs(["📈 Live Market", "🕒 Historical Data"])

# =========================================================
# 🔹 TAB 1: LIVE MARKET + NEWS
# =========================================================
with tab1:
    refresh = st.button("🔁 Refresh Data")

    try:
        if refresh:
            st.cache_data.clear()  # Clears cached data for real-time refresh
            st.success("✅ Live data refreshed successfully!")

        df = fa.fetch_crypto_data()
        if df is not None and not df.empty:
            # Save snapshot
            conn = sqlite3.connect(DB_PATH)
            df.to_sql("crypto_snapshots", conn, if_exists="append", index=False)
            conn.close()

            # Prepare table for styling
            df_clean = df.copy()
            df_clean["24h_val"] = pd.to_numeric(
                df_clean["📉 24h Change"].str.replace("%", ""), errors="coerce"
            )
            gainer_idx = df_clean["24h_val"].idxmax() if not df_clean.empty else None
            loser_idx = df_clean["24h_val"].idxmin() if not df_clean.empty else None

            def highlight_gainers_losers(row):
                style = [""] * len(row)
                for i, col in enumerate(row.index):
                    if col in [
                        "📈 1h Change",
                        "📉 24h Change",
                        "📆 7d Change",
                        "📆 14d Change",
                        "📆 30d Change",
                    ]:
                        val = row[col]
                        if val != "N/A":
                            try:
                                f = float(val.replace("%", ""))
                                style[i] = "color: green" if f > 0 else "color: red"
                            except:
                                style[i] = ""
                    if row.name == gainer_idx:
                        style[i] += "; background-color: #d4edda"
                    if row.name == loser_idx:
                        style[i] += "; background-color: #f8d7da"
                return style

            st.dataframe(df.style.apply(highlight_gainers_losers, axis=1))

            # --- GPT Market Insights ---
            st.markdown("---")
            st.subheader("🤖 Market Insights")
            gpt_summary = generate_gpt_market_summary(df)
            st.markdown(gpt_summary)

            # Save sentiment in DB
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS crypto_sentiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sentiment TEXT
                )
                """
            )
            cursor.execute(
                "INSERT INTO crypto_sentiments (sentiment) VALUES (?)", (gpt_summary,)
            )
            conn.commit()
            conn.close()

            # --- NEWS & SENTIMENT BELOW INSIGHTS ---
            st.markdown("---")
            st.subheader("🗞 Latest Crypto News & Sentiment")

            try:
                news_df = fetch_crypto_news()
                if news_df.empty:
                    st.info("⚠️ No news articles fetched.")
                else:
                    # Ensure DB table exists
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS crypto_news (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT,
                            link TEXT,
                            sentiment TEXT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                    conn.commit()

                    for _, row in news_df.head(10).iterrows():
                        sentiment = analyze_sentiment(str(row.get("content", "")))

                        # ✅ FIX: convert dict-type sentiment safely
                        if isinstance(sentiment, dict):
                            sentiment = str(sentiment)

                        cursor.execute(
                            "INSERT INTO crypto_news (title, link, sentiment) VALUES (?, ?, ?)",
                            (row["title"], row["link"], sentiment),
                        )
                    conn.commit()
                    conn.close()

                    for _, row in news_df.head(10).iterrows():
                        st.markdown(f"- [{row['title']}]({row['link']})")

                    # GPT News Summary
                    st.markdown("---")
                    st.subheader("🧭 News Summary")
                    try:
                        headlines = "\n".join(news_df["title"].head(10).tolist())
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are a crypto news analyst."},
                                {
                                    "role": "user",
                                    "content": f"Summarize the following crypto news headlines into a concise 3-sentence market overview:\n{headlines}",
                                },
                            ],
                            temperature=0.6,
                            max_tokens=150,
                        )
                        summary = response.choices[0].message.content.strip()
                        st.write(summary)
                    except Exception as e:
                        st.error(f"❌ News Summary Error: {e}")

            except Exception as e:
                st.error(f"❌ Error fetching/displaying news: {e}")

        else:
            st.warning("⚠️ No live data fetched.")
    except Exception as e:
        st.error(f"❌ Error fetching data: {e}")

# =========================================================
# 🔹 TAB 2: HISTORICAL DATA
# =========================================================
with tab2:
    try:
        conn = sqlite3.connect(DB_PATH)
        hist_df = pd.read_sql("SELECT * FROM crypto_snapshots", conn)
        conn.close()

        if not hist_df.empty:
            drop_cols = [c for c in ["Price", "Market Cap", "Volume (24h)"] if c in hist_df.columns]
            hist_df.drop(columns=drop_cols, inplace=True, errors="ignore")

    except Exception as e:
        st.error(f"❌ Database Error: {e}")
        hist_df = pd.DataFrame()

    if hist_df.empty:
        st.info("⚠️ No historical data found. Live snapshots will populate automatically.")
    else:
        st.subheader("📊 Historical Snapshot Table")
        st.dataframe(hist_df)

        st.subheader("📈 Multi-Coin Trend Chart")

        coins = st.multiselect(
            "Select Coins",
            hist_df["Name"].unique().tolist(),
            default=hist_df["Name"].unique().tolist(),
        )

        timeframe_map = {
            "1h": "📈 1h Change",
            "24h": "📉 24h Change",
            "7d": "📆 7d Change",
            "14d": "📆 14d Change",
            "30d": "📆 30d Change",
        }

        selected_timeframe = st.selectbox("Select Timeframe", list(timeframe_map.keys()))
        col_name = timeframe_map[selected_timeframe]

        use_timestamp = st.toggle("Use Actual Timestamp (instead of Snapshot #)", value=False)

        plot_df = hist_df[hist_df["Name"].isin(coins)].copy()
        plot_df[col_name] = (
            plot_df[col_name].astype(str).str.replace("%", "", regex=False).astype(float)
        )
        plot_df["Snapshot"] = range(1, len(plot_df) + 1)

        if use_timestamp and "timestamp" in plot_df.columns:
            x_field = alt.X("timestamp:T", title="Timestamp")
        else:
            x_field = alt.X("Snapshot:Q", title="Snapshot Number")

        if not plot_df.empty:
            chart = (
                alt.Chart(plot_df)
                .mark_line(point=True)
                .encode(
                    x=x_field,
                    y=alt.Y(f"{col_name}:Q", title=f"{selected_timeframe} Change (%)", scale=alt.Scale(zero=False)),
                    color=alt.Color("Name:N", title="Cryptocurrency"),
                    tooltip=["Name", col_name, "timestamp" if use_timestamp else "Snapshot"],
                )
                .properties(height=400)
                .interactive()
            )

            try:
                st.altair_chart(chart, width="stretch")
            except TypeError:
                st.altair_chart(chart, use_container_width=True)
        else:
            st.info("⚠️ No data available for the selected coins or timeframe.")

        st.markdown("---")
        st.subheader("💾 Export Historical Data")

        csv = hist_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download CSV",
            data=csv,
            file_name="crypto_history.csv",
            mime="text/csv",
        )

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            hist_df.to_excel(writer, index=False, sheet_name="Snapshots")
        st.download_button(
            "⬇️ Download Excel",
            data=excel_buffer.getvalue(),
            file_name="crypto_history.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
