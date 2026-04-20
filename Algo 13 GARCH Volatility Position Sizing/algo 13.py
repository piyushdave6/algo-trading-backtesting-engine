import json
import time
import numpy as np
from datetime import datetime
from collections import deque

# ========== PARAMETERS ==========
PRICE_FILE = "price_data.json"
TICKS_PER_CANDLE = 5            # keep same exchange ticks
WARMUP_CANDLES = 8              # candles for stable base
RISK_PCT = 0.005                # 0.5% of capital at risk
BASE_CAPITAL = 100000

# --- GARCH(1,1) parameters tuned for small price movement ---
OMEGA = 0.000010   # baseline variance (was too small before)
ALPHA = 0.25       # faster reaction to shocks
BETA = 0.65        # smoother persistence

MIN_VOL_PER_UNIT = 5.0          # ₹5 volatility floor
LOOP_SLEEP = 1.2
# ============================================================

def read_price():
    """Read live price from Exchange.py file."""
    try:
        with open(PRICE_FILE, "r") as f:
            return float(json.load(f)["price"])
    except Exception:
        return None


def main():
    print("📈 Starting GARCH(1,1) Volatility Forecasting — Dynamic Trade Sizing v4\n")

    tick_buffer = []
    prices = deque(maxlen=200)
    capital = BASE_CAPITAL
    risk_cash = BASE_CAPITAL * RISK_PCT

    prev_close = None
    sigma2_prev = 0.0001  # initial variance (1%²)

    try:
        while True:
            # ---- Read price from Exchange.py ----
            price = read_price()
            if price is None:
                print("⚠️ Waiting for price feed...")
                time.sleep(1)
                continue

            tick_buffer.append(price)
            print(f"Tick collected: ₹{price:.2f}  (buf {len(tick_buffer)}/{TICKS_PER_CANDLE})")
            time.sleep(LOOP_SLEEP)

            # ---- Form a new candle ----
            if len(tick_buffer) >= TICKS_PER_CANDLE:
                o, h, l, c = tick_buffer[0], max(tick_buffer), min(tick_buffer), tick_buffer[-1]
                tick_buffer.clear()
                prices.append(c)

                print("--------------------------------------------------")
                print(f"Candle @ {datetime.now().strftime('%H:%M:%S')}: C:{c:.2f} | Collected candles: {len(prices)}")

                # First candle — skip since no previous close
                if prev_close is None:
                    prev_close = c
                    continue

                # ---- Calculate return and update volatility ----
                r_t = (c - prev_close) / prev_close
                eps2 = r_t ** 2

                # GARCH(1,1) recursive variance
                sigma2 = OMEGA + ALPHA * eps2 + BETA * sigma2_prev
                sigma = np.sqrt(sigma2)

                # ---- Update memory ----
                delta_sigma = sigma2 - sigma2_prev
                sigma2_prev = sigma2
                prev_close = c

                # ---- Volatility → Sizing ----
                vol_per_unit = max(MIN_VOL_PER_UNIT, sigma * c)
                units = max(1, int(risk_cash / vol_per_unit))
                risk_used = min(risk_cash, units * vol_per_unit)

                # ---- Output ----
                print(f"Forecast vol: {sigma*100:.4f}% | Vol/Unit ₹{vol_per_unit:.2f}")
                print(f"Suggested units: {units} | Risk used ₹{risk_used:.2f}")
                print(f"🔄 Prev σ²: {sigma2_prev:.8f} | Curr σ²: {sigma2:.8f} | Δ {delta_sigma:.10f}")

                # Environment hint
                if sigma * 100 > 1.5:
                    print(f"⚡ High volatility ({sigma*100:.2f}%) — smaller position.\n")
                elif sigma * 100 < 0.3:
                    print(f"🌙 Very calm market ({sigma*100:.2f}%) — larger sizing.\n")
                else:
                    print(f"✅ Normal volatility ({sigma*100:.2f}%) — balanced trade sizing.\n")

                # Warm-up
                if len(prices) < WARMUP_CANDLES:
                    print(f"🕒 Warm-up phase ({len(prices)}/{WARMUP_CANDLES})...\n")
                    continue

                # Every few candles — show rolling snapshot
                if len(prices) % 5 == 0:
                    print(f"📊 Rolling σ (vol): {sigma*100:.3f}% | Variance={sigma2:.8f}\n")

    except KeyboardInterrupt:
        print("\n🛑 Interrupted manually. Exiting safely.")

    finally:
        print("\n📘 Final Session Summary:")
        print(f"Total candles processed: {len(prices)}")
        print("✅ Algo stopped safely.\n")


if __name__ == "__main__":
    main()
