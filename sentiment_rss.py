import os
import sqlite3
import pandas as pd
import feedparser
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# =========================================================
# 🔧 CONFIG
# =========================================================
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = "crypto_data.db"

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not found. Please check your .env file.")

client = OpenAI(api_key=OPENAI_API_KEY)

FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptonews.com/news/feed"
]

# =========================================================
# 📰 FETCH NEWS
# =========================================================
def fetch_crypto_news():
    articles = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            published = getattr(entry, "published", None) or getattr(entry, "updated", None)
            try:
                published_dt = datetime.strptime(published, "%a, %d %b %Y %H:%M:%S %Z") if published else None
            except Exception:
                published_dt = None

            articles.append({
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", "").strip(),
                "published": published_dt
            })

    df = pd.DataFrame(articles).drop_duplicates(subset=["link"])
    if df.empty:
        return df

    # ✅ Keep only latest 20 to balance speed & coverage
    df = df.sort_values(by="published", ascending=False).head(20)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crypto_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT UNIQUE,
            published DATETIME,
            sentiment TEXT
        )
    """)
    for _, row in df.iterrows():
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO crypto_news (title, link, published) VALUES (?, ?, ?)",
                (row["title"], row["link"], row["published"])
            )
        except Exception as e:
            print(f"⚠️ DB insert error: {e}")
    conn.commit()

    # ✅ Only return *new* (unprocessed) articles for sentiment analysis
    new_articles = pd.read_sql_query(
        "SELECT * FROM crypto_news WHERE sentiment IS NULL ORDER BY published DESC LIMIT 20",
        conn
    )

    conn.close()
    return new_articles

# =========================================================
# 🤖 SENTIMENT ANALYSIS
# =========================================================
def analyze_sentiment_batch(texts):
    """Analyze up to 5 articles in one API call to speed up processing."""
    combined_text = "\n\n".join([f"{i+1}. {t}" for i, t in enumerate(texts)])
    prompt = f"""
    Analyze the sentiment of the following crypto news headlines (Positive, Negative, Neutral).
    Respond in JSON list format with one entry per headline, each containing:
    {{"headline": "...", "sentiment": "...", "reason": "..." }}

    Headlines:
    {combined_text}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return result
            else:
                return [{"sentiment": "Neutral", "reason": "Parsing error"} for _ in texts]
        except json.JSONDecodeError:
            return [{"sentiment": "Neutral", "reason": "Invalid JSON"} for _ in texts]
    except Exception as e:
        print(f"❌ GPT error: {e}")
        return [{"sentiment": "Neutral", "reason": str(e)} for _ in texts]

# ✅ Compatibility wrapper — do not change anything else
def analyze_sentiment(text):
    return analyze_sentiment_batch([text])[0]

# =========================================================
# 🧠 MULTI-THREADED SENTIMENT UPDATES
# =========================================================
def update_sentiments(df):
    if df.empty:
        print("✅ No new articles need sentiment updates.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    rows = df[["id", "title"]].values.tolist()
    print(f"🧠 Analyzing {len(rows)} new articles in batches of 5...")

    # Group rows into batches of 5
    batches = [rows[i:i+5] for i in range(0, len(rows), 5)]

    for batch in batches:
        texts = [title for _, title in batch]
        sentiments = analyze_sentiment_batch(texts)
        for (row_id, title), sentiment in zip(batch, sentiments):
            try:
                cursor.execute(
                    "UPDATE crypto_news SET sentiment=? WHERE id=?",
                    (json.dumps(sentiment), row_id)
                )
            except Exception as e:
                print(f"⚠️ DB update error for '{title}': {e}")
    conn.commit()
    conn.close()
    print("✅ Sentiment updates complete.")

# =========================================================
# 📝 GENERATE MARKET SUMMARY
# =========================================================
def generate_news_summary(df):
    if df.empty:
        return "⚠️ No new news to summarize."
    
    titles_text = "\n".join(df["title"].head(10).tolist())
    prompt = f"""
    Summarize the following crypto news headlines into a short, concise market summary in 2–3 sentences:
    {titles_text}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ GPT error: {e}")
        return "⚠️ Could not generate summary."

# =========================================================
# ✅ MAIN FUNCTION
# =========================================================
def main():
    df = fetch_crypto_news()
    update_sentiments(df)
    summary = generate_news_summary(df)
    
    if not df.empty:
        top_links = df[["title", "link"]].head(10)
        print(summary)
        print("\nTop 10 new news links:")
        for _, row in top_links.iterrows():
            print(f"- {row['title']}: {row['link']}")
    else:
        print("✅ No new articles found today.")

if __name__ == "__main__":
    main()
