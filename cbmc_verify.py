import json
import os
import subprocess
import tempfile

# 配置
INPUT_JSON = "output/loop_invariant_dataset.json"
OUTPUT_JSON = "output/dataset_with_cbmc_results.json"
CBMC_TIMEOUT = 60  # 秒，防止卡死
CBMC_ARGS = [
    "--bounds-check",
    "--pointer-check",
    "--div-by-zero-check",
    "--unwind", "100",
]


def run_cbmc_on_code(c_code: str) -> dict:
    """
    Run CBMC on the given C code string.
    Returns: {"log": str, "result": "SUCCESS" | "FAILURE" | "ERROR"}
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as tmp:
        tmp.write(c_code)
        tmp_path = tmp.name

    try:
        cmd = ["cbmc"] + CBMC_ARGS + [tmp_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CBMC_TIMEOUT
        )
        log = result.stdout + result.stderr
        if result.returncode == 0 and "VERIFICATION SUCCESSFUL" in result.stdout:
            verification_result = "SUCCESS"
        else:
            verification_result = "FAILURE"
    except subprocess.TimeoutExpired:
        log = f"CBMC timed out after {CBMC_TIMEOUT} seconds."
        verification_result = "ERROR"
    except Exception as e:
        log = f"Exception during CBMC execution: {e}"
        verification_result = "ERROR"
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return {
        "log": log,
        "result": verification_result
    }


def main():
    print(f"Loading dataset from {INPUT_JSON}")
    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        loops = json.load(f)

    total = len(loops)
    print(f"Found {total} loops to verify.")

    for idx, loop in enumerate(loops):
        if "verify_code" not in loop or not loop["verify_code"].strip():
            print(f"[{idx + 1}/{total}] Skipping: no verify code")
            loop["cbmc_log"] = "No verify code provided"
            loop["cbmc_result"] = "SKIPPED"
            continue

        print(
            f"[{idx + 1}/{total}] Running CBMC for loop at {loop.get('file_path', 'unknown')}:{loop.get('line', '?')}")
        cbmc_res = run_cbmc_on_code(loop["verify_code"])
        loop["cbmc_log"] = cbmc_res["log"]
        loop["cbmc_result"] = cbmc_res["result"]
        print("result: " + cbmc_res["result"])

    # Save updated dataset
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(loops, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Verification completed. Results saved to {OUTPUT_JSON}")

    # Print summary
    results = [loop["cbmc_result"] for loop in loops]
    from collections import Counter
    summary = Counter(results)
    print("\n📊 Summary:")
    for status, count in summary.items():
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
