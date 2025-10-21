import sqlite3
import pandas as pd

DB_PATH = "crypto_data.db"

# Connect to the database
conn = sqlite3.connect(DB_PATH)

# --- Check historical snapshots ---
print("📊 Latest historical snapshots:")
snapshots_df = pd.read_sql("SELECT * FROM crypto_snapshots ORDER BY ROWID DESC LIMIT 10", conn)
print(snapshots_df)

# --- Check GPT sentiment ---
print("\n🤖 Latest stored GPT sentiment:")
sentiment_df = pd.read_sql("SELECT * FROM crypto_sentiments ORDER BY id DESC LIMIT 5", conn)
print(sentiment_df)

# Close connection
conn.close()
