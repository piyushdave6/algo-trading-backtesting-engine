import json
import time
from datetime import datetime
from collections import deque

PRICE_FILE = "price_data.json"

VWAP_WINDOW = 60
WARMUP_TICKS = 20
SLEEP_SECONDS = 2

START_CAPITAL = 100000
TP_PCT = 0.005
SL_PCT = 0.01
MAX_DRAWDOWN = 0.05
SUMMARY_INTERVAL = 100

price_volume_buffer = deque(maxlen=VWAP_WINDOW)
warmup_buffer = []

capital = START_CAPITAL
position = None
entry_price = None
qty = 0
realised_pnl = 0

start_time = time.time()
last_summary = start_time


def read_price_volume():
    with open(PRICE_FILE, "r") as f:
        data = json.load(f)
    return float(data["price"]), float(data["volume"])


def compute_true_vwap(pv_list):
    if len(pv_list) == 0:
        return None
    total_pv = sum(p * v for p, v in pv_list)
    total_vol = sum(v for _, v in pv_list)
    if total_vol == 0:
        return None
    return total_pv / total_vol


def print_position_status(price):
    if position:
        if position == "LONG":
            unreal = (price - entry_price) * qty
        else:
            unreal = (entry_price - price) * qty

        print(f"   ▶ Position: {position} | Entry={entry_price:.2f} | Qty={qty}")
        print(f"     Unrealised: {unreal:.2f} | Realised: {realised_pnl:.2f}")
        print(f"     Capital: {capital:.2f}\n")


print("\n🚀 Starting VWAP Algo 32 (Price + Volume)")
print(f"📌 Warm-up for first {WARMUP_TICKS} ticks...\n")

while True:

    price, volume = read_price_volume()

    if len(warmup_buffer) < WARMUP_TICKS:
        warmup_buffer.append((price, volume))
        vwap = compute_true_vwap(warmup_buffer)

        print(f"[Warm-up] {len(warmup_buffer)}/{WARMUP_TICKS} "
              f"| Price={price:.2f} | Vol={volume:.0f} | VWAP={vwap:.2f}")

        time.sleep(SLEEP_SECONDS)
        continue

    if len(price_volume_buffer) == 0:
        for p, v in warmup_buffer:
            price_volume_buffer.append((p, v))
        print("\n🔥 Warm-up complete! Starting LIVE TRADING.\n")

    if capital < START_CAPITAL * (1 - MAX_DRAWDOWN):
        print("\n⛔ Algo stopped: 5% drawdown hit.")
        print(f"Final Capital: {capital:.2f}")
        print(f"Total Realised PNL: {realised_pnl:.2f}")
        break

    price_volume_buffer.append((price, volume))
    vwap = compute_true_vwap(price_volume_buffer)
    deviation = (price - vwap) / vwap * 100

    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
          f"Price={price:.2f} Vol={volume:.0f} VWAP={vwap:.2f} Dev={deviation:.3f}%")

    # ----------------------------------------------------
    # ENTRY LOGIC  (FIXED QTY = 100)
    # ----------------------------------------------------
    if position is None:

        qty = 100   # <<< FIXED LOT SIZE

        if price < vwap:
            position = "LONG"
            entry_price = price
            print(f"🟢 LONG ENTERED @ {price:.2f} | Qty={qty}")

        elif price > vwap:
            position = "SHORT"
            entry_price = price
            print(f"🔴 SHORT ENTERED @ {price:.2f} | Qty={qty}")

    # ----------------------------------------------------
    # EXIT LOGIC
    # ----------------------------------------------------
    else:

        if position == "LONG":
            tp = entry_price * (1 + TP_PCT)
            sl = entry_price * (1 - SL_PCT)

            if price >= tp:
                pnl = (price - entry_price) * qty
                realised_pnl += pnl
                capital += pnl
                print(f"✅ LONG TP HIT @ {price:.2f} | Profit={pnl:.2f}")
                position = None

            elif price <= sl:
                pnl = (price - entry_price) * qty
                realised_pnl += pnl
                capital += pnl
                print(f"❌ LONG SL HIT @ {price:.2f} | Loss={pnl:.2f}")
                position = None

        elif position == "SHORT":
            tp = entry_price * (1 - TP_PCT)
            sl = entry_price * (1 + SL_PCT)

            if price <= tp:
                pnl = (entry_price - price) * qty
                realised_pnl += pnl
                capital += pnl
                print(f"✅ SHORT TP HIT @ {price:.2f} | Profit={pnl:.2f}")
                position = None

            elif price >= sl:
                pnl = (entry_price - price) * qty
                realised_pnl += pnl
                capital += pnl
                print(f"❌ SHORT SL HIT @ {price:.2f} | Loss={pnl:.2f}")
                position = None

    print_position_status(price)

    if time.time() - last_summary >= SUMMARY_INTERVAL:
        print("\n⏳ ====== 100-SEC SUMMARY ======")
        print(f"Capital: {capital:.2f}")
        print(f"Realised PNL: {realised_pnl:.2f}")
        if position:
            if position == "LONG":
                unreal = (price - entry_price) * qty
            else:
                unreal = (entry_price - price) * qty
            print(f"Unrealised PNL: {unreal:.2f} ({position})")
        else:
            print("No open positions")
        print("==============================\n")

        last_summary = time.time()

    time.sleep(SLEEP_SECONDS)
