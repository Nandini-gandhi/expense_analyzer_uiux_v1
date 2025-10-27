import argparse
import sys
from src.clean_transactions import main as do_clean
from src.categorize_transactions import main as do_categorize
from src.plot_charts import main as do_charts

def main():
    p = argparse.ArgumentParser(description="expense-coach runner")
    p.add_argument("cmd", choices=["clean","categorize","charts"])
    p.add_argument("--month", default=None)
    args = p.parse_args()

    if args.cmd == "clean":
        do_clean()
    elif args.cmd == "categorize":
        do_categorize()
    elif args.cmd == "charts":
        sys.argv = ["plot_charts.py"] + (["--month", args.month] if args.month else [])
        do_charts()

if __name__ == "__main__":
    main()
