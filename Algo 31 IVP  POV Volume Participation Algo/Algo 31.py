# POV_Algo_Simple_Summary.py
"""
POV Algo - Simple Output + Final Summary
----------------------------------------
Shows:
- Clean per-tick output
- Full execution summary at the end
"""

import json
import time
from datetime import datetime

PRICE_FILE = "price_data.json"
LOG_FILE = "pov_log.json"

POV_PERCENT = 0.10               # Now using 10%
TOTAL_ORDER = 10000
SIDE = "BUY"
CHECK_INTERVAL = 3

CATCHUP_MULT = 1.5
SLOWDOWN_MULT = 0.6
BASE_VOLUME_REFERENCE = 1000     # For educational display only


def read_market():
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return int(data["price"]), int(data["volume"])
    except:
        return None, None


def append_log(entry):
    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
    except:
        logs = []
    logs.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)


def main():
    print("\n📈 POV Algo Started (Simple Mode)\n")

    executed = 0
    cumulative_mv = 0

    slice_count = 0
    catchup_count = 0
    slowdown_count = 0
    total_slice_units = 0

    while executed < TOTAL_ORDER:

        price, mv = read_market()
        if price is None:
            print("Waiting for exchange...")
            time.sleep(2)
            continue

        cumulative_mv += mv
        pov_target = cumulative_mv * POV_PERCENT
        gap = pov_target - executed

        # slice calculation
        if gap > 0:
            slice_units = int(gap * CATCHUP_MULT)
            reason = "Catch-up"
            catchup_count += 1
        else:
            slice_units = max(1, int(abs(gap) * SLOWDOWN_MULT))
            reason = "Slow-down"
            slowdown_count += 1

        slice_units = max(1, min(slice_units, TOTAL_ORDER - executed))
        executed += slice_units

        slice_count += 1
        total_slice_units += slice_units

        # simple output
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}]")
        print(f"Price: {price} | MV: {mv} | Cumulative MV: {cumulative_mv}")
        print(f"POV Target: {int(pov_target)} | Executed: {executed - slice_units} | Gap: {gap:.1f}")
        print(f"Slice: {slice_units} units ({reason})")

        append_log({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "price": price,
            "market_volume": mv,
            "cumulative_mv": cumulative_mv,
            "pov_target": round(pov_target, 2),
            "gap": gap,
            "slice_units": slice_units,
            "executed_so_far": executed,
            "reason": reason
        })

        time.sleep(CHECK_INTERVAL)

    # -------------------------------
    # ⭐ FINAL SUMMARY
    # -------------------------------
    final_participation = (executed / cumulative_mv) * 100
    avg_slice = total_slice_units / slice_count

    print("\n----------------------------------------------")
    print("            📊 POV EXECUTION SUMMARY")
    print("----------------------------------------------")
    print(f"Total Order Size       : {TOTAL_ORDER} units")
    print(f"POV Target (%)         : {POV_PERCENT*100:.1f}%\n")

    print(f"Total Market Volume    : {cumulative_mv} units")
    print(f"Required Participation : {int(cumulative_mv * POV_PERCENT)} units")
    print(f"Actual Executed        : {executed} units\n")

    print(f"Final Participation %  : {final_participation:.2f}%\n")

    print(f"Total Slices Executed  : {slice_count}")
    print(f"Average Slice Size     : {avg_slice:.0f} units\n")

    print(f"Catch-up Slices        : {catchup_count}")
    print(f"Slow-down Slices       : {slowdown_count}\n")

    if final_participation > POV_PERCENT * 100:
        print("Execution Performance  : ABOVE POV target")
    else:
        print("Execution Performance  : BELOW POV target")

    print("Reason                 : Based on real-time market volumes")
    print("----------------------------------------------")
    print("✅ POV Completed!\n")


if __name__ == "__main__":
    main()
