import pandas as pd
import numpy as np
import os
import glob

# Paths relative to the script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Strategy Parameters
ALGO_NAME = "Algo_9_SuperTrend"
WINDOW = 20
MULTIPLIER = 3.0
TP = 0.005
SL = 0.005
QTY = 100
WARMUP = 21

def calculate_atr(highs, lows, closes, window):
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    return np.mean(trs[-window:]) if trs else 0

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
        day_initial_capital = QTY * day_initial_price
        day_capital = day_initial_capital

        highs, lows, closes = [], [], []
        position = 0
        entry_price = 0
        entry_time = None
        
        waiting_for_warmup = True
        counter = 0
        
        supertrend = []
        trend = 1 # 1 for Up, -1 for Down
        upper_band = [0]
        lower_band = [0]

        for i in range(len(day_df)):
            row = day_df.iloc[i]
            price = row["Close"]
            high = row["High"]
            low = row["Low"]
            time = row["Datetime"]
            
            highs.append(high)
            lows.append(low)
            closes.append(price)

            if waiting_for_warmup:
                counter += 1
                if counter < WARMUP:
                    equity_curve.append({"Datetime": time, "Daily_Equity": day_capital, "Cumulative_PnL": cumulative_pnl})
                    # Dummy initial values
                    upper_band.append(0)
                    lower_band.append(0)
                    supertrend.append(0)
                    continue
                else:
                    waiting_for_warmup = False

            # SuperTrend Logic
            atr = calculate_atr(highs, lows, closes, WINDOW)
            hl2 = (high + low) / 2
            
            upper_basic = hl2 + (MULTIPLIER * atr)
            lower_basic = hl2 - (MULTIPLIER * atr)
            
            # Trailing Bands
            if trend == 1:
                # Current Upper Band
                new_upper = min(upper_basic, upper_band[-1]) if upper_band[-1] != 0 else upper_basic
                new_lower = lower_basic # In uptrend, lower basic is not strictly trailing in the same way, but usually it is.
                # Actually standard ST:
                new_lower = max(lower_basic, lower_band[-1]) if closes[-2] > lower_band[-1] else lower_basic
            else:
                new_upper = min(upper_basic, upper_band[-1]) if closes[-2] < upper_band[-1] else upper_basic
                new_lower = max(lower_basic, lower_band[-1]) if lower_band[-1] != 0 else lower_basic

            upper_band.append(new_upper)
            lower_band.append(new_lower)
            
            # Trend Direction
            prev_trend = trend
            if trend == 1 and price < new_lower:
                trend = -1
            elif trend == -1 and price > new_upper:
                trend = 1
            
            # Signal
            if position == 0:
                if trend == 1 and prev_trend == -1:
                    position = 1
                    entry_price = price
                    entry_time = time
                elif trend == -1 and prev_trend == 1:
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
                elif (position == 1 and trend == -1) or (position == -1 and trend == 1):
                    exit_flag = True
                    reason = "SuperTrend Flip"

                if exit_flag:
                    pnl = (price - entry_price) * QTY if position == 1 else (entry_price - price) * QTY
                    day_capital += pnl
                    cumulative_pnl += pnl
                    trade_log.append({
                        "Ticker": ticker, "Date": day, "Entry_Time": entry_time, "Exit_Time": time,
                        "Type": "LONG" if position == 1 else "SHORT", "Entry": entry_price, "Exit": price,
                        "PnL": pnl, "Reason": reason
                    })
                    position = 0
                    waiting_for_warmup = True
                    counter = 0

            equity_curve.append({"Datetime": time, "Daily_Equity": day_capital, "Cumulative_PnL": cumulative_pnl})

        # EOD Square-off
        if position != 0:
            last_price = day_df.iloc[-1]["Close"]
            last_time = day_df.iloc[-1]["Datetime"]
            pnl = (last_price - entry_price) * QTY if position == 1 else (entry_price - last_price) * QTY
            day_capital += pnl
            cumulative_pnl += pnl
            trade_log.append({
                "Ticker": ticker, "Date": day, "Entry_Time": entry_time, "Exit_Time": last_time,
                "Type": "LONG" if position == 1 else "SHORT", "Entry": entry_price, "Exit": last_price,
                "PnL": pnl, "Reason": "EOD"
            })
            if equity_curve and equity_curve[-1]["Datetime"] == last_time:
                equity_curve[-1]["Daily_Equity"] = day_capital
                equity_curve[-1]["Cumulative_PnL"] = cumulative_pnl

    if not trade_log:
        return {"Ticker": ticker, "Total_Trades": 0, "Win_Rate": 0, "Total_PnL": 0}

    trades_df = pd.DataFrame(trade_log)
    equity_df = pd.DataFrame(equity_curve)
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
        equity_df.to_excel(writer, sheet_name="Equity Curve", index=False)

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
        summary_df = pd.DataFrame(summary_stats)
        summary_path = os.path.join(REPORTS_DIR, f"{ALGO_NAME}_Consolidated_Summary.xlsx")
        summary_df.to_excel(summary_path, index=False)
        print(f"Backtest complete. Summary: {summary_path}")

if __name__ == "__main__":
    run_all()
