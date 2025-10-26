import os
import sqlite3
import pandas as pd
import feedparser
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# =========================================================
# 🔧 CONFIG
# =========================================================
load_dotenv()  # Load .env variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = "crypto_data.db"

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# RSS feeds to fetch
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
            except:
                published_dt = None

            articles.append({
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", "").strip(),
                "published": published_dt
            })

    df = pd.DataFrame(articles).drop_duplicates(subset=["link"])
    if df.empty:
        return df

    # Save to DB
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
    conn.close()

    return df

# =========================================================
# 🤖 SENTIMENT ANALYSIS
# =========================================================
def analyze_sentiment(text):
    if not text.strip():
        return {"sentiment": "Neutral", "reason": "Empty text"}

    prompt = f"""
    Classify the sentiment of this crypto news as Positive, Negative, or Neutral.
    Text: "{text}"
    Respond in JSON as: {{"sentiment": "...", "reason": "..." }}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ GPT error: {e}")
        return {"sentiment": "Neutral", "reason": str(e)}

# =========================================================
# 📝 GENERATE MARKET SUMMARY
# =========================================================
def generate_news_summary(df):
    if df.empty:
        return "⚠️ No news articles fetched."
    
    titles_text = "\n".join(df["title"].tolist()[:10])
    prompt = f"""
    Summarize the following crypto news headlines into a short, concise market summary in 2-3 sentences:
    {titles_text}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ GPT error: {e}")
        return "⚠️ Could not generate summary."

# =========================================================
# 💾 STORE SENTIMENTS
# =========================================================
def update_sentiments():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM crypto_news WHERE sentiment IS NULL")
    rows = cursor.fetchall()
    for row_id, title in rows:
        sentiment = analyze_sentiment(title)
        try:
            # Store raw JSON string in DB
            cursor.execute(
                "UPDATE crypto_news SET sentiment=? WHERE id=?",
                (str(sentiment), row_id)
            )
        except Exception as e:
            print(f"⚠️ DB update error: {e}")
    conn.commit()
    conn.close()

# =========================================================
# ✅ MAIN FUNCTION
# =========================================================
def main():
    df = fetch_crypto_news()
    update_sentiments()
    summary = generate_news_summary(df)
    top_links = df[["title", "link"]].head(10)
    
    print(summary)
    print("\nTop 10 news links:")
    for _, row in top_links.iterrows():
        print(f"- {row['title']}: {row['link']}")

if __name__ == "__main__":
    main()
