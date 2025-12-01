import os
import json
import re
from config import RAW_LOOPS_DIR, ABSTRACTED_DIR


# 简化抽象策略：仅处理 *p 和 p++/--（适用于 musl 字符串函数）
def abstract_code(code, ptr_vars):
    """
    将指针操作替换为数组+索引。
    ptr_vars: {'h': 'h_idx', 'n': 'n_idx'}
    """
    s = code

    # 替换 *p -> arr_p[idx_p]
    for p, idx in ptr_vars.items():
        arr = f"arr_{p}"
        s = re.sub(rf'\*\s*{p}\b', f"{arr}[{idx}]", s)

    # 替换 p++ -> idx_p += 1
    for p, idx in ptr_vars.items():
        s = re.sub(rf'\b{p}\s*\+\+', f"{idx} += 1", s)
        s = re.sub(rf'\+\+\s*{p}\b', f"{idx} += 1", s)
        s = re.sub(rf'\b{p}\s*--', f"{idx} -= 1", s)
        s = re.sub(rf'--\s*{p}\b', f"{idx} -= 1", s)

    # 移除函数调用（摘要）
    s = re.sub(r'\b(memchr|memcmp|memcpy)\s*\(.*?\)', '__VERIFIER_assume(1)', s)

    return s


def guess_pointer_vars(code):
    # 启发式：出现在 *p 或 p++ 中的变量很可能是指针
    ptrs = set()
    for match in re.finditer(r'\*\s*(\w+)', code):
        ptrs.add(match.group(1))
    for match in re.finditer(r'(\w+)\s*\+\+', code):
        ptrs.add(match.group(1))
    for match in re.finditer(r'\+\+\s*(\w+)', code):
        ptrs.add(match.group(1))
    return {p: f"{p}_idx" for p in ptrs}


def main():
    os.makedirs(ABSTRACTED_DIR, exist_ok=True)
    for fname in os.listdir(RAW_LOOPS_DIR):
        if not fname.endswith('.json'):
            continue
        with open(os.path.join(RAW_LOOPS_DIR, fname)) as f:
            loop = json.load(f)

        ptr_vars = guess_pointer_vars(loop["original_code"])
        abstracted = abstract_code(loop["original_code"], ptr_vars)

        out = {
            "id": loop["id"],
            "ptr_vars": ptr_vars,
            "abstracted_code": abstracted
        }

        with open(os.path.join(ABSTRACTED_DIR, fname), 'w') as f:
            json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
