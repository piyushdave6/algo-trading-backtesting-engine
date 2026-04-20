# trading_bot.py
import json
import time
from datetime import datetime, timedelta

def read_price():
    """Read the latest price from JSON file."""
    try:
        with open("price_data.json", "r") as f:
            data = json.load(f)
            return data.get("price", None)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def trading_bot():
    initial_balance = 100000
    balance = initial_balance
    shares = 0
    avg_price = 0
    last_price = None

    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=375)

    print("🤖 Trading bot started (target: 2% profit, max time: 375 min)...\n")

    while datetime.now() < end_time:
        price = read_price()
        if price is None:
            print("Waiting for price update...")
            time.sleep(2)
            continue

        # Initialize first buy
        if shares == 0:
            shares += 1
            balance -= price
            avg_price = price
            print(f"🟢 Bought 1 share at ₹{price} (Initial Buy)")
            last_price = price
            time.sleep(5)
            continue

        # If price rises → hold
        if price > last_price:
            print(f"📈 Price rising: ₹{price} (Holding {shares} shares)")

        # If price drops → buy 2 more shares (average down)
        elif price < last_price:
            if balance >= price * 2:
                shares += 2
                balance -= price * 2
                avg_price = ((avg_price * (shares - 2)) + price * 2) / shares
                print(f"🔵 Averaged down, bought 2 shares at ₹{price}. New avg: ₹{avg_price:.2f}")
            else:
                print(f"⚠️ Not enough balance to average down at ₹{price}")

        # Calculate portfolio value
        total_value = balance + shares * price
        profit = total_value - initial_balance
        profit_percent = (profit / initial_balance) * 100

        print(f"💰 Portfolio: ₹{total_value:.2f} | P/L: ₹{profit:.2f} ({profit_percent:.2f}%)")

        # Stop if profit ≥ 2%
        if profit_percent >= 2:
            balance += shares * price
            print(f"\n✅ Target reached! Sold all {shares} shares at ₹{price}")
            shares = 0
            break

        last_price = price
        time.sleep(5)

    # Final report
    final_price = read_price() or 0
    total_value = balance + shares * final_price
    profit = total_value - initial_balance
    profit_percent = (profit / initial_balance) * 100

    print("\n📊 === FINAL SUMMARY ===")
    print(f"Final stock price: ₹{final_price}")
    print(f"Cash balance: ₹{balance}")
    print(f"Shares owned: {shares}")
    print(f"Total portfolio value: ₹{total_value:.2f}")
    print(f"Net profit/loss: ₹{profit:.2f} ({profit_percent:.2f}%)")
    if profit_percent >= 2:
        print("🎯 Target Achieved!")
    else:
        print("⏰ Max time reached (375 min). Stopped without hitting target.")

if __name__ == "__main__":
    trading_bot()
