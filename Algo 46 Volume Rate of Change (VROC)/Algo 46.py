import json
import time
import numpy as np
import sys
from collections import deque
from datetime import datetime

# ================= PARAMETERS =================
VROC_LOOKBACK = 5
RANGE_LOOKBACK = 5

BASE_CAPITAL = 100000.0
UNITS = 100

STOP_DRAWDOWN_PCT = 0.05
SUMMARY_INTERVAL = 100        # 100-sec summary
LOOP_SLEEP = 3

PRICE_FILE = "price_data.json"

TAKE_PROFIT_PCT = 0.020       # +2%
STOP_LOSS_PCT = 0.010         # -1%

VROC_THRESHOLD = 40           # volume expansion trigger
# ==============================================


def read_price_volume():
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"]), float(data["volume"])
    except:
        return None, None


def compute_vroc(volumes, lookback):
    if len(volumes) < lookback + 1:
        return None
    return (volumes[-1] - volumes[0]) / volumes[0] * 100


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

    print("\n✔ Algo stopped safely.\n")


def main():
    print("🤖 Starting VROC Breakout Pro v2 — Full PnL Summary System Enabled\n")

    prices = deque(maxlen=RANGE_LOOKBACK)
    volumes = deque(maxlen=VROC_LOOKBACK + 1)

    realized_pnl = 0.0
    position = 0
    entry_price = 0.0
    entry_time = ""

    priming = False
    range_high = None
    range_low = None

    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - STOP_DRAWDOWN_PCT)
    last_summary = time.time()
    trade_history = []

    print(f"⏳ Collecting {VROC_LOOKBACK + 1} ticks before activation...")

    try:
        while True:

            price, volume = read_price_volume()
            if price is None:
                print("⚠️ Waiting for price...")
                time.sleep(2)
                continue

            prices.append(price)
            volumes.append(volume)

            if len(volumes) < VROC_LOOKBACK + 1:
                print(f"Collecting data... ({len(volumes)}/{VROC_LOOKBACK + 1})")
                time.sleep(2)
                continue

            vroc = compute_vroc(list(volumes), VROC_LOOKBACK)
            close = prices[-1]

            unrealized = position * UNITS * (close - entry_price)
            equity = start_equity + realized_pnl + unrealized

            print(f"\n💹 Price: ₹{close:.2f} | VROC: {vroc:.2f}%")
            print(f"   → Realized PnL: ₹{realized_pnl:,.2f}")
            print(f"   → Unrealized PnL: ₹{unrealized:,.2f}")

            if equity <= stop_equity:
                print("\n🚨 STOP triggered: 5% capital lost.")
                break

            # ---------------- ENTRY ----------------
            if position == 0:

                prange = max(prices) - min(prices)
                tight = prange < close * 0.006

                if not priming and vroc > VROC_THRESHOLD and (tight or vroc > 70):
                    priming = True
                    range_high = max(prices)
                    range_low = min(prices)
                    print(f"🟡 VOLUME PRIMING | Range {range_low}–{range_high}")

                elif priming and close > range_high:
                    position = 1
                    entry_price = close
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG Entry (Breakout) @ ₹{close:.2f}")

                elif priming and close < range_low:
                    position = -1
                    entry_price = close
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT Entry (Breakdown) @ ₹{close:.2f}")

                else:
                    print("⚪ No entry — waiting for breakout.")

            # ---------------- EXIT ----------------
            else:
                pct_change = (close - entry_price) / entry_price * (1 if position == 1 else -1)
                print(f"📊 Unrealized Change: {pct_change:+.2%}")

                exit_trade = False
                exit_reason = ""

                if pct_change >= TAKE_PROFIT_PCT:
                    exit_trade = True
                    exit_reason = "2% Target Achieved"

                elif pct_change <= -STOP_LOSS_PCT:
                    exit_trade = True
                    exit_reason = "Stop Loss Hit"

                elif vroc < 0:
                    exit_trade = True
                    exit_reason = "VROC Reversal"

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
                    priming = False

            # -------- SUMMARY --------
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
