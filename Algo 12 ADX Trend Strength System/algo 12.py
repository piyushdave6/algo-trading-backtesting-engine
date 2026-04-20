# ADX_Trend_Strength_System_v2.py
import json
import time
import numpy as np
from datetime import datetime

# --------------- PARAMETERS ---------------
PRICE_FILE = "price_data.json"
TICKS_PER_CANDLE = 5
WARMUP_CANDLES = 10
ADX_PERIOD = 10
ADX_THRESHOLD = 20      # lowered for better responsiveness
TAKE_PROFIT_PCT = 0.005 # +0.5% profit
STOP_LOSS_PCT = 0.01    # -1% stop loss
UNITS = 100
BASE_CAPITAL = 100000
LOOP_SLEEP = 1.2
DRAWDOWN_STOP_PCT = 0.05
# ------------------------------------------

def read_price():
    try:
        with open(PRICE_FILE, "r") as f:
            return float(json.load(f)["price"])
    except Exception:
        return None

def calc_adx(highs, lows, closes, period=14):
    tr, plus_dm, minus_dm = [], [], []

    for i in range(1, len(highs)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)

    if len(tr) < period:
        return None, None, None

    tr_n = np.convolve(tr, np.ones(period), 'valid')
    plus_dm_n = np.convolve(plus_dm, np.ones(period), 'valid')
    minus_dm_n = np.convolve(minus_dm, np.ones(period), 'valid')

    plus_di = 100 * (plus_dm_n / tr_n)
    minus_di = 100 * (minus_dm_n / tr_n)
    dx = 100 * np.abs((plus_di - minus_di) / (plus_di + minus_di))
    adx = np.convolve(dx, np.ones(period)/period, 'valid')

    return plus_di[-1], minus_di[-1], adx[-1]

def main():
    print("🔥 Starting ADX Trend Strength System (v2)")
    print("⏳ Collecting ticks to form initial candles...\n")

    tick_buffer, highs, lows, closes = [], [], [], []
    position = 0
    entry_price = 0.0
    realized_pnl = 0.0
    capital = BASE_CAPITAL
    start_equity = BASE_CAPITAL
    stop_equity = start_equity * (1 - DRAWDOWN_STOP_PCT)
    trading_live = False

    try:
        while True:
            price = read_price()
            if price is None:
                print("⚠️ Waiting for price feed...")
                time.sleep(1)
                continue

            tick_buffer.append(price)
            print(f"Tick collected: ₹{price:.2f} ({len(tick_buffer)}/{TICKS_PER_CANDLE})")
            time.sleep(1.2)

            if len(tick_buffer) >= TICKS_PER_CANDLE:
                o, h, l, c = tick_buffer[0], max(tick_buffer), min(tick_buffer), tick_buffer[-1]
                tick_buffer.clear()
                highs.append(h)
                lows.append(l)
                closes.append(c)

                print("------------------------------------------------------------")
                print(f"Candle @ {datetime.now().strftime('%H:%M:%S')}: O:{o:.2f} H:{h:.2f} L:{l:.2f} C:{c:.2f}")

                if len(highs) < WARMUP_CANDLES:
                    print(f"🕒 Warm-up phase ({len(highs)}/{WARMUP_CANDLES})...\n")
                    continue

                plus_di, minus_di, adx = calc_adx(highs, lows, closes, ADX_PERIOD)
                if adx is None:
                    print("⚠️ Not enough data for ADX calculation yet.")
                    continue

                # Determine current market bias
                if plus_di > minus_di:
                    trend = "UP"
                elif minus_di > plus_di:
                    trend = "DOWN"
                else:
                    trend = "FLAT"

                print(f"ADX: {adx:.2f} | +DI: {plus_di:.2f} | -DI: {minus_di:.2f} | Trend: {trend}")

                if not trading_live:
                    print("\n✅ Warm-up complete — Trading mode activated!\n")
                    trading_live = True

                equity = capital + realized_pnl + (position * UNITS * (c - entry_price) if position else 0)
                if equity <= stop_equity:
                    print("\n🚨 STOP — Equity fell below 5% threshold.")
                    break

                # ---- TRADING LOGIC ----
                if position == 0:
                    if adx > ADX_THRESHOLD:
                        if plus_di > minus_di:
                            position = 1
                            entry_price = c
                            print(f"📈 LONG ENTRY @ ₹{entry_price:.2f} | Reason: +DI({plus_di:.2f}) > -DI({minus_di:.2f}) and ADX({adx:.2f}) strong")
                        elif minus_di > plus_di:
                            position = -1
                            entry_price = c
                            print(f"📉 SHORT ENTRY @ ₹{entry_price:.2f} | Reason: -DI({minus_di:.2f}) > +DI({plus_di:.2f}) and ADX({adx:.2f}) strong")
                        else:
                            print("⚪ No clear trend detected.")
                    else:
                        print(f"💤 No trade — ADX below {ADX_THRESHOLD} (weak trend)")

                else:
                    unrealized = position * UNITS * (c - entry_price)
                    pct_change = (c - entry_price) / entry_price * (1 if position == 1 else -1)
                    side = "LONG" if position == 1 else "SHORT"
                    print(f"Position: {side} @ ₹{entry_price:.2f} | Unrealized: ₹{unrealized:.2f} | Δ {pct_change*100:.2f}%")

                    # Exit logic
                    if pct_change >= TAKE_PROFIT_PCT:
                        realized_pnl += unrealized
                        print(f"✅ TAKE-PROFIT @ ₹{c:.2f} | PnL: ₹{unrealized:.2f}")
                        position = 0
                    elif pct_change <= -STOP_LOSS_PCT:
                        realized_pnl += unrealized
                        print(f"❌ STOP-LOSS @ ₹{c:.2f} | PnL: ₹{unrealized:.2f}")
                        position = 0
                    elif adx < ADX_THRESHOLD:
                        realized_pnl += unrealized
                        print(f"⚡ EXIT {side} — ADX weakened below {ADX_THRESHOLD} | PnL: ₹{unrealized:.2f}")
                        position = 0
                    else:
                        print("↔️ Holding position — trend still valid.")

                print(f"📊 Equity: ₹{equity:.2f} | Realized PnL: ₹{realized_pnl:.2f}\n")

    except KeyboardInterrupt:
        print("\n🛑 Interrupted manually.")
    finally:
        print("\n📘 Final Summary")
        print(f"Total Realized PnL: ₹{realized_pnl:.2f}")
        print("✅ Algo stopped safely.")

if __name__ == "__main__":
    main()
