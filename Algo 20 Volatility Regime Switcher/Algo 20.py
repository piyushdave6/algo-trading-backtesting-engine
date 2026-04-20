#!/usr/bin/env python3
"""
Algo 21 — Volatility Regime Switcher (ATR) with:
  - TREND mode: SuperTrend-like HL2 (20-period)
  - REVERSION mode: SMA (20)
Warm-up: 20 prices
Author: Generated for user
Related file: /mnt/data/Exchange.py
"""

import json
import time
from collections import deque
from datetime import datetime
import numpy as np

# ================== USER PARAMETERS ==================
PRICE_FILE = "price_data.json"   # incoming price feed (JSON -> {"price": 1234})
WARMUP = 20                      # warm-up length in prices
ATR_WINDOW = 20                  # window to compute ATR and HL2/SMA
SMA_PERIOD = 20

BASE_CAPITAL = 100000.0
UNITS = 100

LOOP_SLEEP = 3                  # seconds per loop (adjust to your feed frequency)
SUMMARY_INTERVAL = 100            # seconds between summaries

TAKE_PROFIT_PCT = 0.005           # 0.5% take profit
STOP_LOSS_PCT = 0.010            # 0.1% stop loss

# Whether SMA reversion should require a deviation margin (set to 0 for simple price < SMA)
SMA_DEVIATION_REQUIRED = 0.0      # example 0.005 would require 0.5% deviation

# =====================================================

def read_price():
    """Read latest price from PRICE_FILE (returns float or None)."""
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return float(data["price"])
    except Exception:
        return None

def calc_atr_from_prices(p_list):
    """Simplified ATR: mean of absolute differences over p_list."""
    if len(p_list) < 2:
        return 0.0
    diffs = [abs(p_list[i] - p_list[i-1]) for i in range(1, len(p_list))]
    return float(np.mean(diffs))

def calc_sma(p_list, period):
    price_list = list(p_list)
    if len(price_list) < period:
        return None
    return float(np.mean(price_list[-period:]))

def calc_hl2(p_list, window):
    """HL2 = (highest_in_window + lowest_in_window) / 2"""
    price_list = list(p_list)
    if len(price_list) < window:
        return None
    window_prices = price_list[-window:]
    return (max(window_prices) + min(window_prices)) / 2.0

def print_trade_history(trades):
    if not trades:
        print("No trades executed.")
        return
    print("\n📘 TRADE HISTORY")
    print("-" * 70)
    print(f"{'Time':<10} {'Type':<6} {'Entry':>10} {'Exit':>10} {'PnL (₹)':>12}")
    print("-" * 70)
    for t in trades:
        print(f"{t['time']:<10} {t['type']:<6} {t['entry']:>10.2f} {t['exit']:>10.2f} {t['pnl']:>12.2f}")
    print("-" * 70)

def format_money(x):
    return f"₹{x:,.2f}"

def main():
    print("🤖 Algo 21 — Volatility Regime Switcher (ATR -> SuperTrend / SMA)\n")
    prices = deque(maxlen=ATR_WINDOW + 50)   # keep enough history
    trade_history = []

    position = 0          # 0 none, 1 long, -1 short
    entry_price = 0.0
    entry_time = ""
    realized_pnl = 0.0
    start_equity = BASE_CAPITAL

    atr_base = None
    warmed = False

    last_summary = time.time()
    start_time = time.time()

    print(f"⏳ Warm-up: collecting {WARMUP} prices...")

    try:
        while True:
            p = read_price()
            if p is None:
                # no data yet
                time.sleep(1)
                continue

            prices.append(float(p))

            # Warm-up phase
            if not warmed:
                if len(prices) < WARMUP:
                    print(f"Collecting warm-up... ({len(prices)}/{WARMUP}) Price={p:.2f}")
                    time.sleep(LOOP_SLEEP)
                    continue
                # compute ATR_base from the warm-up window
                window_prices = list(prices)[-ATR_WINDOW:]
                atr_base = calc_atr_from_prices(window_prices)
                warmed = True
                print("\n✅ Warm-up complete.")
                print(f"   ATR_base (warm-up ATR over {ATR_WINDOW}): {atr_base:.4f}")
                print("   Entering trading mode...\n")
                time.sleep(LOOP_SLEEP)
                continue

            # --- Trading mode (update indicators each tick) ---
            # Compute current ATR over ATR_WINDOW
            price_list = list(prices)
            if len(price_list) < ATR_WINDOW:
                # shouldn't happen after warm-up, but safe-check
                time.sleep(LOOP_SLEEP)
                continue

            recent = price_list[-ATR_WINDOW:]
            atr = calc_atr_from_prices(recent)

            # Decide regime: ATR <= ATR_base => TREND; ATR > ATR_base => REVERSION
            if atr <= atr_base:
                regime = "TREND"
            else:
                regime = "REVERSION"

            # Compute regime-specific baseline
            hl2 = calc_hl2(prices, ATR_WINDOW)       # SuperTrend base
            sma = calc_sma(prices, SMA_PERIOD)       # SMA baseline

            # Common PnL
            unrealized = position * UNITS * (price_list[-1] - entry_price)
            equity = start_equity + realized_pnl + unrealized

            # Minimal logging (no vol/ATR%/STD)
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n⏱ {now} | Price={price_list[-1]:.2f}")
            print(f"   Regime={regime} | ATR={atr:.4f}")
            if regime == "TREND":
                # show HL2 (buy/sell baseline)
                if hl2 is not None:
                    print(f"   SuperTrend HL2 (mid of {ATR_WINDOW} range) = {hl2:.2f}")
            else:
                # show SMA (buy/sell baseline)
                if sma is not None:
                    print(f"   SMA({SMA_PERIOD}) = {sma:.2f}")

            print(f"   Realized {format_money(realized_pnl)} | Unrealized {format_money(unrealized)} | Equity {format_money(equity)}")

            price_now = price_list[-1]

            # ---------- ENTRY / EXIT LOGIC ----------
            if position == 0:
                # no open position => check for entry according to regime
                if regime == "TREND":
                    # SuperTrend simple rule: price > HL2 => LONG, price < HL2 => SHORT
                    if hl2 is not None:
                        if price_now > hl2:
                            position = 1
                            entry_price = price_now
                            entry_time = now
                            print(f"📈 TREND — LONG ENTRY @ {entry_price:.2f}")
                        elif price_now < hl2:
                            position = -1
                            entry_price = price_now
                            entry_time = now
                            print(f"📉 TREND — SHORT ENTRY @ {entry_price:.2f}")
                else:  # REVERSION
                    # SMA reversion: price < SMA*(1 - dev) => LONG, price > SMA*(1 + dev) => SHORT
                    if sma is not None:
                        lower_thresh = sma * (1.0 - SMA_DEVIATION_REQUIRED)
                        upper_thresh = sma * (1.0 + SMA_DEVIATION_REQUIRED)
                        if price_now < lower_thresh:
                            position = 1
                            entry_price = price_now
                            entry_time = now
                            print(f"📈 REVERSION — LONG ENTRY @ {entry_price:.2f} (price below SMA)")
                        elif price_now > upper_thresh:
                            position = -1
                            entry_price = price_now
                            entry_time = now
                            print(f"📉 REVERSION — SHORT ENTRY @ {entry_price:.2f} (price above SMA)")
            else:
                # position open -> check TP/SL or opposite regime signal
                # pct change in direction of the trade
                pct = (price_now - entry_price) / entry_price * (1 if position == 1 else -1)

                # Exit if TP or SL hit
                if pct >= TAKE_PROFIT_PCT:
                    pnl = position * UNITS * (price_now - entry_price)
                    realized_pnl += pnl
                    trade_history.append({"time": entry_time, "type": "LONG" if position == 1 else "SHORT",
                                          "entry": entry_price, "exit": price_now, "pnl": pnl})
                    print(f"✅ TAKE PROFIT @ {price_now:.2f} | PnL {format_money(pnl)}")
                    position = 0
                    entry_price = 0.0
                elif pct <= -STOP_LOSS_PCT:
                    pnl = position * UNITS * (price_now - entry_price)
                    realized_pnl += pnl
                    trade_history.append({"time": entry_time, "type": "LONG" if position == 1 else "SHORT",
                                          "entry": entry_price, "exit": price_now, "pnl": pnl})
                    print(f"❌ STOP LOSS @ {price_now:.2f} | PnL {format_money(pnl)}")
                    position = 0
                    entry_price = 0.0
                else:
                    # Exit if opposite signal appears due to regime logic:
                    if regime == "TREND":
                        # If in trend and price crosses HL2 to opposite side, exit (and optionally flip)
                        if hl2 is not None:
                            if position == 1 and price_now < hl2:
                                # long but now below HL2 => close
                                pnl = position * UNITS * (price_now - entry_price)
                                realized_pnl += pnl
                                trade_history.append({"time": entry_time, "type": "LONG", "entry": entry_price, "exit": price_now, "pnl": pnl})
                                print(f"🔄 EXIT (HL2 cross) @ {price_now:.2f} | PnL {format_money(pnl)}")
                                position = 0
                                entry_price = 0.0
                            elif position == -1 and price_now > hl2:
                                pnl = position * UNITS * (price_now - entry_price)
                                realized_pnl += pnl
                                trade_history.append({"time": entry_time, "type": "SHORT", "entry": entry_price, "exit": price_now, "pnl": pnl})
                                print(f"🔄 EXIT (HL2 cross) @ {price_now:.2f} | PnL {format_money(pnl)}")
                                position = 0
                                entry_price = 0.0
                    else:
                        # Reversion mode: exit when price returns to SMA (or crosses)
                        if sma is not None:
                            if position == 1 and price_now >= sma:
                                pnl = position * UNITS * (price_now - entry_price)
                                realized_pnl += pnl
                                trade_history.append({"time": entry_time, "type": "LONG", "entry": entry_price, "exit": price_now, "pnl": pnl})
                                print(f"🔄 EXIT (SMA revert) @ {price_now:.2f} | PnL {format_money(pnl)}")
                                position = 0
                                entry_price = 0.0
                            elif position == -1 and price_now <= sma:
                                pnl = position * UNITS * (price_now - entry_price)
                                realized_pnl += pnl
                                trade_history.append({"time": entry_time, "type": "SHORT", "entry": entry_price, "exit": price_now, "pnl": pnl})
                                print(f"🔄 EXIT (SMA revert) @ {price_now:.2f} | PnL {format_money(pnl)}")
                                position = 0
                                entry_price = 0.0

            # Periodic summary
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                total_equity = start_equity + realized_pnl + position * UNITS * (price_now - entry_price)
                print("\n📘 PERFORMANCE SUMMARY")
                print(f"   Realized PnL: {format_money(realized_pnl)}")
                print(f"   Unrealized PnL: {format_money(unrealized)}")
                print(f"   Equity: {format_money(total_equity)}")
                print(f"   Current Regime: {regime}")
                print(f"   Warm-up ATR_base: {atr_base:.4f}")
                last_summary = time.time()

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Manual stop (Ctrl+C) received — closing and summarizing...")

        # Close open position at last price
        if position != 0:
            exit_price = price_list[-1]
            pnl = position * UNITS * (exit_price - entry_price)
            realized_pnl += pnl
            trade_history.append({"time": entry_time, "type": "LONG" if position == 1 else "SHORT",
                                  "entry": entry_price, "exit": exit_price, "pnl": pnl})
            print(f"🔚 Closing open position @ {exit_price:.2f} | PnL {format_money(pnl)}")

        # Final summary
        final_equity = start_equity + realized_pnl
        print("\n📘 FINAL SESSION SUMMARY")
        print(f"Start Equity: {format_money(start_equity)}")
        print(f"Total Realized PnL: {format_money(realized_pnl)}")
        print(f"Final Equity: {format_money(final_equity)}")
        elapsed = time.time() - start_time
        print(f"Run time: {int(elapsed)} seconds")
        print_trade_history(trade_history)
        print("✅ Algo stopped safely.")

if __name__ == "__main__":
    main()
