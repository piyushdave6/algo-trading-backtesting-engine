import json
import time
import numpy as np
import sys
from collections import deque

# =============== PARAMETERS ===============
WINDOW = 20               # rolling window for mean/std
ENTRY_Z = 1.0             # entry threshold
EXIT_Z = 0.2              # exit threshold (reversion to mean)
BASE_CAPITAL = 100000.0
STOP_LOSS_PCT = 0.02      # 2% stop loss
SUMMARY_INTERVAL = 100
LOOP_SLEEP = 5
DRAWDOWN_STOP_PCT = 0.05  # stop trading at -5% total loss
UNITS = 100               # fixed trade size (buy/sell quantity)
PRICE_FILE = "price_data.json"
# ==========================================

def read_price():
    """Read latest price from simulated feed."""
    try:
        with open(PRICE_FILE, "r") as f:
            return float(json.load(f)["price"])
    except Exception:
        return None

def main():
    print("🤖 Starting Z-Score Mean Reversion Algo (100-Unit Trades)\n")

    prices = deque(maxlen=WINDOW)
    cash = BASE_CAPITAL
    realized_pnl = 0.0
    position = 0           # +1 = long, -1 = short, 0 = none
    entry_price = 0.0
    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - DRAWDOWN_STOP_PCT)
    last_summary = time.time()

    print("⏳ Collecting price data to initialize...")

    while True:
        price = read_price()
        if price is None:
            print("⚠️ Waiting for price data...")
            time.sleep(3)
            continue

        prices.append(price)

        if len(prices) < WINDOW:
            print(f"Collecting data... ({len(prices)}/{WINDOW})")
            time.sleep(2)
            continue

        mean = np.mean(prices)
        std = np.std(prices)
        if std == 0:
            time.sleep(LOOP_SLEEP)
            continue

        z = (price - mean) / std
        equity = cash + realized_pnl + (position * UNITS * (price - entry_price))

        # global risk limit
        if equity <= stop_equity:
            print("\n🚨 STOP TRIGGERED — Equity down 5% from start.")
            print(f"💔 Final Equity: ₹{equity:,.2f}")
            sys.exit()

        print(f"\n💹 Price: ₹{price:.2f} | Mean: ₹{mean:.2f} | Z: {z:+.2f} | Equity: ₹{equity:,.2f}")

        # ============ TRADING LOGIC ============
        if position == 0:
            if z > ENTRY_Z:
                # Overbought → short 100 units
                entry_price = price
                position = -1
                print(f"📉 SHORT ENTRY @ ₹{price:.2f} | Z={z:+.2f} | Units={UNITS}")
            elif z < -ENTRY_Z:
                # Oversold → long 100 units
                entry_price = price
                position = 1
                print(f"📈 LONG ENTRY @ ₹{price:.2f} | Z={z:+.2f} | Units={UNITS}")
            else:
                print("⚪ No trade — Z-score within neutral range.")
        else:
            # manage open trade
            unrealized = position * UNITS * (price - entry_price)
            print(f"📊 Unrealized PnL: ₹{unrealized:,.2f}")

            stop_loss = entry_price * (1 - STOP_LOSS_PCT) if position == 1 else entry_price * (1 + STOP_LOSS_PCT)

            # Exit if mean reversion or stop loss hit
            if abs(z) <= EXIT_Z:
                realized_pnl += unrealized
                position = 0
                print(f"✅ EXIT @ ₹{price:.2f} | Realized PnL: ₹{unrealized:,.2f}")
            elif (position == 1 and price <= stop_loss) or (position == -1 and price >= stop_loss):
                realized_pnl += unrealized
                position = 0
                print(f"❌ STOP LOSS EXIT @ ₹{price:.2f} | Realized PnL: ₹{unrealized:,.2f}")

        # periodic summary
        if time.time() - last_summary >= SUMMARY_INTERVAL:
            total_equity = cash + realized_pnl + (position * UNITS * (price - entry_price))
            total_pnl = total_equity - start_equity
            print("\n📘 PERFORMANCE SUMMARY (100s):")
            print(f"   Realized PnL: ₹{realized_pnl:,.2f}")
            print(f"   Total Equity: ₹{total_equity:,.2f}")
            print(f"   Net P/L: ₹{total_pnl:,.2f}")
            last_summary = time.time()

        time.sleep(LOOP_SLEEP)

if __name__ == "__main__":
    main()
