import json
import time
import numpy as np
import sys
from collections import deque
from datetime import datetime

# ================= PARAMETERS =================
RSI_PERIOD = 14
BASE_CAPITAL = 100000.0
UNITS = 100
STOP_DRAWDOWN_PCT = 0.05
SUMMARY_INTERVAL = 100        # <── 100-sec summary
LOOP_SLEEP =3
PRICE_FILE = "price_data.json"
TAKE_PROFIT_PCT = 0.005       # +0.5%
STOP_LOSS_PCT = 0.010        # -1%
# ==============================================


def read_price():
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"])
    except:
        return None


def compute_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


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
    print("🤖 Starting RSI Reversion Pro v2 — Full PnL Summary System Enabled\n")

    prices = deque(maxlen=RSI_PERIOD + 1)
    realized_pnl = 0.0
    position = 0
    entry_price = 0.0
    entry_time = ""

    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - STOP_DRAWDOWN_PCT)
    last_summary = time.time()
    trade_history = []

    print(f"⏳ Collecting {RSI_PERIOD + 1} prices before activation...")

    try:
        while True:

            price = read_price()
            if price is None:
                print("⚠️ Waiting for price...")
                time.sleep(2)
                continue

            prices.append(price)
            if len(prices) < RSI_PERIOD + 1:
                print(f"Collecting data... ({len(prices)}/{RSI_PERIOD + 1})")
                time.sleep(2)
                continue

            rsi = compute_rsi(list(prices), RSI_PERIOD)
            close = prices[-1]

            # Unrealized PnL (even when no trade)
            unrealized = position * UNITS * (close - entry_price)
            equity = start_equity + realized_pnl + unrealized

            # Show every cycle PnL
            print(f"\n💹 Price: ₹{close:.2f} | RSI: {rsi:.2f}")
            print(f"   → Realized PnL: ₹{realized_pnl:,.2f}")
            print(f"   → Unrealized PnL: ₹{unrealized:,.2f}")
            
            if equity <= stop_equity:
                print("\n🚨 STOP triggered: 5% capital lost.")
                break

            # ENTRY
            if position == 0:

                if rsi < 30:
                    position = 1
                    entry_price = close
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG Entry (RSI {rsi:.2f}) @ ₹{close:.2f}")

                elif rsi > 70:
                    position = -1
                    entry_price = close
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT Entry (RSI {rsi:.2f}) @ ₹{close:.2f}")

                else:
                    print("⚪ No entry — RSI not in signal zone.")

            else:
                # If position is open
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

                elif (position == 1 and rsi > 50) or (position == -1 and rsi < 50):
                    exit_trade = True
                    exit_reason = "RSI Mean Reversion"

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

            # 100-sec performance summary
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
