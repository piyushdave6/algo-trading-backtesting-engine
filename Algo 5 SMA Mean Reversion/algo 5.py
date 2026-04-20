import json
import time
import numpy as np
import sys
from collections import deque
from datetime import datetime

# =============== PARAMETERS ===============
WINDOW = 20               # rolling window for SMA
ENTRY_THRESHOLD = 0.01    # 1% deviation to trigger entry
EXIT_THRESHOLD = 0.005    # 0.5% deviation to trigger exit
STOP_LOSS_PCT = 0.02      # 2% stop loss
BASE_CAPITAL = 100000.0
SUMMARY_INTERVAL = 100
LOOP_SLEEP = 5
DRAWDOWN_STOP_PCT = 0.05
UNITS = 100               # fixed units per trade
PRICE_FILE = "price_data.json"
# ==========================================

def read_price():
    """Read the latest simulated price from JSON."""
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"])
    except Exception:
        return None

def print_trade_log(trade_history, realized_pnl):
    """Pretty print the trade history when algo stops."""
    print("\n📘 FINAL TRADE HISTORY")
    print("-" * 70)
    print(f"{'Time':<20} {'Type':<8} {'Entry':<10} {'Exit':<10} {'PnL (₹)':<10}")
    print("-" * 70)
    for trade in trade_history:
        print(f"{trade['time']:<20} {trade['type']:<8} "
              f"{trade['entry']:<10.2f} {trade['exit']:<10.2f} {trade['pnl']:<10.2f}")
    print("-" * 70)
    print(f"Total Realized PnL: ₹{realized_pnl:,.2f}")
    print("-" * 70)

def main():
    print("🤖 Starting SMA Mean Reversion Algo — 1% Threshold (Press 'q' to exit safely)\n")

    prices = deque(maxlen=WINDOW)
    cash = BASE_CAPITAL
    realized_pnl = 0.0
    position = 0  # +1 long, -1 short, 0 none
    entry_price = 0.0
    entry_time = ""
    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - DRAWDOWN_STOP_PCT)
    last_summary = time.time()

    trade_history = []

    print("⏳ Waiting for enough price data...")

    try:
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

            sma = np.mean(prices)
            deviation = (price - sma) / sma
            equity = cash + realized_pnl + (position * UNITS * (price - entry_price))

            # safety: stop algo if too much loss
            if equity <= stop_equity:
                print("\n🚨 STOP TRIGGERED — 5% Capital Drawdown Reached.")
                break

            print(f"\n💹 Price: ₹{price:.2f} | SMA: ₹{sma:.2f} | Deviation: {deviation:+.2%} | Equity: ₹{equity:,.2f}")

            # ======= ENTRY LOGIC =======
            if position == 0:
                if deviation > ENTRY_THRESHOLD:
                    # Overbought → Short
                    entry_price = price
                    position = -1
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT ENTRY @ ₹{price:.2f} | Deviation: {deviation:+.2%} | Units={UNITS}")
                elif deviation < -ENTRY_THRESHOLD:
                    # Oversold → Long
                    entry_price = price
                    position = 1
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG ENTRY @ ₹{price:.2f} | Deviation: {deviation:+.2%} | Units={UNITS}")
                else:
                    print("⚪ No signal — price near SMA.")
            else:
                # ======= EXIT LOGIC =======
                unrealized = position * UNITS * (price - entry_price)
                print(f"📊 Unrealized PnL: ₹{unrealized:,.2f}")

                stop_loss = entry_price * (1 - STOP_LOSS_PCT) if position == 1 else entry_price * (1 + STOP_LOSS_PCT)
                exit_condition = abs(deviation) <= EXIT_THRESHOLD

                if exit_condition:
                    realized_pnl += unrealized
                    position_type = "LONG" if position == 1 else "SHORT"
                    trade_history.append({
                        "time": entry_time,
                        "type": position_type,
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unrealized
                    })
                    print(f"✅ EXIT @ ₹{price:.2f} | PnL: ₹{unrealized:,.2f} (Returned to SMA)")
                    position = 0
                elif (position == 1 and price <= stop_loss) or (position == -1 and price >= stop_loss):
                    realized_pnl += unrealized
                    position_type = "LONG" if position == 1 else "SHORT"
                    trade_history.append({
                        "time": entry_time,
                        "type": position_type,
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unrealized
                    })
                    print(f"❌ STOP LOSS EXIT @ ₹{price:.2f} | PnL: ₹{unrealized:,.2f}")
                    position = 0

            # ======= PERIODIC SUMMARY =======
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = cash + realized_pnl + (position * UNITS * (price - entry_price))
                total_pnl = total_equity - start_equity
                print("\n📘 PERFORMANCE SUMMARY (100s):")
                print(f"   Realized PnL: ₹{realized_pnl:,.2f}")
                print(f"   Total Equity: ₹{total_equity:,.2f}")
                print(f"   Net P/L: ₹{total_pnl:,.2f}")
                last_summary = time.time()

            # allow manual exit with key press
            import msvcrt  # works on Windows
            if msvcrt.kbhit():
                key = msvcrt.getch().decode("utf-8").lower()
                if key == "q":
                    print("\n🛑 Manual exit triggered by user (key 'q').")
                    break

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted manually (Ctrl+C).")

    finally:
        print_trade_log(trade_history, realized_pnl)
        print("✅ Algo stopped safely.\n")

if __name__ == "__main__":
    main()
