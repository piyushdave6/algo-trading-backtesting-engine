import pandas as pd
import numpy as np
import os
import glob

# Paths relative to the script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Strategy Parameters
ALGO_NAME = "Algo_19_HMA"
HMA_FAST_LEN = 9
HMA_SLOW_LEN = 21
TP = 0.005
SL = 0.01
QTY = 100
WARMUP = 21

def wma(values, period):
    if len(values) < period: return None
    weights = np.arange(1, period + 1)
    return np.dot(values[-period:], weights) / weights.sum()

def calculate_hma(prices_series, period):
    if len(prices_series) < period: return None
    half_len = period // 2
    sqrt_len = int(np.sqrt(period))
    
    raw_hma_values = []
    for i in range(sqrt_len):
        end_idx = len(prices_series) - i
        sub_prices = prices_series[:end_idx]
        w_half = wma(sub_prices, half_len)
        w_full = wma(sub_prices, period)
        if w_half is None or w_full is None: return None
        raw_hma_values.append(2 * w_half - w_full)
    
    return wma(np.array(raw_hma_values[::-1]), sqrt_len)

def run_single_backtest(filepath):
    ticker = os.path.basename(filepath).split("_")[0]
    print(f"  Processing {ticker}...")

    try:
        df = pd.read_excel(filepath)
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return None

    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df["Date"] = df["Datetime"].dt.date
    df = df.sort_values("Datetime").reset_index(drop=True)

    trade_log = []
    equity_curve = []
    cumulative_pnl = 0

    for day, day_df in df.groupby("Date"):
        day_df = day_df.reset_index(drop=True)
        day_initial_price = day_df.iloc[0]["Close"]
        day_capital = QTY * day_initial_price

        prices = []
        position = 0
        entry_price = 0
        entry_time = None
        waiting_for_warmup = True
        counter = 0

        for i in range(len(day_df)):
            price = day_df.iloc[i]["Close"]
            time = day_df.iloc[i]["Datetime"]
            prices.append(price)

            if waiting_for_warmup:
                counter += 1
                if counter < WARMUP:
                    equity_curve.append({"Datetime": time, "Daily_Equity": day_capital, "Cumulative_PnL": cumulative_pnl})
                    continue
                else:
                    waiting_for_warmup = False

            # HMA Logic
            hma_fast = calculate_hma(prices, HMA_FAST_LEN)
            hma_slow = calculate_hma(prices, HMA_SLOW_LEN)
            hma_fast_prev = calculate_hma(prices[:-1], HMA_FAST_LEN)
            
            if hma_fast is None or hma_slow is None or hma_fast_prev is None:
                equity_curve.append({"Datetime": time, "Daily_Equity": day_capital, "Cumulative_PnL": cumulative_pnl})
                continue

            slope = hma_fast - hma_fast_prev

            if position == 0:
                if hma_fast > hma_slow and slope > 0:
                    position = 1
                    entry_price = price
                    entry_time = time
                elif hma_fast < hma_slow and slope < 0:
                    position = -1
                    entry_price = price
                    entry_time = time
            else:
                # Exit Logic: TP / SL
                tp_price = entry_price * (1 + TP if position == 1 else 1 - TP)
                sl_price = entry_price * (1 - SL if position == 1 else 1 + SL)

                exit_flag = False
                reason = ""

                if (position == 1 and price >= tp_price) or (position == -1 and price <= tp_price):
                    exit_flag = True
                    reason = "TP"
                elif (position == 1 and price <= sl_price) or (position == -1 and price >= sl_price):
                    exit_flag = True
                    reason = "SL"
                elif (position == 1 and slope < 0) or (position == -1 and slope > 0):
                    exit_flag = True
                    reason = "Slope Flip"

                if exit_flag:
                    pnl = (price - entry_price) * QTY if position == 1 else (entry_price - price) * QTY
                    cumulative_pnl += pnl
                    trade_log.append({
                        "Ticker": ticker, "Date": day, "Entry_Time": entry_time, "Exit_Time": time,
                        "Type": "LONG" if position == 1 else "SHORT", "Entry": entry_price, "Exit": price,
                        "PnL": pnl, "Reason": reason
                    })
                    position = 0
                    waiting_for_warmup = True
                    counter = 0

            equity_curve.append({"Datetime": time, "Daily_Equity": day_capital + (price - entry_price)*QTY*position, "Cumulative_PnL": cumulative_pnl})

        # EOD Square-off
        if position != 0:
            last_price = day_df.iloc[-1]["Close"]
            last_time = day_df.iloc[-1]["Datetime"]
            pnl = (last_price - entry_price) * QTY if position == 1 else (entry_price - last_price) * QTY
            cumulative_pnl += pnl
            trade_log.append({
                "Ticker": ticker, "Date": day, "Entry_Time": entry_time, "Exit_Time": last_time,
                "Type": "LONG" if position == 1 else "SHORT", "Entry": entry_price, "Exit": last_price,
                "PnL": pnl, "Reason": "EOD"
            })

    if not trade_log:
        return {"Ticker": ticker, "Total_Trades": 0, "Win_Rate": 0, "Total_PnL": 0}

    trades_df = pd.DataFrame(trade_log)
    total_trades = len(trades_df)
    wins = len(trades_df[trades_df["PnL"] > 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    total_pnl = trades_df["PnL"].sum()

    report_filename = f"{ALGO_NAME}_Report_{ticker}.xlsx"
    report_path = os.path.join(REPORTS_DIR, report_filename)
    if not os.path.exists(REPORTS_DIR): os.makedirs(REPORTS_DIR)
    with pd.ExcelWriter(report_path) as writer:
        pd.DataFrame({"Metric": ["Ticker", "Total Trades", "Win Rate (%)", "Total PnL"],
                      "Value": [ticker, total_trades, round(win_rate, 2), round(total_pnl, 2)]}).to_excel(writer, sheet_name="Dashboard", index=False)
        trades_df.to_excel(writer, sheet_name="Trade Log", index=False)

    return {"Ticker": ticker, "Total_Trades": total_trades, "Win_Rate": win_rate, "Total_PnL": total_pnl}

def run_all():
    if not os.path.exists(REPORTS_DIR): os.makedirs(REPORTS_DIR)
    files = glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
    if not files:
        print(f"No data files found in {DATA_DIR}.")
        return
    summary_stats = []
    for f in files:
        stats = run_single_backtest(f)
        if stats: summary_stats.append(stats)
    if summary_stats:
        pd.DataFrame(summary_stats).to_excel(os.path.join(REPORTS_DIR, f"{ALGO_NAME}_Consolidated_Summary.xlsx"), index=False)

if __name__ == "__main__":
    run_all()
