import json
import time
import numpy as np
import sys
from collections import deque
from datetime import datetime

# =============== PARAMETERS ==================
WINDOW = 20                # number of prices to collect before locking
PADDING_MULT = 0.5         # padding = ATR * multiplier (dynamic)
MIN_PADDING = 0.1          # minimum padding in price units
TAKE_PROFIT_PCT = 0.005    # 0.5% profit target
STOP_LOSS_PCT = 0.02       # 2% stop loss
BASE_CAPITAL = 100000.0
SUMMARY_INTERVAL = 100
LOOP_SLEEP = 3
DRAWDOWN_STOP_PCT = 0.05
UNITS = 100
PRICE_FILE = "price_data.json"
# ==============================================

def read_price():
    """Reads the latest simulated price from price_data.json"""
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"])
    except Exception:
        return None

def calc_atr(prices):
    """Simplified ATR = average absolute price change"""
    if len(prices) < 2:
        return 0.0
    diffs = np.abs(np.diff(prices))
    return float(np.mean(diffs))

def print_trade_log(trade_history, realized_pnl):
    """Display trade history when algo stops"""
    print("\n📘 FINAL TRADE HISTORY")
    print("-" * 75)
    print(f"{'Time':<20} {'Type':<8} {'Entry':<10} {'Exit':<10} {'PnL (₹)':<12}")
    print("-" * 75)
    for t in trade_history:
        print(f"{t['time']:<20} {t['type']:<8} {t['entry']:<10.2f} {t['exit']:<10.2f} {t['pnl']:<12.2f}")
    print("-" * 75)
    print(f"Total Realized PnL: ₹{realized_pnl:,.2f}")
    print("-" * 75)

def main():
    print("🤖 Smart Range Breakout — Dynamic Volatility-Adaptive Version\n")
    prices = deque(maxlen=WINDOW)
    trade_history = []
    cash = BASE_CAPITAL
    realized_pnl = 0.0
    position = 0
    entry_price = 0.0
    entry_time = ""
    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - DRAWDOWN_STOP_PCT)
    last_summary = time.time()

    collecting = True
    upper_band = lower_band = None
    padding = 0.0

    try:
        while True:
            price = read_price()
            if price is None:
                print("⚠️ Waiting for price data...")
                time.sleep(2)
                continue

            prices.append(price)

            # ========== COLLECTION PHASE ==========
            if collecting:
                atr_live = calc_atr(list(prices))
                print(f"📥 Collecting data ({len(prices)}/{WINDOW}) | Price: ₹{price:.2f} | ATR so far: ₹{atr_live:.4f}")

                if len(prices) < WINDOW:
                    time.sleep(2)
                    continue

                # Once we have 20 readings:
                raw_upper = max(prices)
                raw_lower = min(prices)
                atr_final = calc_atr(list(prices))
                padding = max(MIN_PADDING, atr_final * PADDING_MULT)

                # compute padded bands
                upper_band = raw_upper + padding
                lower_band = raw_lower - padding
                range_pct = (upper_band - lower_band) / price

                print("\n🔒 CHANNEL LOCKED — 20 readings complete")
                print(f"   Highest Price (Upper Boundary): ₹{raw_upper:.2f}")
                print(f"   Lowest Price (Lower Boundary): ₹{raw_lower:.2f}")
                print(f"   Final ATR: ₹{atr_final:.4f}")
                print(f"   Padding Applied (ATR × {PADDING_MULT}): ₹{padding:.4f}")
                print(f"   Padded Range: ₹{lower_band:.2f} — ₹{upper_band:.2f}")
                print(f"   Total Range Width: {range_pct*100:.2f}%\n")

                collecting = False
                continue

            # ========== TRADING PHASE ==========
            equity = cash + realized_pnl + (position * UNITS * (price - entry_price) if position != 0 else 0.0)
            if equity <= stop_equity:
                print("\n🚨 STOP — overall drawdown exceeded. Exiting.")
                break

            atr_now = calc_atr(list(prices))
            print(f"\n💹 Price: ₹{price:.2f} | Range: ₹{lower_band:.2f}–₹{upper_band:.2f} | ATR: ₹{atr_now:.4f} | Equity: ₹{equity:,.2f}")

            # ENTRY
            if position == 0:
                if price > upper_band:
                    position = 1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG ENTRY @ ₹{price:.2f} | Units={UNITS}")
                elif price < lower_band:
                    position = -1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT ENTRY @ ₹{price:.2f} | Units={UNITS}")
                else:
                    print("⚪ Waiting for breakout beyond adaptive range.")
            else:
                # Manage open position
                unrealized = position * UNITS * (price - entry_price)
                print(f"📊 Position: {'LONG' if position==1 else 'SHORT'} @ ₹{entry_price:.2f} | Unrealized PnL: ₹{unrealized:,.2f}")

                # compute target and stop
                if position == 1:
                    profit_price = entry_price * (1 + TAKE_PROFIT_PCT)
                    stop_price = entry_price * (1 - STOP_LOSS_PCT)
                    hit_profit = price >= profit_price
                    hit_stop = price <= stop_price
                else:
                    profit_price = entry_price * (1 - TAKE_PROFIT_PCT)
                    stop_price = entry_price * (1 + STOP_LOSS_PCT)
                    hit_profit = price <= profit_price
                    hit_stop = price >= stop_price

                if hit_profit:
                    realized_pnl += unrealized
                    trade_history.append({"time": entry_time, "type": "LONG" if position==1 else "SHORT",
                                          "entry": entry_price, "exit": price, "pnl": unrealized})
                    print(f"✅ PROFIT BOOKED @ ₹{price:.2f} | PnL: ₹{unrealized:,.2f}")
                    position = 0
                    prices.clear()
                    collecting = True
                elif hit_stop:
                    realized_pnl += unrealized
                    trade_history.append({"time": entry_time, "type": "LONG" if position==1 else "SHORT",
                                          "entry": entry_price, "exit": price, "pnl": unrealized})
                    print(f"❌ STOP LOSS @ ₹{price:.2f} | PnL: ₹{unrealized:,.2f}")
                    position = 0
                    prices.clear()
                    collecting = True

            # periodic summary
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = cash + realized_pnl + (position * UNITS * (price - entry_price) if position!=0 else 0.0)
                print("\n📘 SUMMARY (100s):")
                print(f"   Realized PnL: ₹{realized_pnl:,.2f}")
                print(f"   Total Equity: ₹{total_equity:,.2f}")
                last_summary = time.time()

            # manual exit
            try:
                import msvcrt
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode().lower()
                    if key == 'q':
                        print("\n🛑 Manual exit requested (q).")
                        break
            except Exception:
                pass

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user (Ctrl+C).")

    finally:
        print_trade_log(trade_history, realized_pnl)
        print("✅ Algo stopped safely.\n")

if __name__ == "__main__":
    main()
