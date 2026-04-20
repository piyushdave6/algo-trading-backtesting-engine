# MACD_Trend_Strategy_v2.py
import json
import time
import numpy as np
from collections import deque
from datetime import datetime

# ---------------- PARAMETERS ----------------
PRICE_FILE = "price_data.json"
WARMUP = 50               # ensure enough data to seed EMAs
EMA_SHORT = 12
EMA_LONG = 26
SIGNAL_PERIOD = 9
UNITS = 100               # fixed units per trade
TAKE_PROFIT_PCT = 0.005   # ✅ 0.5% take profit
STOP_LOSS_PCT = 0.005     # ✅ 0.5% stop loss
BASE_CAPITAL = 100000.0
DRAWDOWN_STOP_PCT = 0.05  # stop entire algo at 5% loss
LOOP_SLEEP = 3            # seconds between ticks
SUMMARY_INTERVAL = 120
# --------------------------------------------

def read_price():
    """Read the latest simulated price from price_data.json"""
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"])
    except Exception:
        return None

def sma(values):
    return float(np.mean(values)) if len(values) else 0.0

def update_ema(prev_ema, price, period):
    alpha = 2.0 / (period + 1.0)
    if prev_ema is None:
        return price
    return price * alpha + prev_ema * (1 - alpha)

def print_trade_log(trades, realized_pnl):
    print("\n📘 FINAL TRADE HISTORY")
    print("-" * 80)
    print(f"{'Time':<20} {'Side':<6} {'Entry':<10} {'Exit':<10} {'PnL (₹)':<12}")
    print("-" * 80)
    for t in trades:
        print(f"{t['time']:<20} {t['side']:<6} {t['entry']:<10.2f} {t['exit']:<10.2f} {t['pnl']:<12.2f}")
    print("-" * 80)
    print(f"Total Realized PnL: ₹{realized_pnl:,.2f}")
    print("-" * 80)

def main():
    print("🤖 Starting MACD Trend Strategy (TP=0.5%, SL=0.5%) — Press 'q' to exit safely\n")

    prices = deque(maxlen=500)
    trade_history = []
    cash = BASE_CAPITAL
    realized_pnl = 0.0
    position = 0
    entry_price = 0.0
    entry_time = ""
    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - DRAWDOWN_STOP_PCT)

    ema_short = ema_long = macd = signal = None
    prev_macd = prev_signal = None

    last_summary = time.time()

    print(f"⏳ Collecting live prices (need {WARMUP} readings)...")

    try:
        while True:
            price = read_price()
            if price is None:
                print("⚠️ Waiting for price feed...")
                time.sleep(2)
                continue

            prices.append(price)

            if len(prices) < WARMUP:
                print(f"Collecting data... ({len(prices)}/{WARMUP}) | Latest: ₹{price:.2f}")
                time.sleep(1)
                continue

            if ema_short is None or ema_long is None:
                ema_short = sma(list(prices)[-EMA_SHORT:])
                ema_long = sma(list(prices)[-EMA_LONG:])
                macd = ema_short - ema_long
                signal = macd
                prev_macd = macd
                prev_signal = signal
                print(f"\n✅ Initialized EMAs — EMA{EMA_SHORT}: {ema_short:.2f}, EMA{EMA_LONG}: {ema_long:.2f}\n")
                continue

            ema_short = update_ema(ema_short, price, EMA_SHORT)
            ema_long = update_ema(ema_long, price, EMA_LONG)
            prev_macd = macd
            macd = ema_short - ema_long
            prev_signal = signal
            signal = update_ema(signal, macd, SIGNAL_PERIOD)
            hist = macd - signal

            equity = cash + realized_pnl + (position * UNITS * (price - entry_price) if position != 0 else 0.0)
            if equity <= stop_equity:
                print("\n🚨 STOP — 5% drawdown hit.")
                break

            macd_cross_up = (prev_macd <= prev_signal and macd > signal)
            macd_cross_down = (prev_macd >= prev_signal and macd < signal)
            long_confirm = macd > 0 and macd_cross_up
            short_confirm = macd < 0 and macd_cross_down

            print(f"\n💹 Price: ₹{price:.2f} | Equity: ₹{equity:,.2f}")
            print(f"   EMA{EMA_SHORT}: {ema_short:.2f} | EMA{EMA_LONG}: {ema_long:.2f}")
            print(f"   MACD: {macd:.3f} | Signal: {signal:.3f} | Hist: {hist:.3f}")

            if position == 0:
                if long_confirm:
                    position = 1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG ENTRY @ ₹{price:.2f} | MACD crossed above Signal (MACD>0)")
                elif short_confirm:
                    position = -1
                    entry_price = price
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT ENTRY @ ₹{price:.2f} | MACD crossed below Signal (MACD<0)")
                else:
                    print("⚪ No signal — waiting for crossover confirmation.")
            else:
                unrealized = position * UNITS * (price - entry_price)
                pct_change = (price - entry_price) / entry_price * (1 if position == 1 else -1)
                print(f"   Position: {'LONG' if position==1 else 'SHORT'} @ ₹{entry_price:.2f} | PnL ₹{unrealized:.2f} | Δ {pct_change:+.2%}")

                if pct_change >= TAKE_PROFIT_PCT:
                    realized_pnl += unrealized
                    trade_history.append({"time": entry_time, "side": "LONG" if position==1 else "SHORT",
                                          "entry": entry_price, "exit": price, "pnl": unrealized})
                    print(f"✅ TAKE-PROFIT EXIT @ ₹{price:.2f} | PnL ₹{unrealized:.2f}")
                    position = 0
                elif pct_change <= -STOP_LOSS_PCT:
                    realized_pnl += unrealized
                    trade_history.append({"time": entry_time, "side": "LONG" if position==1 else "SHORT",
                                          "entry": entry_price, "exit": price, "pnl": unrealized})
                    print(f"❌ STOP-LOSS EXIT @ ₹{price:.2f} | PnL ₹{unrealized:.2f}")
                    position = 0
                else:
                    print("   Holding position — no exit signal yet.")

            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = cash + realized_pnl + (position * UNITS * (price - entry_price) if position != 0 else 0.0)
                print("\n📘 SUMMARY UPDATE:")
                print(f"   Realized PnL: ₹{realized_pnl:.2f}")
                print(f"   Total Equity: ₹{total_equity:.2f}")
                last_summary = time.time()

            try:
                import msvcrt
                if msvcrt.kbhit():
                    if msvcrt.getch().decode().lower() == "q":
                        print("\n🛑 Manual exit triggered (q).")
                        break
            except Exception:
                pass

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted manually (Ctrl+C).")

    finally:
        print_trade_log(trade_history, realized_pnl)
        print("✅ Strategy stopped safely.")

if __name__ == "__main__":
    main()
