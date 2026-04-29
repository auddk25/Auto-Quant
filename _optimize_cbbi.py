"""Quick parameter sweep for CbbiLead strategy thresholds."""
import subprocess, sys, re, json
from pathlib import Path

STRATEGY_FILE = Path("user_data/strategies/MtfTrendCbbiLead.py")
ORIG = STRATEGY_FILE.read_text(encoding="utf-8")

# Test grid: entry CBBI threshold × exit CBBI threshold
entry_thresholds = [0.30, 0.35, 0.40, 0.45, 0.50]
exit_thresholds  = [0.60, 0.65, 0.70, 0.75, 0.80]

results = []
for e_entry in entry_thresholds:
    for e_exit in exit_thresholds:
        # Patch: find "< 0.XX" (entry) and "> 0.XX" (exit) in the strategy file
        patched = ORIG
        patched = re.sub(r'<\s*0\.\d+', f'< {e_entry}', patched, count=1)  # first match = entry
        patched = re.sub(r'>\s*0\.\d+', f'> {e_exit}', patched)             # all matches = exit lines
        STRATEGY_FILE.write_text(patched, encoding="utf-8")

        # Run backtest
        r = subprocess.run([sys.executable, "run.py"], capture_output=True, text=True, timeout=120)
        m = re.search(r'MtfTrendCbbiLead.*?total_profit_pct:\s*([\d.+-]+).*?trade_count:\s*(\d+)', r.stdout, re.DOTALL)
        if m:
            profit = float(m.group(1))
            trades = int(m.group(2))
            results.append((e_entry, e_exit, profit, trades))
            print(f"CBBI<{e_entry:.2f} / CBBI>{e_exit:.2f}: {profit:.2f}% ({trades}t)")
        else:
            print(f"CBBI<{e_entry:.2f} / CBBI>{e_exit:.2f}: error")

# Restore original
STRATEGY_FILE.write_text(ORIG, encoding="utf-8")

# Show top results
print("\n--- TOP 5 ---")
for r in sorted(results, key=lambda x: x[2], reverse=True)[:5]:
    print(f"Entry<{r[0]:.2f}  Exit>{r[1]:.2f}  =>  {r[2]:.2f}%  ({r[3]} trades)")
