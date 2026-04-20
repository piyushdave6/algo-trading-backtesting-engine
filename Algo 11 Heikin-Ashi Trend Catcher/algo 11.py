# HeikinAshi_Trend_Catcher_v6.py
import json
import time
import numpy as np
from collections import deque
from datetime import datetime

# ---------------- PARAMETERS ----------------
PRICE_FILE = "price_data.json"
TICKS_PER_CANDLE = 10        # increased to 10
WARMUP_CANDLES = 10          # increased to 10
ATR_PERIOD = 14
UNITS = 100
TAKE_PROFIT_PCT = 0.005      # +0.5% take profit
STOP_LOSS_PCT = 0.01         # -1% stop loss
BASE_CAPITAL = 100000
DRAWDOWN_STOP_PCT = 0.05
LOOP_SLEEP = 1.2
# --------------------------------------------------

def read_price():
    try:
        with open(PRICE_FILE, "r") as f:
            return float(json.load(f)["price"])
    except Exception:
        return None

def calc_atr(highs, lows, closes, period=14):
    trs = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    return np.mean(trs[-period:]) if len(trs) >= period else np.mean(trs) if trs else 0.0

def heikin_ashi_candle(prev_ha, o, h, l, c):
    ha_close = (o + h + l + c) / 4
    if prev_ha is None:
        ha_open = (o + c) / 2
    else:
        ha_open = (prev_ha["open"] + prev_ha["close"]) / 2
    ha_high = max(h, ha_open, ha_close)
    ha_low = min(l, ha_open, ha_close)
    return {"open": ha_open, "high": ha_high, "low": ha_low, "close": ha_close}

def main():
    print("🔥 Starting Heikin-Ashi Trend Catcher Algo (v6)")
    print("⏳ Collecting live ticks to form initial candles...\n")

    tick_buffer = []
    candles, ha_candles = [], []
    highs, lows, closes = [], [], []
    position = 0
    entry_price = 0.0
    realized_pnl = 0.0
    capital = BASE_CAPITAL
    prev_ha = None

    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - DRAWDOWN_STOP_PCT)
    trading_live = False
    prev_color = None

    try:
        while True:
            price = read_price()
            if price is None:
                print("⚠️ Waiting for price feed...")
                time.sleep(1)
                continue

            tick_buffer.append(price)
            print(f"Tick collected: ₹{price:.2f}  (buffer {len(tick_buffer)}/{TICKS_PER_CANDLE})")
            time.sleep(1.2)

            if len(tick_buffer) >= TICKS_PER_CANDLE:
                o, h, l, c = tick_buffer[0], max(tick_buffer), min(tick_buffer), tick_buffer[-1]
                tick_buffer.clear()

                candles.append({"open": o, "high": h, "low": l, "close": c})
                highs.append(h)
                lows.append(l)
                closes.append(c)

                ha = heikin_ashi_candle(prev_ha, o, h, l, c)
                ha_candles.append(ha)
                prev_ha = ha

                atr = calc_atr(highs, lows, closes, ATR_PERIOD)
                color = "GREEN" if ha["close"] > ha["open"] else "RED"

                print("------------------------------------------")
                print(f"Candle @ {datetime.now().strftime('%H:%M:%S')}: O:{o:.2f} H:{h:.2f} L:{l:.2f} C:{c:.2f}")
                print(f"Heikin-Ashi: O:{ha['open']:.2f} H:{ha['high']:.2f} L:{ha['low']:.2f} C:{ha['close']:.2f} | Color: {color}")
                print(f"ATR({ATR_PERIOD}) ≈ ₹{atr:.4f}")

                if len(candles) < WARMUP_CANDLES:
                    print(f"🕒 Warm-up phase ({len(candles)}/{WARMUP_CANDLES})...\n")
                    continue

                if not trading_live:
                    print("\n✅ Warm-up complete — Trading mode activated!\n")
                    trading_live = True

                equity = capital + realized_pnl + (position * UNITS * (c - entry_price) if position != 0 else 0)
                if equity <= stop_equity:
                    print("\n🚨 STOP — Equity dropped below 5% threshold.")
                    break

                # ---- TRADING LOGIC ----
                if position == 0:
                    if color == "GREEN":
                        position = 1
                        entry_price = c
                        prev_color = color
                        print(f"📈 LONG ENTRY @ ₹{entry_price:.2f} | Reason: Heikin-Ashi turned GREEN (uptrend)")
                    elif color == "RED":
                        position = -1
                        entry_price = c
                        prev_color = color
                        print(f"📉 SHORT ENTRY @ ₹{entry_price:.2f} | Reason: Heikin-Ashi turned RED (downtrend)")

                else:
                    unrealized = position * UNITS * (c - entry_price)
                    pct_change = (c - entry_price) / entry_price * (1 if position == 1 else -1)
                    side = "LONG" if position == 1 else "SHORT"
                    print(f"Position: {side} @ ₹{entry_price:.2f} | Unrealized: ₹{unrealized:.2f} | Change: {pct_change*100:.2f}%")

                    # ---- IMMEDIATE EXIT ON COLOR FLIP ----
                    if (position == 1 and color == "RED") or (position == -1 and color == "GREEN"):
                        realized_pnl += unrealized
                        print(f"⚡ Trend Flip Exit: {side} closed as HA turned {color} | PnL: ₹{unrealized:.2f}")
                        position = 0
                        prev_color = color
                        continue

                    # ---- TAKE PROFIT / STOP LOSS ----
                    if pct_change >= TAKE_PROFIT_PCT:
                        realized_pnl += unrealized
                        print(f"✅ TAKE-PROFIT HIT @ ₹{c:.2f} | PnL: ₹{unrealized:.2f}")
                        position = 0
                        prev_color = color
                    elif pct_change <= -STOP_LOSS_PCT:
                        realized_pnl += unrealized
                        print(f"❌ STOP-LOSS HIT @ ₹{c:.2f} | PnL: ₹{unrealized:.2f}")
                        position = 0
                        prev_color = color
                    else:
                        print("↔️ Holding position — waiting for target, SL, or trend change.")

                print(f"📊 Equity: ₹{equity:.2f} | Realized PnL: ₹{realized_pnl:.2f}\n")
                time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted manually.")

    finally:
        print("\n📘 Final Summary")
        print(f"Total Realized PnL: ₹{realized_pnl:.2f}")
        print("✅ Algo stopped safely.")

if __name__ == "__main__":
    main()
