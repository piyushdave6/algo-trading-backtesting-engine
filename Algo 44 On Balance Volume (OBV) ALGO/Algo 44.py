import json
import time
import numpy as np
from collections import deque
from datetime import datetime

# ================= PARAMETERS =================
OBV_LOOKBACK = 6
BASE_CAPITAL = 100000.0
UNITS = 100
STOP_DRAWDOWN_PCT = 0.05
SUMMARY_INTERVAL = 100
LOOP_SLEEP = 4
PRICE_FILE = "price_data.json"
TAKE_PROFIT_PCT = 0.005       # +0.5%
STOP_LOSS_PCT = 0.010         # -1%
# ==============================================


def read_tick():
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"]), float(data["volume"])
    except:
        return None, None


def print_final_report(trades, realized, start_equity):
    print("\n\n📘 FINAL FULL SESSION REPORT")
    print("=" * 80)

    total_trades = len(trades)
    wins = len([t for t in trades if t['pnl'] > 0])
    losses = total_trades - wins
    largest_win = max([t['pnl'] for t in trades], default=0)
    largest_loss = min([t['pnl'] for t in trades], default=0)
    final_equity = start_equity + realized

    print(f"Total Trades Executed: {total_trades}")
    print(f"Wins: {wins} | Losses: {losses}")
    print(f"Win Rate: {wins / total_trades * 100 if total_trades > 0 else 0:.2f}%")
    print(f"Largest Win: ₹{largest_win:,.2f}")
    print(f"Largest Loss: ₹{largest_loss:,.2f}")
    print(f"Realized PnL: ₹{realized:,.2f}")
    print(f"Final Equity: ₹{final_equity:,.2f}")
    print("=" * 80)

    print("\n🧾 TRADE HISTORY")
    print("-" * 80)
    print(f"{'Time':<20} {'Type':<8} {'Entry':<10} {'Exit':<10} {'PnL (₹)':<10}")
    print("-" * 80)
    for t in trades:
        print(f"{t['time']:<20} {t['type']:<8} {t['entry']:<10.2f} {t['exit']:<10.2f} {t['pnl']:<10.2f}")
    print("-" * 80)


def main():
    print("🤖 Starting OBV Reversion Pro v1 — Full PnL Summary System Enabled\n")

    prices = deque(maxlen=OBV_LOOKBACK + 1)
    volumes = deque(maxlen=OBV_LOOKBACK + 1)
    obv_series = deque(maxlen=OBV_LOOKBACK + 1)

    obv = 0
    realized_pnl = 0.0
    position = 0
    entry_price = 0.0
    entry_time = ""

    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - STOP_DRAWDOWN_PCT)
    last_summary = time.time()
    trade_history = []

    print(f"⏳ Collecting {OBV_LOOKBACK + 1} ticks before activation...")

    try:
        while True:

            price, volume = read_tick()
            if price is None:
                print("⚠️ Waiting for price...")
                time.sleep(2)
                continue

            prices.append(price)
            volumes.append(volume)

            if len(prices) > 1:
                if prices[-1] > prices[-2]:
                    obv += volume
                elif prices[-1] < prices[-2]:
                    obv -= volume

            obv_series.append(obv)

            if len(obv_series) < OBV_LOOKBACK + 1:
                print(f"Collecting data... ({len(obv_series)}/{OBV_LOOKBACK + 1})")
                time.sleep(2)
                continue

            obv_slope = obv_series[-1] - obv_series[-2]
            close = prices[-1]

            unrealized = position * UNITS * (close - entry_price)
            equity = start_equity + realized_pnl + unrealized

            print(f"\n💹 Price: ₹{close:.2f} | OBV: {obv}")
            print(f"   → Realized PnL: ₹{realized_pnl:,.2f}")
            print(f"   → Unrealized PnL: ₹{unrealized:,.2f}")

            if equity <= stop_equity:
                print("\n🚨 STOP triggered: 5% capital lost.")
                break

            # ENTRY
            if position == 0:
                if obv_slope > 0:
                    position = 1
                    entry_price = close
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG Entry (OBV rising) @ ₹{close:.2f}")

                elif obv_slope < 0:
                    position = -1
                    entry_price = close
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT Entry (OBV falling) @ ₹{close:.2f}")

                else:
                    print("⚪ No entry — OBV flat.")

            else:
                pct_change = (close - entry_price) / entry_price * (1 if position == 1 else -1)
                print(f"📊 Unrealized Change: {pct_change:+.2%}")

                exit_trade = False
                exit_reason = ""

                if pct_change >= TAKE_PROFIT_PCT:
                    exit_trade = True
                    exit_reason = "Take Profit Hit"

                elif pct_change <= -STOP_LOSS_PCT:
                    exit_trade = True
                    exit_reason = "Stop Loss Hit"

                elif (position == 1 and obv_slope < 0) or (position == -1 and obv_slope > 0):
                    exit_trade = True
                    exit_reason = "OBV Reversal"

                if exit_trade:
                    realized_pnl += unrealized
                    trade_history.append({
                        "time": entry_time,
                        "type": "LONG" if position == 1 else "SHORT",
                        "entry": entry_price,
                        "exit": close,
                        "pnl": unrealized
                    })

                    print(f"🔴 EXIT @ ₹{close:.2f} | {exit_reason} | PnL: ₹{unrealized:,.2f}")
                    position = 0

            if time.time() - last_summary >= SUMMARY_INTERVAL:
                print("\n📘 100-SEC PERFORMANCE SUMMARY")
                print("=" * 40)
                print(f"Realized PnL: ₹{realized_pnl:,.2f}")
                print(f"Unrealized PnL: ₹{unrealized:,.2f}")
                print(f"Total Equity: ₹{equity:,.2f}")
                print(f"Total Trades: {len(trade_history)}")
                print("=" * 40)
                last_summary = time.time()

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user (Ctrl+C). Generating final report...\n")

    finally:
        print_final_report(trade_history, realized_pnl, start_equity)


if __name__ == "__main__":
    main()
