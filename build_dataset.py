import os
import subprocess
from config import OUTPUT_DIR


def run_script(name):
    print(f"Running {name}...")
    subprocess.run(["python", name], check=True)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    run_script("extract_loops.py")
    run_script("abstract_loop.py")
    run_script("verify_invariant.py")
    run_script("clean_data.py")
    print("✅ Dataset built at output/dataset.json")


if __name__ == "__main__":
    main()
