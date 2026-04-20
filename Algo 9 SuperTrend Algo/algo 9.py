import json
import time
import numpy as np
import sys
from collections import deque
from datetime import datetime

# ================= PARAMETERS =================
WINDOW = 20
MULT = 3.0
BASE_CAPITAL = 100000.0
UNITS = 100
STOP_DRAWDOWN_PCT = 0.05
SUMMARY_INTERVAL = 60
LOOP_SLEEP = 5
PRICE_FILE = "price_data.json"
TAKE_PROFIT_PCT = 0.005   # +0.5%
STOP_LOSS_PCT = 0.005     # -0.5%
# ==============================================

def read_price():
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"])
    except:
        return None

def calc_atr(prices):
    if len(prices) < 2:
        return 0.0
    diffs = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
    return np.mean(diffs)

def print_trade_log(trades, realized_pnl):
    print("\n📘 FINAL TRADE HISTORY")
    print("-" * 75)
    print(f"{'Time':<20} {'Type':<8} {'Entry':<10} {'Exit':<10} {'PnL (₹)':<10}")
    print("-" * 75)
    for t in trades:
        print(f"{t['time']:<20} {t['type']:<8} "
              f"{t['entry']:<10.2f} {t['exit']:<10.2f} {t['pnl']:<10.2f}")
    print("-" * 75)
    print(f"Total Realized PnL: ₹{realized_pnl:,.2f}")
    print("-" * 75)

def main():
    print("🤖 Starting SuperTrend Pro v2 — Dual Range Logic\n")

    prices = deque(maxlen=WINDOW)
    cash = BASE_CAPITAL
    realized_pnl = 0.0
    position = 0
    entry_price = 0.0
    entry_time = ""
    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - STOP_DRAWDOWN_PCT)
    last_summary = time.time()
    trade_history = []

    trend = None
    prev_upper_band = prev_lower_band = prev_supertrend = None

    print("⏳ Collecting 20 prices before activation...")

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

            high = max(prices)
            low = min(prices)
            close = prices[-1]
            hl2 = (high + low) / 2
            atr = calc_atr(list(prices))

            upper_basic = hl2 + MULT * atr
            lower_basic = hl2 - MULT * atr

            if trend == "up" and prev_upper_band is not None:
                upper_band = min(upper_basic, prev_upper_band)
            else:
                upper_band = upper_basic

            if trend == "down" and prev_lower_band is not None:
                lower_band = max(lower_basic, prev_lower_band)
            else:
                lower_band = lower_basic

            if prev_supertrend is None:
                supertrend = hl2
                trend = "up" if close > hl2 else "down"
                reason = "initial trend detection"
            else:
                if close > prev_supertrend:
                    new_trend = "up"
                    reason = "close > previous SuperTrend"
                else:
                    new_trend = "down"
                    reason = "close < previous SuperTrend"

                if new_trend != trend:
                    print(f"\n⚠️ Trend Change → {new_trend.upper()} ({reason})")
                    trend = new_trend

                if trend == "up":
                    supertrend = lower_band
                else:
                    supertrend = upper_band

            prev_upper_band = upper_band
            prev_lower_band = lower_band
            prev_supertrend = supertrend

            equity = cash + realized_pnl + position * UNITS * (price - entry_price)
            if equity <= stop_equity:
                print("\n🚨 STOP TRIGGERED — 5% capital loss limit reached.")
                break

            # Print continuous status
            print(f"\n💹 Price: ₹{price:.2f} | Trend: {trend.upper()} | ATR: ₹{atr:.2f}")
            print(f"   → Range: ₹{lower_band:.2f} – ₹{upper_band:.2f}")
            print(f"   → SuperTrend: ₹{supertrend:.2f} | Equity: ₹{equity:,.2f}")

            long_trigger = lower_band
            short_trigger = upper_band
            print(f"   → Next LONG trigger: ₹{long_trigger:.2f} | Next SHORT trigger: ₹{short_trigger:.2f}")

            if position != 0:
                print(f"   → Current Position: {'LONG' if position == 1 else 'SHORT'} @ ₹{entry_price:.2f}")

            # ENTRY
            if position == 0:
                if trend == "up" and close > supertrend:
                    position = 1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG ENTRY @ ₹{price:.2f} | SuperTrend ₹{supertrend:.2f} | ATR ₹{atr:.2f}")
                elif trend == "down" and close < supertrend:
                    position = -1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT ENTRY @ ₹{price:.2f} | SuperTrend ₹{supertrend:.2f} | ATR ₹{atr:.2f}")
                else:
                    print("⚪ No trade — watching range.")
            else:
                unrealized = position * UNITS * (price - entry_price)
                pct_change = (price - entry_price) / entry_price * (1 if position == 1 else -1)
                print(f"📊 Unrealized PnL: ₹{unrealized:,.2f} | Change: {pct_change:+.2%}")

                # Check exits
                if pct_change >= TAKE_PROFIT_PCT:
                    realized_pnl += unrealized
                    trade_type = "LONG" if position == 1 else "SHORT"
                    trade_history.append({
                        "time": entry_time,
                        "type": trade_type,
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unrealized
                    })
                    print(f"✅ PROFIT BOOKED (+0.5%) @ ₹{price:.2f} | PnL: ₹{unrealized:,.2f}")
                    position = 0
                elif pct_change <= -STOP_LOSS_PCT:
                    realized_pnl += unrealized
                    trade_type = "LONG" if position == 1 else "SHORT"
                    trade_history.append({
                        "time": entry_time,
                        "type": trade_type,
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unrealized
                    })
                    print(f"❌ STOP LOSS (-0.5%) @ ₹{price:.2f} | PnL: ₹{unrealized:,.2f}")
                    position = 0

            # Summary
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = cash + realized_pnl + position * UNITS * (price - entry_price)
                total_pnl = total_equity - start_equity
                print("\n📘 PERFORMANCE SUMMARY:")
                print(f"   Realized PnL: ₹{realized_pnl:,.2f}")
                print(f"   Total Equity: ₹{total_equity:,.2f}")
                print(f"   Net P/L: ₹{total_pnl:,.2f}")
                last_summary = time.time()

            # Manual exit
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
