import json
import time
from datetime import datetime
from collections import deque

# ================= PARAMETERS =================
DATA_FILE = "price_data.json"

MAX_QTY = 100
LOOP_SLEEP = 2

ROLLING_WINDOW = 10   # 🔑 KEY FIX: conviction over time
# ==============================================


def read_buy_sell_volume():
    """
    Expected JSON format:
    {
        "price": 1012,
        "volume": 2400,
        "buy_volume": 1680,
        "sell_volume": 720,
        "timestamp": "2026-01-03T10:32:15Z"
    }
    """
    try:
        with open(DATA_FILE, "r") as f:
            d = json.load(f)
            return float(d["buy_volume"]), float(d["sell_volume"])
    except:
        return None, None


def compute_vpi(buy_vol, sell_vol):
    total = buy_vol + sell_vol
    if total == 0:
        return 0.0
    return (buy_vol - sell_vol) / total


def quantity_from_vpi(vpi):
    strength = abs(vpi)

    if strength < 0.20:
        return 0
    elif strength < 0.40:
        return int(MAX_QTY * 0.25)
    elif strength < 0.60:
        return int(MAX_QTY * 0.50)
    elif strength < 0.80:
        return int(MAX_QTY * 0.75)
    else:
        return MAX_QTY


def market_state_from_vpi(vpi):
    s = abs(vpi)
    if s < 0.20:
        return "BALANCED (NO TRADE)"
    elif s < 0.40:
        return "WEAK DOMINANCE"
    elif s < 0.60:
        return "CLEAR DOMINANCE"
    elif s < 0.80:
        return "STRONG CONTROL"
    else:
        return "EXTREME CONTROL"


def main():
    print("\n🤖 VPI Quantity Engine — FINAL (Rolling Conviction Enabled)")
    print("📌 Pure Volume | No Direction | Max Qty = 100\n")

    buy_buffer = deque(maxlen=ROLLING_WINDOW)
    sell_buffer = deque(maxlen=ROLLING_WINDOW)

    while True:
        buy_vol, sell_vol = read_buy_sell_volume()

        if buy_vol is None:
            print("⚠️ Waiting for buy/sell volume data...")
            time.sleep(2)
            continue

        # ---- ROLLING ACCUMULATION ----
        buy_buffer.append(buy_vol)
        sell_buffer.append(sell_vol)

        rolling_buy = sum(buy_buffer)
        rolling_sell = sum(sell_buffer)

        vpi = compute_vpi(rolling_buy, rolling_sell)
        qty = quantity_from_vpi(vpi)
        state = market_state_from_vpi(vpi)

        print("=" * 75)
        print(f"🕒 Time            : {datetime.now().strftime('%H:%M:%S')}")
        print(f"📦 Rolling Buy Vol : {rolling_buy:,.0f}")
        print(f"📦 Rolling Sell Vol: {rolling_sell:,.0f}")
        print(f"📊 VPI (rolling)   : {vpi:+.3f}")
        print(f"📐 |VPI|           : {abs(vpi):.3f}")
        print(f"🧠 Market State    : {state}")
        print(f"🧮 Quantity        : {qty} / {MAX_QTY}")

        if qty == 0:
            print("⚪ ACTION: STAY FLAT")
        elif qty < MAX_QTY:
            print("🟡 ACTION: PARTICIPATE (SCALED SIZE)")
        else:
            print("🔥 ACTION: MAX PARTICIPATION")

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()
