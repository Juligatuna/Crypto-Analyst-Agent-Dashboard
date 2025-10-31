# Crypto Analyst Agent Dashboard

An interactive Streamlit dashboard that analyzes cryptocurrency market data, visualizes key trends, and generates insights using real-time or cached data.

## 🚀 Live Dashboard

Explore the live Streamlit app here:  
👉 [Crypto Analyst Agent Dashboard](https://crypto-analyst-agent-dashboard.streamlit.app/)

## Features

📊 Interactive crypto analytics dashboard built with Streamlit

🧠 Real-time or periodic data fetching from public APIs

💾 Local environment variable management with .env

🛠️ Easy to deploy on Streamlit Cloud

⚡ Lightweight — no external database dependency

## Repository Structure
```bash
Crypto-Analyst-Agent/
├── dashboard.py          # Streamlit dashboard interface
├── fetch_and_analyze.py  # Data fetching & analysis logic
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (API keys, etc.)
└── README.md             # Project documentation
```
## Installation & Setup
### 1. Clone the repository
git clone https://github.com/<your-username>/Crypto-Analyst-Agent.git
cd Crypto-Analyst-Agent

### 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate  # on Windows
source venv/bin/activate  # on macOS/Linux

### 3. Install dependencies
pip install -r requirements.txt

### 4. Set environment variables

Create a .env file in the root folder with your API keys:

API_KEY=your_api_key_here

### 5. Run locally
streamlit run dashboard.py

## Deploying on Streamlit Cloud

Push the repository to GitHub.

Go to https://streamlit.io/cloud
 → “Deploy an app”.

Select your GitHub repo and the dashboard.py file.

Add your .env variables in Secrets Manager under app settings.

Deploy — your dashboard will be live and shareable!

## Example .env (do not upload this file)
API_KEY=your_public_api_key

## Author
Julius Irungu
juligatuna@gmail.com
