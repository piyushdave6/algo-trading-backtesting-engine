import json
import time
import numpy as np
from collections import deque
from datetime import datetime
import msvcrt   # for Windows key detection

# =============== PARAMETERS ===============
HMA_FAST_LEN = 9
HMA_SLOW_LEN = 21

TAKE_PROFIT_PCT = 0.005     # +0.5%
STOP_LOSS_PCT  = 0.01       # -1%

BASE_CAPITAL = 100000.0
SUMMARY_INTERVAL = 100
LOOP_SLEEP = 2
DRAWDOWN_STOP_PCT = 0.05
UNITS = 100
PRICE_FILE = "price_data.json"
# ==========================================


# ---------- Hull MA Calculation ----------
def wma(values, period):
    weights = np.arange(1, period + 1)
    return np.dot(values[-period:], weights) / weights.sum()


def hull_ma(values, period):
    if len(values) < period:
        return None

    half = period // 2
    sqrt_len = int(np.sqrt(period))

    wma_half = wma(values, half)
    wma_full = wma(values, period)

    hull_series = 2 * wma_half - wma_full

    if sqrt_len <= 0:
        return None

    temp = np.array([hull_series] * sqrt_len)
    return wma(temp, sqrt_len)


# ---------- Read Price ----------
def read_price():
    try:
        with open(PRICE_FILE, "r") as f:
            return float(json.load(f)["price"])
    except:
        return None


# ---------- Print Final Trades ----------
def print_trade_log(trade_history, realized_pnl):
    print("\n📘 FINAL TRADE HISTORY")
    print("-" * 70)
    print(f"{'Time':<20} {'Type':<8} {'Entry':<10} {'Exit':<10} {'PnL (₹)':<10}")
    print("-" * 70)
    for t in trade_history:
        print(f"{t['time']:<20} {t['type']:<8} "
              f"{t['entry']:<10.2f} {t['exit']:<10.2f} {t['pnl']:<10.2f}")
    print("-" * 70)
    print(f"Total Realized PnL: ₹{realized_pnl:,.2f}")
    print("-" * 70)


# ================= MAIN ALGO =================
def main():

    print("🤖 Starting Hull MA Trend Follower — Low Lag Trend System\n")

    prices = deque(maxlen=200)
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

            if len(prices) < HMA_SLOW_LEN:
                print(f"Collecting data... ({len(prices)}/{HMA_SLOW_LEN})")
                time.sleep(2)
                continue

            hma_fast = hull_ma(np.array(prices), HMA_FAST_LEN)
            hma_slow = hull_ma(np.array(prices), HMA_SLOW_LEN)

            if hma_fast is None or hma_slow is None:
                continue

            # Calculate slope of HMA fast
            if len(prices) > 1:
                prev_fast = hull_ma(np.array(list(prices)[:-1]), HMA_FAST_LEN)
                slope = hma_fast - prev_fast if prev_fast else 0
            else:
                slope = 0

            equity = cash + realized_pnl + (position * UNITS * (price - entry_price))

            # Drawdown safety
            if equity <= stop_equity:
                print("\n🚨 STOP TRIGGERED — 5% Capital Drawdown Reached.")
                break

            print(f"\n💹 Price: ₹{price:.2f} | HMA_FAST={hma_fast:.2f} | HMA_SLOW={hma_slow:.2f} | Equity=₹{equity:,.2f}")

            # -------- ENTRY SIGNALS --------
            long_signal  = hma_fast > hma_slow and slope > 0
            short_signal = hma_fast < hma_slow and slope < 0

            # -------- ENTRY LOGIC --------
            if position == 0:

                if long_signal:
                    position = 1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG ENTRY @ ₹{price:.2f} — HMA Trend UP | Units={UNITS}")

                elif short_signal:
                    position = -1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT ENTRY @ ₹{price:.2f} — HMA Trend DOWN | Units={UNITS}")

                else:
                    print("⚪ No trend — no trade.")

            else:
                # -------- Unrealized PnL --------
                unreal = position * UNITS * (price - entry_price)
                pos_txt = "LONG" if position == 1 else "SHORT"
                print(f"📊 {pos_txt} @ ₹{entry_price:.2f} | Unrealized: ₹{unreal:,.2f} | Realized: ₹{realized_pnl:,.2f}")

                # TP / SL prices
                tp_price = entry_price * (1 + TAKE_PROFIT_PCT if position == 1 else 1 - TAKE_PROFIT_PCT)
                sl_price = entry_price * (1 - STOP_LOSS_PCT  if position == 1 else 1 + STOP_LOSS_PCT)

                hit_tp = (position == 1 and price >= tp_price) or (position == -1 and price <= tp_price)
                hit_sl = (position == 1 and price <= sl_price) or (position == -1 and price >= sl_price)

                # -------- NEW: TREND REVERSAL EXIT --------
                trend_reversal = (position == 1 and short_signal) or (position == -1 and long_signal)

                if hit_tp or hit_sl or trend_reversal:

                    if trend_reversal:
                        reason = "🔄 TREND REVERSAL EXIT"
                    elif hit_tp:
                        reason = "🏆 TAKE PROFIT EXIT"
                    else:
                        reason = "❌ STOP LOSS EXIT"

                    realized_pnl += unreal

                    trade_history.append({
                        "time": entry_time,
                        "type": pos_txt,
                        "entry": entry_price,
                        "exit": price,
                        "pnl": unreal
                    })

                    print(f"{reason} @ ₹{price:.2f} | PnL: ₹{unreal:,.2f}")
                    position = 0

            # -------- PERIODIC SUMMARY --------
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = cash + realized_pnl + (position * UNITS * (price - entry_price))
                print("\n📘 PERFORMANCE SUMMARY (100s):")
                print(f"Realized: ₹{realized_pnl:,.2f}")
                print(f"Total Equity: ₹{total_equity:,.2f}")
                print(f"Net P/L: ₹{total_equity - start_equity:,.2f}")
                last_summary = time.time()

            # Manual Exit
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
