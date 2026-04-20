import yfinance as yf
import pandas as pd
import os
import time

# Standard Nifty 50 Tickers for Backtesting
TICKERS = [
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS", "SBILIFE.NS", "TCS.NS",
    "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS", "RELIANCE.NS",
    "ONGC.NS", "BPCL.NS", "COALINDIA.NS", "POWERGRID.NS", "HINDUNILVR.NS",
    "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "MARUTI.NS", "M&M.NS",
    "BAJAJ-AUTO.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "SUNPHARMA.NS",
    "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "TATASTEEL.NS",
    "JSWSTEEL.NS", "HINDALCO.NS", "ULTRACEMCO.NS", "GRASIM.NS", "BHARTIARTL.NS",
    "LT.NS", "ASIANPAINT.NS", "TITAN.NS", "TRENT.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "UPL.NS", "LTIM.NS", "SHRIRAMFIN.NS", "NTPC.NS"
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def download_data():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    print(f"Downloading 5m data for {len(TICKERS)} tickers...")
    for ticker in TICKERS:
        try:
            df = yf.download(ticker, interval="5m", period="60d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            cols = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
            df = df[[c for c in cols if c in df.columns]]
            df = df.dropna()
            if "Datetime" in df.columns:
                df["Datetime"] = pd.to_datetime(df["Datetime"]).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
            df.to_excel(os.path.join(DATA_DIR, f"{ticker}_5m_60d.xlsx"), index=False)
            print(f"  Saved {ticker}")
            time.sleep(0.5)
        except Exception as e: print(f"  Error {ticker}: {e}")

if __name__ == "__main__":
    download_data()
