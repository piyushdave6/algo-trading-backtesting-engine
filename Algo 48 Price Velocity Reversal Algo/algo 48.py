# ============================================================
# ALGO-12 : PRICE VELOCITY REVERSAL ALGO
# ============================================================

import json
import time
import numpy as np
from collections import deque
from datetime import datetime

# ================= PARAMETERS =================
BASE_CAPITAL = 100000.0
UNITS = 100
STOP_DRAWDOWN_PCT = 0.05

VELOCITY_WINDOW = 3           # small for fast reaction
VELOCITY_THRESHOLD = 2.0      # minimum momentum
TAKE_PROFIT_PCT = 0.005       # +0.5%
STOP_LOSS_PCT = 0.010         # -1%

SUMMARY_INTERVAL = 100
LOOP_SLEEP = 3
PRICE_FILE = "price_data.json"
# ==============================================


def read_price():
    try:
        with open(PRICE_FILE, "r") as f:
            return float(json.load(f)["price"])
    except:
        return None


def print_final_report(trades, realized, start_equity):
    print("\n\n📘 FINAL FULL SESSION REPORT")
    print("=" * 80)

    total_trades = len(trades)
    wins = len([t for t in trades if t['pnl'] > 0])
    losses = total_trades - wins
    final_equity = start_equity + realized

    print(f"Total Trades: {total_trades}")
    print(f"Wins / Losses: {wins} / {losses}")
    print(f"Win Rate: {wins/total_trades*100 if total_trades else 0:.2f}%")
    print(f"Realized PnL: ₹{realized:,.2f}")
    print(f"Final Equity: ₹{final_equity:,.2f}")

    print("\n🧾 TRADE LOG")
    print("-"*80)
    for t in trades:
        print(t)
    print("-"*80)


def main():
    print("🤖 Starting PRICE VELOCITY REVERSAL ALGO\n")

    prices = deque(maxlen=VELOCITY_WINDOW + 2)
    position = 0
    entry_price = 0.0
    entry_time = ""

    realized_pnl = 0.0
    trade_history = []

    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - STOP_DRAWDOWN_PCT)
    last_summary = time.time()

    try:
        while True:
            price = read_price()
            if price is None:
                time.sleep(2)
                continue

            prices.append(price)
            if len(prices) < VELOCITY_WINDOW + 2:
                time.sleep(2)
                continue

            # -------- PRICE DYNAMICS --------
            velocity = prices[-1] - prices[-2]
            prev_velocity = prices[-2] - prices[-3]
            acceleration = velocity - prev_velocity

            unrealized = position * UNITS * (price - entry_price)
            equity = start_equity + realized_pnl + unrealized

            print(f"\n💹 Price: ₹{price:.2f}")
            print(f"Velocity: {velocity:+.2f} | Acceleration: {acceleration:+.2f}")
            print(f"Realized: ₹{realized_pnl:,.2f} | Unrealized: ₹{unrealized:,.2f}")

            if equity <= stop_equity:
                print("🚨 Capital Stop Hit")
                break

            # ---------------- ENTRY ----------------
            if position == 0:
                # LONG: selling exhaustion
                if velocity < -VELOCITY_THRESHOLD and acceleration > 0:
                    position = 1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG @ ₹{price:.2f} (Velocity Reversal)")

                # SHORT: buying exhaustion
                elif velocity > VELOCITY_THRESHOLD and acceleration < 0:
                    position = -1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT @ ₹{price:.2f} (Velocity Reversal)")

            # ---------------- EXIT ----------------
            else:
                pct_change = (price - entry_price) / entry_price * (1 if position == 1 else -1)

                exit_trade = False
                reason = ""

                if pct_change >= TAKE_PROFIT_PCT:
                    exit_trade = True
                    reason = "Take Profit"

                elif pct_change <= -STOP_LOSS_PCT:
                    exit_trade = True
                    reason = "Stop Loss"

                elif (position == 1 and velocity > 0) or (position == -1 and velocity < 0):
                    exit_trade = True
                    reason = "Velocity Flip"

                if exit_trade:
                    realized_pnl += unrealized
                    trade_history.append({
                        "time": entry_time,
                        "type": "LONG" if position == 1 else "SHORT",
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unrealized
                    })
                    print(f"🔴 EXIT @ ₹{price:.2f} | {reason} | PnL: ₹{unrealized:,.2f}")
                    position = 0

            # -------- SUMMARY --------
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                print("\n📘 100-SEC SUMMARY")
                print(f"Equity: ₹{equity:,.2f} | Trades: {len(trade_history)}")
                last_summary = time.time()

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted")

    finally:
        print_final_report(trade_history, realized_pnl, start_equity)


if __name__ == "__main__":
    main()
