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
    success = 0
    skipped = 0
    cbmc_failed = 0

    skipped_cases = []
    cbmc_failed_cases = []

    for json_file in verified_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)

            total += 1
            log = data.get("cbmc_log", "")
            verified = data.get("verified")

            if verified is True:
                success += 1
            elif verified is False:
                if "Skipped:" in log:
                    skipped += 1
                    skipped_cases.append(data["id"])
                else:
                    cbmc_failed += 1
                    cbmc_failed_cases.append(data["id"])
            else:
                # Fallback: treat as skipped if 'verified' field missing
                skipped += 1
                skipped_cases.append(data["id"])

        except Exception as e:
            print(f"Error reading {json_file}: {e}")
            skipped += 1
            skipped_cases.append(json_file.stem)

    print("=" * 60)
    print("📊 Loop Invariant Verification Results (Detailed)")
    print("=" * 60)
    print(f"Total loops processed       : {total}")
    print(f"✅ Verified successfully     : {success}")
    print(f"⚠️  Skipped (unsupported)    : {skipped}")
    print(f"❌ CBMC verification failed  : {cbmc_failed}")
    print("-" * 60)

    if total > 0:
        support_rate = (success + cbmc_failed) / total * 100  # % of loops we attempted
        success_rate_among_supported = (success / (success + cbmc_failed) * 100) if (success + cbmc_failed) > 0 else 0
        print(f"🔧 Coverage (attempted)      : {support_rate:.2f}%")
        print(f"🎯 Success rate (of attempted): {success_rate_among_supported:.2f}%")
    print("=" * 60)

    # Optional: show examples of each category
    if cbmc_failed_cases:
        print("\n❌ Top 5 CBMC Verification Failures:")
        for case in cbmc_failed_cases[:5]:
            print(f"  - {case}")

    if skipped_cases:
        print(f"\n⚠️  Top 5 Skipped Loops (unsupported patterns):")
        for case in skipped_cases[:5]:
            print(f"  - {case}")

    print("\n💡 Interpretation:")
    print("  - 'Skipped' means the loop was too complex to abstract (e.g., function calls, struct members).")
    print("  - 'CBMC failed' means abstraction succeeded but invariant did NOT hold.")
    print("=" * 60)


if __name__ == "__main__":
    main()
