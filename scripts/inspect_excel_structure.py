"""
Dump the raw table structure of a bank Excel pricelist so we can see
exactly how columns are laid out (fee-name column vs price columns vs
channel/sub-headers). Diagnostic only -- writes nothing.

Run:  python scripts/inspect_excel_structure.py excel/leumi.xls [max_rows]
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: inspect_excel_structure.py <excel_path> [max_rows]")
        return 1
    path = sys.argv[1]
    if not Path(path).is_absolute():
        path = str(ROOT / path)
    max_rows = int(sys.argv[2]) if len(sys.argv) > 2 else 40

    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=str)
    print(f"FILE: {path}")
    print(f"SHEETS: {list(sheets.keys())}\n")

    for name, df in sheets.items():
        df = df.fillna("")
        print(f"===== sheet '{name}'  shape={df.shape} =====")
        shown = 0
        for idx, row in df.iterrows():
            cells = [str(c).strip() for c in row.tolist()]
            nonempty = [(i, c) for i, c in enumerate(cells) if c and c.lower() != "nan"]
            if not nonempty:
                continue
            # show as col[i]=value so we see which column holds what
            rendered = "  ".join(f"c{i}={c[:34]!r}" for i, c in nonempty)
            print(f"  r{idx:>3}: {rendered}")
            shown += 1
            if shown >= max_rows:
                print(f"  ... (stopped after {max_rows} non-empty rows)")
                break
        print()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
