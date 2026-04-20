import json
import time
import numpy as np
import sys
from collections import deque
from datetime import datetime

# =============== PARAMETERS ===============
SHORT_WINDOW = 5          # short-term MA
LONG_WINDOW = 12          # long-term MA
STOP_LOSS_PCT = 0.02      # 2% stop loss
TAKE_PROFIT_PCT = 0.01    # 1% profit target
BASE_CAPITAL = 100000.0
SUMMARY_INTERVAL = 60
LOOP_SLEEP = 3
DRAWDOWN_STOP_PCT = 0.05
UNITS = 100
PRICE_FILE = "price_data.json"
MIN_CROSS_DIFF = 0.001    # filter to avoid small crossover noise
# ==========================================

def read_price():
    """Read latest simulated price."""
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
    print("🤖 Moving Average Crossover — 1% Profit / 2% Loss Rule (Press 'q' to exit safely)\n")

    short_prices = deque(maxlen=SHORT_WINDOW)
    long_prices = deque(maxlen=LONG_WINDOW)

    cash = BASE_CAPITAL
    realized_pnl = 0.0
    position = 0
    entry_price = 0.0
    entry_time = ""
    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - DRAWDOWN_STOP_PCT)
    last_summary = time.time()

    trade_history = []
    collecting = True  # flag for re-collection phase

    print("⏳ Collecting price data...")

    try:
        while True:
            price = read_price()
            if price is None:
                print("⚠️ Waiting for price data...")
                time.sleep(2)
                continue

            short_prices.append(price)
            long_prices.append(price)

            # Wait until enough price data is collected
            if len(long_prices) < LONG_WINDOW:
                print(f"Collecting data... Short({len(short_prices)}/{SHORT_WINDOW}) | Long({len(long_prices)}/{LONG_WINDOW})")
                time.sleep(2)
                continue

            short_ma = np.mean(short_prices)
            long_ma = np.mean(long_prices)
            diff = short_ma - long_ma
            equity = cash + realized_pnl + (position * UNITS * (price - entry_price))

            if equity <= stop_equity:
                print("\n🚨 STOP TRIGGERED — 5% Capital Drawdown Reached.")
                break

            print(f"\n💹 Price: ₹{price:.2f} | Short MA(5): ₹{short_ma:.2f} | Long MA(12): ₹{long_ma:.2f} | Equity: ₹{equity:,.2f}")

            # ======= ENTRY LOGIC =======
            if position == 0 and not collecting:
                if diff > MIN_CROSS_DIFF:
                    entry_price = price
                    position = 1
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG ENTRY @ ₹{price:.2f} | Upward crossover | Units={UNITS}")
                elif diff < -MIN_CROSS_DIFF:
                    entry_price = price
                    position = -1
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT ENTRY @ ₹{price:.2f} | Downward crossover | Units={UNITS}")
                else:
                    print("⚪ No signal — crossover too small.")
            elif position == 0 and collecting:
                print(f"🧭 Re-collecting prices... Short({len(short_prices)}/{SHORT_WINDOW}) | Long({len(long_prices)}/{LONG_WINDOW})")
                if len(short_prices) == SHORT_WINDOW and len(long_prices) == LONG_WINDOW:
                    collecting = False
                    print("✅ Enough data collected — Ready to trade.")
                time.sleep(2)
                continue

            # ======= EXIT LOGIC =======
            elif position != 0:
                unrealized = position * UNITS * (price - entry_price)
                stop_loss = entry_price * (1 - STOP_LOSS_PCT) if position == 1 else entry_price * (1 + STOP_LOSS_PCT)
                take_profit = entry_price * (1 + TAKE_PROFIT_PCT) if position == 1 else entry_price * (1 - TAKE_PROFIT_PCT)
                current_return = (price - entry_price) / entry_price if position == 1 else (entry_price - price) / entry_price
                print(f"📊 Unrealized PnL: ₹{unrealized:,.2f}")

                # ✅ EXIT if profit >= 1%
                if current_return >= TAKE_PROFIT_PCT:
                    realized_pnl += unrealized
                    trade_type = "LONG" if position == 1 else "SHORT"
                    trade_history.append({
                        "time": entry_time,
                        "type": trade_type,
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unrealized
                    })
                    print(f"✅ EXIT @ ₹{price:.2f} | Reason: Profit Target (1%) | PnL: ₹{unrealized:,.2f}")
                    position = 0
                    collecting = True
                    short_prices.clear()
                    long_prices.clear()
                    print("🔄 Restarting collection phase...\n")

                # ❌ EXIT only if loss >= 2% (ignore minor crossover loss)
                elif current_return <= -STOP_LOSS_PCT:
                    realized_pnl += unrealized
                    trade_type = "LONG" if position == 1 else "SHORT"
                    trade_history.append({
                        "time": entry_time,
                        "type": trade_type,
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unrealized
                    })
                    print(f"❌ STOP LOSS EXIT @ ₹{price:.2f} | Reason: 2% Max Loss | PnL: ₹{unrealized:,.2f}")
                    position = 0
                    collecting = True
                    short_prices.clear()
                    long_prices.clear()
                    print("🔄 Restarting collection phase after stop loss.\n")

                # Cross-over occurs but loss < 2% → keep holding
                elif (position == 1 and diff < -MIN_CROSS_DIFF) or (position == -1 and diff > MIN_CROSS_DIFF):
                    print("⚠️ Crossover against position — monitoring until loss hits 2%.")

            # ======= PERIODIC SUMMARY =======
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = cash + realized_pnl + (position * UNITS * (price - entry_price))
                total_pnl = total_equity - start_equity
                print("\n📘 PERFORMANCE SUMMARY:")
                print(f"   Realized PnL: ₹{realized_pnl:,.2f}")
                print(f"   Total Equity: ₹{total_equity:,.2f}")
                print(f"   Net P/L: ₹{total_pnl:,.2f}")
                last_summary = time.time()

            # ======= MANUAL EXIT =======
            import msvcrt
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
