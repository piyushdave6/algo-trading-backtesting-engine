#!/usr/bin/env python3
"""
Keltner-only Volatility Breakout
- Middle = SMA(20)
- Band = SMA +/- K * ATR(20)
- Entry: Price > Upper -> LONG ; Price < Lower -> SHORT
- Exit: TP/SL, cross back to SMA, or opposite band break (flip)
- Warm-up: 20 prices
- Clean logging + final trade history
Related/local helper file (optional): /mnt/data/Exchange.py
"""

import json
import time
from collections import deque
from datetime import datetime
import numpy as np

# -------------- USER PARAMETERS --------------
PRICE_FILE = "price_data.json"   # feed file {"price": 1234}
WARMUP = 20
WINDOW = 20                       # SMA & ATR window
K = 1                         # Keltner multiplier (2 is standard)
UNITS = 100
BASE_CAPITAL = 100000.0

LOOP_SLEEP = 3               # seconds between loop iterations
SUMMARY_INTERVAL = 100            # seconds

TAKE_PROFIT_PCT = 0.005           # 0.5% TP
STOP_LOSS_PCT = 0.010             # 0.5% SL

EXIT_ON_SMA_CROSS = True          # exit when price crosses back to SMA
FLIP_ON_OPPOSITE_BREAK = True     # close and flip immediately on opposite band break

# -------------- helper functions --------------
def read_price():
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"])
    except Exception:
        return None

def calc_atr(prices):
    """Simplified ATR: mean of absolute price differences over window."""
    if len(prices) < 2:
        return 0.0
    diffs = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
    return float(np.mean(diffs))

def calc_sma(prices, period):
    pl = list(prices)
    if len(pl) < period:
        return None
    return float(np.mean(pl[-period:]))

def format_money(x):
    return f"₹{x:,.2f}"

def print_trade_history(trades):
    if not trades:
        print("No trades executed.")
        return
    print("\n📘 TRADE HISTORY")
    print("-" * 72)
    print(f"{'Time':<10} {'Type':<6} {'Entry':>10} {'Exit':>10} {'PnL (₹)':>12}")
    print("-" * 72)
    for t in trades:
        print(f"{t['time']:<10} {t['type']:<6} {t['entry']:>10.2f} {t['exit']:>10.2f} {t['pnl']:>12.2f}")
    print("-" * 72)

# -------------- main algo --------------
def main():
    print("🤖 Keltner Breakout — SMA(20) + K * ATR(20)\n")
    prices = deque(maxlen=WINDOW + 200)   # keep extra history
    trade_history = []

    warmed = False
    atr_base = None

    position = 0               # 0 none, 1 long, -1 short
    entry_price = 0.0
    entry_time = ""
    realized_pnl = 0.0
    start_equity = BASE_CAPITAL

    last_summary = time.time()
    start_time = time.time()

    print(f"⏳ Warm-up: collecting {WARMUP} prices...")

    try:
        while True:
            p = read_price()
            if p is None:
                time.sleep(1)
                continue

            prices.append(float(p))

            # warm-up phase
            if not warmed:
                if len(prices) < WARMUP:
                    print(f"Collecting warm-up... ({len(prices)}/{WARMUP}) Price={p:.2f}")
                    time.sleep(LOOP_SLEEP)
                    continue
                # compute ATR_base from warm-up window
                warm_window = list(prices)[-WINDOW:]
                atr_base = calc_atr(warm_window)
                warmed = True
                print("\n✅ Warm-up complete.")
                print(f"   ATR_base (warm-up ATR over {WINDOW}): {atr_base:.4f}")
                print("   Entering trading mode...\n")
                time.sleep(LOOP_SLEEP)
                continue

            # trading mode: compute SMA and ATR on rolling WINDOW
            pl = list(prices)
            if len(pl) < WINDOW:
                time.sleep(LOOP_SLEEP)
                continue

            recent = pl[-WINDOW:]
            sma = calc_sma(recent, WINDOW)
            atr = calc_atr(recent)
            upper = sma + K * atr
            lower = sma - K * atr

            price_now = pl[-1]
            unrealized = position * UNITS * (price_now - entry_price)
            equity = start_equity + realized_pnl + unrealized

            # Clean logging
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n⏱ {now} | Price={price_now:.2f} | Regime: KELTNER")
            print(f"   SMA({WINDOW})={sma:.2f} | ATR={atr:.4f} | K={K}")
            print(f"   Upper={upper:.2f} | Lower={lower:.2f}")
            print(f"   Realized {format_money(realized_pnl)} | Unrealized {format_money(unrealized)} | Equity {format_money(equity)}")

            # SIGNALS & POSITION LOGIC
            # 1) If no position -> look for entry on band breakout
            if position == 0:
                if price_now > upper:
                    # long breakout
                    position = 1
                    entry_price = price_now
                    entry_time = now
                    print(f"📈 BREAKOUT LONG ENTRY @ {entry_price:.2f} (price > upper)")
                elif price_now < lower:
                    # short breakout
                    position = -1
                    entry_price = price_now
                    entry_time = now
                    print(f"📉 BREAKOUT SHORT ENTRY @ {entry_price:.2f} (price < lower)")

            # 2) If position open -> check TP/SL and exit conditions + flip on opposite break if enabled
            else:
                # Pct change in direction of trade
                pct = (price_now - entry_price) / entry_price * (1 if position == 1 else -1)

                # TP / SL
                if pct >= TAKE_PROFIT_PCT:
                    pnl = position * UNITS * (price_now - entry_price)
                    realized_pnl += pnl
                    trade_history.append({"time": entry_time, "type": "LONG" if position==1 else "SHORT",
                                          "entry": entry_price, "exit": price_now, "pnl": pnl})
                    print(f"✅ TAKE PROFIT @ {price_now:.2f} | PnL {format_money(pnl)}")
                    position = 0
                    entry_price = 0.0

                elif pct <= -STOP_LOSS_PCT:
                    pnl = position * UNITS * (price_now - entry_price)
                    realized_pnl += pnl
                    trade_history.append({"time": entry_time, "type": "LONG" if position==1 else "SHORT",
                                          "entry": entry_price, "exit": price_now, "pnl": pnl})
                    print(f"❌ STOP LOSS @ {price_now:.2f} | PnL {format_money(pnl)}")
                    position = 0
                    entry_price = 0.0

                else:
                    # Exit on SMA cross if enabled
                    if EXIT_ON_SMA_CROSS:
                        if position == 1 and price_now < sma:
                            pnl = position * UNITS * (price_now - entry_price)
                            realized_pnl += pnl
                            trade_history.append({"time": entry_time, "type": "LONG", "entry": entry_price, "exit": price_now, "pnl": pnl})
                            print(f"🔄 EXIT (cross SMA) @ {price_now:.2f} | PnL {format_money(pnl)}")
                            position = 0
                            entry_price = 0.0
                        elif position == -1 and price_now > sma:
                            pnl = position * UNITS * (price_now - entry_price)
                            realized_pnl += pnl
                            trade_history.append({"time": entry_time, "type": "SHORT", "entry": entry_price, "exit": price_now, "pnl": pnl})
                            print(f"🔄 EXIT (cross SMA) @ {price_now:.2f} | PnL {format_money(pnl)}")
                            position = 0
                            entry_price = 0.0

                    # Flip on opposite band break if enabled
                    if FLIP_ON_OPPOSITE_BREAK and position == 1 and price_now < lower:
                        # long -> price fell below lower band -> close long and open short
                        pnl = position * UNITS * (price_now - entry_price)
                        realized_pnl += pnl
                        trade_history.append({"time": entry_time, "type": "LONG", "entry": entry_price, "exit": price_now, "pnl": pnl})
                        print(f"🔁 FLIP: LONG closed @ {price_now:.2f} | PnL {format_money(pnl)}")
                        # open SHORT
                        position = -1
                        entry_price = price_now
                        entry_time = now
                        print(f"📉 FLIP OPEN SHORT @ {entry_price:.2f}")

                    elif FLIP_ON_OPPOSITE_BREAK and position == -1 and price_now > upper:
                        pnl = position * UNITS * (price_now - entry_price)
                        realized_pnl += pnl
                        trade_history.append({"time": entry_time, "type": "SHORT", "entry": entry_price, "exit": price_now, "pnl": pnl})
                        print(f"🔁 FLIP: SHORT closed @ {price_now:.2f} | PnL {format_money(pnl)}")
                        position = 1
                        entry_price = price_now
                        entry_time = now
                        print(f"📈 FLIP OPEN LONG @ {entry_price:.2f}")

            # periodic summary
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = start_equity + realized_pnl + position * UNITS * (price_now - (entry_price if entry_price else price_now))
                print("\n📘 PERFORMANCE SUMMARY")
                print(f"   Realized PnL: {format_money(realized_pnl)}")
                print(f"   Unrealized PnL: {format_money(unrealized)}")
                print(f"   Equity: {format_money(total_equity)}")
                print(f"   Upper: {upper:.2f} | Lower: {lower:.2f} | SMA: {sma:.2f} | ATR_base: {atr_base:.4f}")
                last_summary = time.time()

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Manual stop received — closing open position and summarizing...")

        # close open position if any
        if position != 0:
            exit_price = pl[-1]
            pnl = position * UNITS * (exit_price - entry_price)
            realized_pnl += pnl
            trade_history.append({"time": entry_time, "type": "LONG" if position==1 else "SHORT",
                                  "entry": entry_price, "exit": exit_price, "pnl": pnl})
            print(f"🔚 Closed open position @ {exit_price:.2f} | PnL {format_money(pnl)}")

        final_equity = start_equity + realized_pnl
        elapsed = time.time() - start_time
        print("\n📘 FINAL SESSION SUMMARY")
        print(f"   Start Equity: {format_money(start_equity)}")
        print(f"   Realized PnL: {format_money(realized_pnl)}")
        print(f"   Final Equity: {format_money(final_equity)}")
        print(f"   Run time (s): {int(elapsed)}")
        print_trade_history(trade_history)
        print("✅ Algo stopped safely.")

if __name__ == "__main__":
    main()
