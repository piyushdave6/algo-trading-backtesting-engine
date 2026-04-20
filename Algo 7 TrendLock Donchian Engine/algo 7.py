import json
import time
import numpy as np
import sys
from collections import deque
from datetime import datetime

# =============== PARAMETERS ===============
WINDOW = 10
STOP_LOSS_PCT = 0.02
TAKE_PROFIT_PCT = 0.005
BASE_CAPITAL = 100000.0
SUMMARY_INTERVAL = 60
LOOP_SLEEP = 3
DRAWDOWN_STOP_PCT = 0.05
UNITS = 100
PRICE_FILE = "price_data.json"
MAX_RANGE_PCT = 0.03
ATR_MULTIPLIER = 6.0
ATR_FLOOR = 0.1
# ==========================================

def read_price():
    """Read latest simulated price."""
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"])
    except Exception:
        return None

def calc_atr(prices):
    """Approximate ATR using average absolute difference."""
    diffs = np.abs(np.diff(prices))
    return np.mean(diffs) if len(diffs) > 0 else 0.0

def print_trade_log(trade_history, realized_pnl):
    """Final trade history summary."""
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
    print("🤖 Donchian Channel Breakout + ATR Insight Dashboard (v6)\n")

    prices = deque(maxlen=WINDOW)
    cash = BASE_CAPITAL
    realized_pnl = 0.0
    position = 0
    entry_price = 0.0
    entry_time = ""
    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - DRAWDOWN_STOP_PCT)
    last_summary = time.time()

    trade_history = []
    collecting = True
    range_locked = False
    upper_band = lower_band = mid = None
    atr = 0.0

    print("⏳ Collecting initial price data for Donchian range and ATR...\n")

    try:
        while True:
            price = read_price()
            if price is None:
                print("⚠️ Waiting for price data...")
                time.sleep(2)
                continue

            # ========== DATA COLLECTION PHASE ==========
            if collecting:
                prices.append(price)
                print(f"Collecting data... ({len(prices)}/{WINDOW}) | Price: ₹{price:.2f}")
                if len(prices) == WINDOW:
                    upper_band = np.max(prices)
                    lower_band = np.min(prices)
                    mid = (upper_band + lower_band) / 2
                    atr = max(calc_atr(prices), ATR_FLOOR)
                    range_width = (upper_band - lower_band) / lower_band
                    range_diff = upper_band - lower_band

                    # Filter unrealistic volatility
                    if range_width > MAX_RANGE_PCT and range_diff > ATR_MULTIPLIER * atr:
                        print(f"⚠️ Range too volatile (Width={range_width:.2%}, Diff={range_diff:.2f}, ATR={atr:.2f}) — restarting...")
                        prices.clear()
                        time.sleep(3)
                        continue

                    range_locked = True
                    collecting = False
                    print("\n✅ Channel Locked!")
                    print(f"   Upper Band: ₹{upper_band:.2f}")
                    print(f"   Lower Band: ₹{lower_band:.2f}")
                    print(f"   ATR: ₹{atr:.2f}")
                    print(f"   Range Width: {range_width:.2%}")
                    print("   Waiting for breakout beyond locked range...\n")
                time.sleep(2)
                continue

            # ========== TRADING PHASE ==========
            atr_live = max(calc_atr(prices), ATR_FLOOR)
            equity = cash + realized_pnl + (position * UNITS * (price - entry_price))

            if equity <= stop_equity:
                print("\n🚨 STOP TRIGGERED — 5% Capital Drawdown Reached.")
                break

            # Dynamic output
            print(f"\n💹 Price: ₹{price:.2f} | Range: ₹{lower_band:.2f}–₹{upper_band:.2f} | ATR: ₹{atr_live:.2f} | Equity: ₹{equity:,.2f}")

            # ===== ENTRY LOGIC =====
            if position == 0:
                if price > upper_band:
                    position = 1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG ENTRY @ ₹{price:.2f} | Above ₹{upper_band:.2f} | Units={UNITS}")
                elif price < lower_band:
                    position = -1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT ENTRY @ ₹{price:.2f} | Below ₹{lower_band:.2f} | Units={UNITS}")
                else:
                    print("⚪ No breakout — price within locked range.")

            # ===== EXIT LOGIC =====
            elif position != 0:
                unrealized = position * UNITS * (price - entry_price)
                stop_loss = entry_price * (1 - STOP_LOSS_PCT) if position == 1 else entry_price * (1 + STOP_LOSS_PCT)
                take_profit = entry_price * (1 + TAKE_PROFIT_PCT) if position == 1 else entry_price * (1 - TAKE_PROFIT_PCT)

                side = "LONG" if position == 1 else "SHORT"
                print(f"📊 Position: {side} @ ₹{entry_price:.2f} | Unrealized PnL: ₹{unrealized:,.2f}")

                # Profit exit
                if (position == 1 and price >= take_profit) or (position == -1 and price <= take_profit):
                    realized_pnl += unrealized
                    trade_history.append({
                        "time": entry_time,
                        "type": side,
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unrealized
                    })
                    print(f"✅ EXIT @ ₹{price:.2f} | Reason: Profit (0.5%) | PnL: ₹{unrealized:,.2f}")
                    position = 0
                    prices.clear()
                    collecting = True
                    range_locked = False
                    print("\n🔄 Restarting new channel collection...\n")

                # Stop-loss exit
                elif (position == 1 and price <= stop_loss) or (position == -1 and price >= stop_loss):
                    realized_pnl += unrealized
                    trade_history.append({
                        "time": entry_time,
                        "type": side,
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unrealized
                    })
                    print(f"❌ STOP LOSS EXIT @ ₹{price:.2f} | Reason: 2% Loss | PnL: ₹{unrealized:,.2f}")
                    position = 0
                    prices.clear()
                    collecting = True
                    range_locked = False
                    print("\n🔄 Restarting new channel collection...\n")

            # ===== SUMMARY =====
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = cash + realized_pnl + (position * UNITS * (price - entry_price))
                total_pnl = total_equity - start_equity
                print("\n📘 PERFORMANCE SUMMARY:")
                print(f"   Realized PnL: ₹{realized_pnl:,.2f}")
                print(f"   Total Equity: ₹{total_equity:,.2f}")
                print(f"   Net P/L: ₹{total_pnl:,.2f}")
                last_summary = time.time()

            # Manual exit key
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
