import json
import time
import numpy as np
import sys
from collections import deque
from datetime import datetime
import msvcrt  # windows keypress

# =============== PARAMETERS ===============
FAST = 5
MID = 10
SLOW = 20

TAKE_PROFIT_PCT = 0.005     # +0.50%
STOP_LOSS_PCT  = 0.01       # -1.00%

BASE_CAPITAL = 100000.0
SUMMARY_INTERVAL = 100
LOOP_SLEEP = 2.5
DRAWDOWN_STOP_PCT = 0.05
UNITS = 100
PRICE_FILE = "price_data.json"
# ==========================================


def read_price():
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"])
    except Exception:
        return None


def print_trade_log(trade_history, realized_pnl):
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

    print("🤖 Starting MA Ribbon Breakout Algo — Fixed TP/SL\n")

    prices = deque(maxlen=SLOW)
    cash = BASE_CAPITAL
    realized_pnl = 0.0
    position = 0
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

            if len(prices) < SLOW:
                print(f"Collecting data... ({len(prices)}/{SLOW})")
                time.sleep(2)
                continue

            fast = np.mean(list(prices)[-FAST:])
            mid  = np.mean(list(prices)[-MID:])
            slow = np.mean(prices)

            equity = cash + realized_pnl + (position * UNITS * (price - entry_price))

            if equity <= stop_equity:
                print("\n🚨 STOP TRIGGERED — 5% Capital Drawdown Reached.")
                break

            print(f"\n💹 Price: ₹{price:.2f} | FAST={fast:.2f} | MID={mid:.2f} | SLOW={slow:.2f} | Equity=₹{equity:,.2f}")

            # -------- ENTRY LOGIC (Ribbon Alignment) --------
            long_signal  = fast > mid > slow
            short_signal = fast < mid < slow

            if position == 0:

                if long_signal:
                    position = 1
                    entry_price = price
                    entry_time  = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG ENTRY @ ₹{price:.2f} — Ribbon Aligned UP | Units={UNITS}")

                elif short_signal:
                    position = -1
                    entry_price = price
                    entry_time  = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT ENTRY @ ₹{price:.2f} — Ribbon Aligned DOWN | Units={UNITS}")

                else:
                    print("⚪ No alignment — no trade.")

            else:
                # -------- EXIT LOGIC (Take Profit / Stop Loss) --------
                unreal = position * UNITS * (price - entry_price)

                print(f"📊 Unrealized: ₹{unreal:,.2f} | Realized: ₹{realized_pnl:,.2f}")

                # Calculate TP & SL
                tp_price = entry_price * (1 + TAKE_PROFIT_PCT if position == 1 else 1 - TAKE_PROFIT_PCT)
                sl_price = entry_price * (1 - STOP_LOSS_PCT  if position == 1 else 1 + STOP_LOSS_PCT)

                hit_tp = (position == 1 and price >= tp_price) or (position == -1 and price <= tp_price)
                hit_sl = (position == 1 and price <= sl_price) or (position == -1 and price >= sl_price)

                if hit_tp:
                    realized_pnl += unreal
                    trade_history.append({
                        "time": entry_time,
                        "type": "LONG" if position == 1 else "SHORT",
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unreal
                    })
                    print(f"🏆 TAKE PROFIT EXIT @ ₹{price:.2f} | PnL: ₹{unreal:,.2f}")
                    position = 0

                elif hit_sl:
                    realized_pnl += unreal
                    trade_history.append({
                        "time": entry_time,
                        "type": "LONG" if position == 1 else "SHORT",
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unreal
                    })
                    print(f"❌ STOP LOSS EXIT @ ₹{price:.2f} | PnL: ₹{unreal:,.2f}")
                    position = 0

            # ---- periodic summary ----
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = cash + realized_pnl + (position * UNITS * (price - entry_price))
                total_pnl = total_equity - start_equity
                print("\n📘 PERFORMANCE SUMMARY (100s):")
                print(f"   Realized PnL: ₹{realized_pnl:,.2f}")
                print(f"   Total Equity: ₹{total_equity:,.2f}")
                print(f"   Net P/L: ₹{total_pnl:,.2f}")
                last_summary = time.time()

            # manual exit
            if msvcrt.kbhit():
                if msvcrt.getch().decode("utf-8").lower() == "q":
                    print("\n🛑 Manual exit (q).")
                    break

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Manual stop (Ctrl+C).")

    finally:
        print_trade_log(trade_history, realized_pnl)
        print("✅ Algo stopped safely.\n")


if __name__ == "__main__":
    main()
