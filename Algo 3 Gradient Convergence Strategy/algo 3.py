# AlgoStrategy.py
import json
import time
import numpy as np
import sys

def get_live_price():
    """Reads the latest price from price_data.json"""
    try:
        with open("price_data.json", "r") as f:
            data = json.load(f)
            return data["price"]
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def mean_reversion_strategy(prices, alpha=0.1):
    """Implements gradient-based mean reversion logic."""
    if len(prices) < 5:
        return 0  # Not enough data to trade
    
    current_price = prices[-1]
    mean_price = np.mean(prices[-5:])  # short moving average
    gradient = 2 * (current_price - mean_price)

    # Trade signal based on gradient
    if gradient > 0:
        position = -1  # Overvalued -> short
    elif gradient < 0:
        position = 1   # Undervalued -> long
    else:
        position = 0

    # Step size (position scale)
    step_size = -alpha * gradient

    return position, step_size, gradient, mean_price

def main():
    print("🤖 Starting Gradient Convergence Algo Trading (Safe Mode)...\n")
    prices = []
    cash = 100000  # initial capital
    start_equity = cash
    position = 0
    last_summary_time = time.time()

    # Define stop-loss threshold (5% drawdown)
    stop_loss_limit = start_equity * 0.95

    while True:
        price = get_live_price()
        if price is None:
            print("Waiting for price data...")
            time.sleep(3)
            continue

        prices.append(price)
        if len(prices) > 50:
            prices.pop(0)

        signal = mean_reversion_strategy(prices)
        if signal == 0:
            time.sleep(3)
            continue

        position, step_size, gradient, mean_price = signal
        trade_value = step_size * 100  # scale trade

        # Update cash based on position
        cash += -position * trade_value
        equity = cash + position * price

        print(f"Price: ₹{price:,.2f} | Mean: ₹{mean_price:,.2f} | Gradient: {gradient:+.2f} | "
              f"Pos: {position:+} | Step: {step_size:+.4f} | Equity: ₹{equity:,.2f}")

        # 🚨 Check for 5% capital loss stop
        if equity <= stop_loss_limit:
            loss_amount = start_equity - equity
            print("\n==============================")
            print("🚨 STOP LOSS TRIGGERED!")
            print(f"💔 Equity fell below 5% limit.")
            print(f"❌ Total Loss: ₹{loss_amount:,.2f}")
            print(f"🛑 Trading stopped automatically to prevent further loss.")
            print("==============================\n")
            sys.exit(0)  # safely stop execution

        # 🧾 Every 100 seconds, show Profit/Loss summary
        current_time = time.time()
        if current_time - last_summary_time >= 100:
            profit_loss = equity - start_equity
            status = "PROFIT" if profit_loss > 0 else "LOSS"
            print("\n==============================")
            print(f"🕒 100-Second Summary:")
            print(f"💰 Current Equity: ₹{equity:,.2f}")
            print(f"📊 Total {status}: ₹{profit_loss:,.2f}")
            print("==============================\n")
            last_summary_time = current_time

        # ⏰ Slow loop
        time.sleep(7)

if __name__ == "__main__":
    main()
