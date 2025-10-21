import os
from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError

# Load environment variables from .env
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Optional: fallback IP if DNS fails
FALLBACK_IP = "56.228.74.197"  # replace with nslookup result

print("🔍 Checking environment variables:")
print(f"Host: '{DB_HOST}'")
print(f"Database: '{DB_NAME}'")
print(f"User: '{DB_USER}'")
print(f"Password: {'*' * len(DB_PASSWORD)}")
print(f"Port: '{DB_PORT}'")
print("-" * 60)

def try_connect(host):
    try:
        conn = psycopg2.connect(
            host=host,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print(f"✅ Successfully connected to PostgreSQL at {host}:{DB_PORT}")
        conn.close()
        return True
    except OperationalError as e:
        print(f"❌ Connection failed to {host}:{DB_PORT}")
        print(e)
        return False

# First try the hostname
if not try_connect(DB_HOST):
    print("\n⚠️ Hostname failed, trying fallback IP...")
    try_connect(FALLBACK_IP)
