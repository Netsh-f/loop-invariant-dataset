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
    abs = load_json_dir(ABSTRACTED_DIR)
    ver = load_json_dir(VERIFIED_DIR)

    cleaned = []
    for id in raw:
        if id in abs and id in ver:
            item = {**raw[id], **abs[id], **ver[id]}
            # Remove redundant fields
            item.pop("ptr_vars", None)
            cleaned.append(item)

    print(f"Cleaned dataset size: {len(cleaned)}")
    with open("output/dataset.json", 'w') as f:
        json.dump(cleaned, f, indent=2)


if __name__ == "__main__":
    main()
