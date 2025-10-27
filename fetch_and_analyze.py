
import os
import requests
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("COINGECKO_API_KEY")  # Optional for future use
API_URL = "https://api.coingecko.com/api/v3/coins/markets"

# List of coins to track
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
    ("tron", "TRX")
]

def safe_pct(value):
    """Format percentage values safely."""
    if value is None:
        return "N/A"
    try:
        return f"{value:.2f}%"
    except:
        return "N/A"

def fetch_crypto_data():
    """Fetch live crypto data from CoinGecko API."""
    coin_ids = [c[0] for c in COINS]
    coin_symbols = {c[0]: c[1] for c in COINS}

    params = {
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "price_change_percentage": "1h,24h,7d,14d,30d"
    }

    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error fetching data from CoinGecko: {e}")
        return pd.DataFrame()

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

    # ✅ Ensure timestamp is added for historical tracking
    df["timestamp"] = pd.Timestamp.now()

    return df

def generate_insights(df):
    """Generate narrative insights and highlight key market movements."""
    if df.empty:
        return "⚠️ No data available from CoinGecko. Please try again later."

    narrative = "🧠 Insight: "

    major_coins = ["Bitcoin", "Ethereum", "BNB"]
    stablecoins = ["Tether", "USDC"]
    others = [coin for coin in df["Name"].tolist() if coin not in major_coins + stablecoins]

    # Major coin trends
    major_trends = []
    for _, row in df.iterrows():
        name = row["Name"]
        price = row["💰 Price (USD)"]
        change_24h = row.get("📉 24h Change", "0.00%") or "0.00%"
        try:
            change_val = float(change_24h.replace("%", ""))
        except:
            change_val = 0.0

        if name in major_coins:
            if change_val < 0:
                major_trends.append(f"{name} has dipped slightly to {price}" if abs(change_val) < 2 else f"{name} has dropped {abs(change_val):.2f}% to {price}")
            elif change_val > 0:
                major_trends.append(f"{name} has risen {change_val:.2f}% to {price}")
            else:
                major_trends.append(f"{name} remains stable at {price}")

    if major_trends:
        narrative += " ".join(major_trends) + ", reflecting recent market movements. "

    # Stablecoin trends
    stable_trends = []
    for _, row in df.iterrows():
        name = row["Name"]
        price = row["💰 Price (USD)"]
        if name in stablecoins:
            stable_trends.append(f"{name} remains relatively stable at {price}")
    if stable_trends:
        narrative += "Stablecoins like " + ", ".join(stable_trends) + ", indicating a flight to safety among investors. "

    # Biggest gainer and loser
    df_clean = df[df["📉 24h Change"] != "N/A"].copy()
    if not df_clean.empty:
        df_clean["24h_val"] = pd.to_numeric(df_clean["📉 24h Change"].str.replace("%", ""), errors="coerce")
        gainer_row = df_clean.loc[df_clean["24h_val"].idxmax()]
        loser_row = df_clean.loc[df_clean["24h_val"].idxmin()]
        narrative += f"The biggest 24h gainer is {gainer_row['Name']} ({gainer_row['📉 24h Change']}) and the biggest 24h loser is {loser_row['Name']} ({loser_row['📉 24h Change']}). "

    # Other coins negative momentum
    other_trends = []
    for _, row in df.iterrows():
        name = row["Name"]
        change_24h = row.get("📉 24h Change", "0.00%") or "0.00%"
        try:
            change_val = float(change_24h.replace("%", ""))
        except:
            change_val = 0.0
        if name in others and change_val < 0:
            other_trends.append(name)
    if other_trends:
        narrative += ", ".join(other_trends) + " also reflect negative momentum, suggesting broader market hesitancy. "

    narrative += "This subdued performance may stem from macroeconomic factors, such as inflation concerns and tightening monetary policies, which continue to influence investor sentiment. Overall, traders should remain vigilant as volatility remains a defining characteristic of the current crypto landscape."

    return narrative

def main():
    print("Fetching cryptocurrency data...\n")
    df = fetch_crypto_data()
    print(df.to_string(index=False))

    print("\nMarket Insights:\n")
    insights = generate_insights(df)
    print(insights)

if __name__ == "__main__":
    main()
