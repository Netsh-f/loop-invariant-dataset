# analyze_results.py
import os
import json
from pathlib import Path


def main():
    verified_dir = Path("output/verified")

    if not verified_dir.exists():
        print(f"Directory {verified_dir} does not exist!")
        return

    total = 0
    verified_true = 0
    verified_false = 0
    skipped = 0

    false_cases = []

    for json_file in verified_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)

            total += 1
            if "verified" not in data:
                skipped += 1
                continue

            if data["verified"] is True:
                verified_true += 1
            elif data["verified"] is False:
                verified_false += 1
                false_cases.append(data["id"])
            else:
                skipped += 1

        except Exception as e:
            print(f"Error reading {json_file}: {e}")
            skipped += 1

    print("=" * 50)
    print("📊 Loop Invariant Verification Results")
    print("=" * 50)
    print(f"Total loops processed : {total}")
    print(f"Verified successfully : {verified_true}")
    print(f"Verification failed   : {verified_false}")
    print(f"Skipped / invalid     : {skipped}")
    print("-" * 50)

    if total > 0:
        success_rate = (verified_true / total) * 100
        print(f"✅ Success rate: {success_rate:.2f}%")
    else:
        print("No valid results found.")

    if false_cases:
        print("\n❌ Failed cases (first 10):")
        for case in false_cases[:10]:
            print(f"  - {case}")
        if len(false_cases) > 10:
            print(f"  ... and {len(false_cases) - 10} more")

    print("=" * 50)


if __name__ == "__main__":
    main()
