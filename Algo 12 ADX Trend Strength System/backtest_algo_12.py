import pandas as pd
import numpy as np
import os
import glob

# Paths relative to the script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Strategy Parameters
ALGO_NAME = "Algo_12_ADX"
WINDOW = 14
ADX_THRESHOLD = 20
TP = 0.005
SL = 0.01
QTY = 100
WARMUP = 21

def calculate_adx(df, window):
    plus_dm = df['High'].diff()
    minus_dm = df['Low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    minus_dm = abs(minus_dm)
    
    # Smooth DM and TR
    tr1 = df['High'] - df['Low']
    tr2 = abs(df['High'] - df['Close'].shift(1))
    tr3 = abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(window=window).mean()
    plus_di = 100 * (plus_dm.rolling(window=window).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=window).mean() / atr)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    adx = dx.rolling(window=window).mean()
    
    return plus_di, minus_di, adx

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
        plus_di, minus_di, adx = calculate_adx(day_df, WINDOW)
        
        day_initial_price = day_df.iloc[0]["Close"]
        day_initial_capital = QTY * day_initial_price
        day_capital = day_initial_capital

        position = 0
        entry_price = 0
        entry_time = None
        waiting_for_warmup = True
        counter = 0

        for i in range(len(day_df)):
            row = day_df.iloc[i]
            price = row["Close"]
            time = row["Datetime"]

            if waiting_for_warmup:
                counter += 1
                if counter < WARMUP:
                    equity_curve.append({"Datetime": time, "Daily_Equity": day_capital, "Cumulative_PnL": cumulative_pnl})
                    continue
                else:
                    waiting_for_warmup = False

            # ADX Logic
            curr_adx = adx[i]
            curr_plus = plus_di[i]
            curr_minus = minus_di[i]
            prev_plus = plus_di[i-1]
            prev_minus = minus_di[i-1]

            if position == 0:
                if curr_adx > ADX_THRESHOLD:
                    # Long: +DI crosses above -DI
                    if prev_plus <= prev_minus and curr_plus > curr_minus:
                        position = 1
                        entry_price = price
                        entry_time = time
                    # Short: -DI crosses above +DI
                    elif prev_minus <= prev_plus and curr_minus > curr_plus:
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
                elif curr_adx < ADX_THRESHOLD:
                    exit_flag = True
                    reason = "Trend Weakening (ADX < 20)"
                elif (position == 1 and curr_minus > curr_plus) or (position == -1 and curr_plus > curr_minus):
                    exit_flag = True
                    reason = "DI Reverse"

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
