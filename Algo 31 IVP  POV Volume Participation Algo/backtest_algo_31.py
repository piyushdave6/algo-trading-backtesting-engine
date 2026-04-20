import pandas as pd
import numpy as np
import os
import glob

# Paths relative to the script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Execution Parameters
TOTAL_ORDER = 10000
POV_TARGET = 0.10
CATCHUP_MULT = 1.5
SLOWDOWN_MULT = 0.6

def run_single_backtest(filepath):
    ticker = os.path.basename(filepath).split("_")[0]
    print(f"  Processing {ticker}...")

    try:
        df = pd.read_excel(filepath)
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return None

    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df = df.sort_values("Datetime").reset_index(drop=True)

    execution_log = []
    executed = 0
    cumulative_market_vol = 0
    total_cost = 0

    for i in range(len(df)):
        if executed >= TOTAL_ORDER: break
        
        row = df.iloc[i]
        price = row["Close"]
        mv = row["Volume"]
        time = row["Datetime"]
        
        cumulative_market_vol += mv
        target_participation = cumulative_market_vol * POV_TARGET
        gap = target_participation - executed
        
        if gap > 0:
            slice_units = int(gap * CATCHUP_MULT)
            reason = "Catch-up"
        else:
            slice_units = max(1, int(abs(gap) * SLOWDOWN_MULT))
            reason = "Slow-down"
            
        slice_units = max(1, min(slice_units, TOTAL_ORDER - executed))
        
        executed += slice_units
        total_cost += slice_units * price
        
        execution_log.append({
            "Time": time, "Price": price, "Market_Vol": mv, "Target_POV": int(target_participation),
            "Executed": executed, "Slice": slice_units, "Reason": reason
        })

    if not execution_log:
        return None

    exec_df = pd.DataFrame(execution_log)
    avg_price = total_cost / executed if executed > 0 else 0
    vwap_market = (df["Close"] * df["Volume"]).sum() / df["Volume"].sum()
    
    report_filename = f"Algo_31_POV_Report_{ticker}.xlsx"
    report_path = os.path.join(REPORTS_DIR, report_filename)
    if not os.path.exists(REPORTS_DIR): os.makedirs(REPORTS_DIR)
    with pd.ExcelWriter(report_path) as writer:
        pd.DataFrame({"Metric": ["Ticker", "Target Order", "Actual Executed", "Avg Price", "Market VWAP", "POV %"],
                      "Value": [ticker, TOTAL_ORDER, executed, round(avg_price, 2), round(vwap_market, 2), round((executed/cumulative_market_vol)*100, 2)]}).to_excel(writer, sheet_name="Dashboard", index=False)
        exec_df.to_excel(writer, sheet_name="Execution Log", index=False)

    return {"Ticker": ticker, "Executed": executed, "Avg_Price": avg_price, "Market_VWAP": vwap_market}

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
        pd.DataFrame(summary_stats).to_excel(os.path.join(REPORTS_DIR, "Algo_31_POV_Consolidated_Summary.xlsx"), index=False)

if __name__ == "__main__":
    run_all()
