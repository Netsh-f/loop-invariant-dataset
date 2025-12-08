# build_dataset.py
import os
import json
from config import RAW_LOOPS_DIR, ABSTRACTED_DIR, VERIFIED_DIR


def load_json_dir(path):
    data = {}
    for f in os.listdir(path):
        if f.endswith('.json'):
            with open(os.path.join(path, f)) as fp:
                d = json.load(fp)
                data[d["id"]] = d
    return data


def main():
    raw = load_json_dir(RAW_LOOPS_DIR)
    abs_data = load_json_dir(ABSTRACTED_DIR)
    ver_data = load_json_dir(VERIFIED_DIR)

    cleaned = []
    skipped_count = 0

    for loop_id in raw:
        # 必须三个阶段都有
        if loop_id not in abs_data or loop_id not in ver_data:
            continue

        item = {**raw[loop_id], **abs_data[loop_id], **ver_data[loop_id]}

        # ✅ 关键过滤：跳过未验证或被跳过的循环
        if not item.get("verified", False):
            skipped_count += 1
            continue

        # 可选：再检查 log 是否含 "Skipped"（防御性）
        cbmc_log = item.get("cbmc_log", "")
        if isinstance(cbmc_log, str) and cbmc_log.startswith("Skipped"):
            skipped_count += 1
            continue

        # 移除中间字段
        item.pop("ptr_vars", None)

        cleaned.append(item)

    print(f"✅ Kept: {len(cleaned)} verified loops")
    print(f"🗑️  Skipped: {skipped_count} unsupported/failed loops")

    # 保存最终数据集
    os.makedirs("output", exist_ok=True)
    with open("output/dataset.json", 'w') as f:
        json.dump(cleaned, f, indent=2)

    # 检查是否达到 100 条
    if len(cleaned) >= 100:
        print("🎉 Dataset meets minimum requirement (≥100 verified loops)!")
    else:
        print(f"⚠️  Warning: Only {len(cleaned)} verified loops (<100)")


if __name__ == "__main__":
    main()
