import os
import time
import json
import requests
import pandas as pd
from dotenv import load_dotenv

# =========================================================
# 🔧 CONFIG
# =========================================================
load_dotenv()

API_KEY = os.getenv("COINGECKO_API_KEY")  # optional
API_URL = "https://api.coingecko.com/api/v3/coins/markets"
CACHE_FILE = "crypto_cache.json"
CACHE_TTL = 300  # 5 minutes cache to respect rate limits

COINS = [
    ("bitcoin", "BTC"),
    ("ethereum", "ETH"),
    ("tether", "USDT"),
    ("binancecoin", "BNB"),
    ("ripple", "XRP"),
    ("solana", "SOL"),
    ("usd-coin", "USDC"),
    ("dogecoin", "DOGE"),
    ("staked-ether", "STETH"),
    ("tron", "TRX"),
]

# =========================================================
# 🧮 HELPERS
# =========================================================
def safe_pct(value):
    if value is None:
        return "N/A"
    try:
        return f"{value:.2f}%"
    except Exception:
        return "N/A"


def load_cache():
    """Return cached data if it's recent."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
        if time.time() - cache.get("timestamp", 0) < CACHE_TTL:
            return pd.DataFrame(cache["data"])
    except Exception:
        return None
    return None


def save_cache(df):
    """Save data to local cache."""
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"timestamp": time.time(), "data": df.to_dict(orient="records")}, f)
    except Exception:
        pass


# =========================================================
# 📊 FETCH LIVE DATA (with retry + caching)
# =========================================================
def fetch_crypto_data():
    """Fetch live crypto data from CoinGecko, respecting rate limits."""
    # Try cached data first
    cached = load_cache()
    if cached is not None:
        print("🟡 Using cached market data (to avoid rate limit).")
        return cached

    coin_ids = [c[0] for c in COINS]
    coin_symbols = {c[0]: c[1] for c in COINS}

    params = {
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "price_change_percentage": "1h,24h,7d,14d,30d",
    }

    # Retry logic for 429 errors
    for attempt in range(3):
        try:
            response = requests.get(API_URL, params=params, timeout=10)
            if response.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"⚠️ Rate limit hit. Retrying in {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            data = response.json()
            break

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Error fetching data from CoinGecko: {e}")
            if attempt < 2:
                time.sleep(10)
                continue
            return cached if cached is not None else pd.DataFrame()
    else:
        return cached if cached is not None else pd.DataFrame()

    # Parse results
    results = []
    for coin in data:
        cid = coin.get("id")
        results.append({
            "Name": coin.get("name", "N/A"),
            "Symbol": coin_symbols.get(cid, coin.get("symbol", "N/A").upper()),
            "💰 Price (USD)": f"${coin.get('current_price', 0):,.2f}",
            "📈 1h Change": safe_pct(coin.get("price_change_percentage_1h_in_currency")),
            "📉 24h Change": safe_pct(coin.get("price_change_percentage_24h_in_currency")),
            "📆 7d Change": safe_pct(coin.get("price_change_percentage_7d_in_currency")),
            "📆 14d Change": safe_pct(coin.get("price_change_percentage_14d_in_currency")),
            "📆 30d Change": safe_pct(coin.get("price_change_percentage_30d_in_currency")),
        })

    df = pd.DataFrame(results)
    df["timestamp"] = pd.Timestamp.now()

    # Save cache for next calls
    save_cache(df)
    return df


# =========================================================
# 🧠 MARKET INSIGHTS
# =========================================================
def generate_insights(df):
    if df.empty:
        return "⚠️ No data available from CoinGecko. Please try again later."

    narrative = "🧠 Insight: "
    major_coins = ["Bitcoin", "Ethereum", "BNB"]
    stablecoins = ["Tether", "USDC"]
    others = [coin for coin in df["Name"].tolist() if coin not in major_coins + stablecoins]

    # Major coins
    major_trends = []
    for _, row in df.iterrows():
        name, price, change_24h = row["Name"], row["💰 Price (USD)"], row["📉 24h Change"]
        try:
            change_val = float(change_24h.replace("%", ""))
        except:
            change_val = 0
        if name in major_coins:
            if change_val < 0:
                major_trends.append(f"{name} fell {abs(change_val):.2f}% to {price}")
            elif change_val > 0:
                major_trends.append(f"{name} rose {change_val:.2f}% to {price}")
            else:
                major_trends.append(f"{name} stayed flat at {price}")
    if major_trends:
        narrative += " ".join(major_trends) + ". "

    # Stablecoins
    stable_trends = [f"{r['Name']} steady at {r['💰 Price (USD)']}" for _, r in df.iterrows() if r["Name"] in stablecoins]
    if stable_trends:
        narrative += " ".join(stable_trends) + ". "

    # Gainers and losers
    df_clean = df[df["📉 24h Change"] != "N/A"].copy()
    if not df_clean.empty:
        df_clean["val24h"] = pd.to_numeric(df_clean["📉 24h Change"].str.replace("%", ""), errors="coerce")
        gainer, loser = df_clean.loc[df_clean["val24h"].idxmax()], df_clean.loc[df_clean["val24h"].idxmin()]
        narrative += f"Top gainer: {gainer['Name']} ({gainer['📉 24h Change']}), biggest loser: {loser['Name']} ({loser['📉 24h Change']}). "

    narrative += "Overall, the market shows moderate volatility with traders adjusting to global sentiment."
    return narrative


# =========================================================
# 🧪 MAIN
# =========================================================
def main():
    print("Fetching cryptocurrency data...\n")
    df = fetch_crypto_data()
    print(df.to_string(index=False))
    print("\nMarket Insights:\n")
    print(generate_insights(df))


if __name__ == "__main__":
    main()
