# Pivot_Breakout_Detailed_v2.py
import json
import time
from datetime import datetime

PRICE_FILE = "price_data.json"    # Exchange.py feed
WARMUP = 20                    # warm-up price count
RECALC_WINDOW = 5             # recalc pivots after exit
UNITS = 100
TP = 0.005                        # +0.5%
SL = -0.01                        # -1%
SLEEP = 2


# ---------------------------------------------------------
def read_price():
    try:
        with open(PRICE_FILE, "r") as f:
            return float(json.load(f)["price"])
    except:
        return None


# ---------------------------------------------------------
# Calculate pivots from given price list
# ---------------------------------------------------------
def calculate_pivots(prices):
    H = max(prices)
    L = min(prices)
    C = prices[-1]

    P  = (H + L + C) / 3
    R1 = 2*P - L
    S1 = 2*P - H
    R2 = P + (H - L)
    S2 = P - (H - L)

    return P, R1, S1, R2, S2


# ---------------------------------------------------------
def main():
    print("📊 Pivot Breakout v2 — Full Detail Mode\n")

    prices = []
    position = 0
    entry_price = 0
    entry_time = ""

    realized_pnl = 0
    prev_price = None

    pivots = None  # (P, R1, S1, R2, S2)

    try:
        while True:

            price = read_price()
            if price is None:
                print("Waiting for price feed…")
                time.sleep(1)
                continue

            print(f"\nTick Price: {price}")

            # -------------------------------
            # WARM-UP PHASE
            # -------------------------------
            if pivots is None and len(prices) < WARMUP:
                prices.append(price)
                print(f"🕒 Warm-up {len(prices)}/{WARMUP} … collecting prices…")
                prev_price = price
                time.sleep(SLEEP)
                continue

            # -------------------------------
            # CALCULATE INITIAL PIVOTS
            # -------------------------------
            if pivots is None:
                pivots = calculate_pivots(prices)
                P, R1, S1, R2, S2 = pivots

                print("\n🎯 Warm-up Complete — Pivot Levels:")
                print(f" P  = {P:.2f}")
                print(f" R1 = {R1:.2f}")
                print(f" R2 = {R2:.2f}")
                print(f" S1 = {S1:.2f}")
                print(f" S2 = {S2:.2f}\n")

                prev_price = price
                time.sleep(SLEEP)
                continue

            # -------------------------------
            # SHOW PIVOT LEVELS EVERY TICK
            # -------------------------------
            P, R1, S1, R2, S2 = pivots
            print(f"Pivot Info => P:{P:.2f} | R1:{R1:.2f} | R2:{R2:.2f} | S1:{S1:.2f} | S2:{S2:.2f}")

            current = price

            # -------------------------------
            # ENTRY LOGIC
            # -------------------------------
            if position == 0:

                # LONG entries
                if prev_price <= R1 and current > R1:
                    position = 1
                    entry_price = current
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 LONG ENTRY @ {current} | R1 Breakout")

                elif prev_price <= R2 and current > R2:
                    position = 1
                    entry_price = current
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📈 STRONG LONG @ {current} | R2 Breakout")

                # SHORT entries
                elif prev_price >= S1 and current < S1:
                    position = -1
                    entry_price = current
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 SHORT ENTRY @ {current} | S1 Breakdown")

                elif prev_price >= S2 and current < S2:
                    position = -1
                    entry_price = current
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    print(f"📉 STRONG SHORT @ {current} | S2 Breakdown")

            # -------------------------------
            # EXIT LOGIC + FULL DETAILS
            # -------------------------------
            else:
                pct_change = (current - entry_price) / entry_price * (1 if position == 1 else -1)
                unreal_pnl = pct_change * UNITS * entry_price

                print(f"Holding {'LONG' if position==1 else 'SHORT'} @ {entry_price}")
                print(f" UnRealized PnL: {unreal_pnl:.2f}")
                print(f" Realized PnL  : {realized_pnl:.2f}")
  

                # TAKE PROFIT
                if pct_change >= TP:
                    print(f"✅ TAKE PROFIT EXIT @ {current} | PnL={unreal_pnl:.2f}")
                    realized_pnl += unreal_pnl
                    position = 0

                    # recalc pivots using latest RECALC_WINDOW prices
                    prices.append(current)
                    pivots = calculate_pivots(prices[-RECALC_WINDOW:])
                    print("\n🔁 Recalculated Pivot Levels:")
                    P, R1, S1, R2, S2 = pivots
                    print(f" P  = {P:.2f}")
                    print(f" R1 = {R1:.2f}")
                    print(f" R2 = {R2:.2f}")
                    print(f" S1 = {S1:.2f}")
                    print(f" S2 = {S2:.2f}")

                # STOP LOSS
                elif pct_change <= SL:
                    print(f"❌ STOP LOSS EXIT @ {current} | PnL={unreal_pnl:.2f}")
                    realized_pnl += unreal_pnl
                    position = 0

                    # recalc pivots
                    prices.append(current)
                    pivots = calculate_pivots(prices[-RECALC_WINDOW:])
                    print("\n🔁 Recalculated Pivot Levels:")
                    P, R1, S1, R2, S2 = pivots
                    print(f" P  = {P:.2f}")
                    print(f" R1 = {R1:.2f}")
                    print(f" R2 = {R2:.2f}")
                    print(f" S1 = {S1:.2f}")
                    print(f" S2 = {S2:.2f}")

            prev_price = current
            prices.append(current)
            time.sleep(SLEEP)

    except KeyboardInterrupt:
        print("\n🛑 Manual Stop.")
        print(f"Final Realized PnL: {realized_pnl:.2f}")


if __name__ == "__main__":
    main()
