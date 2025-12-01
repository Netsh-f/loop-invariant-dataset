# abstract_loop.py
import os
import json
import re
from config import RAW_LOOPS_DIR, ABSTRACTED_DIR


def is_simple_pointer_loop(code):
    """只处理安全的指针遍历模式"""
    if not re.search(r'\*\s*\w', code):
        return False
    # 允许 *p++, *++p, p++, ++p
    if not re.search(r'\b\w+\s*\+\+|\+\+\s*\w+', code):
        return False
    # 不含函数调用（除控制关键字外）
    if re.search(r'\b(?!if|while|for|assert|return)\w+\s*\(', code):
        return False
    return True


def generate_abstract_c(loop_id, original_code):
    """
    仅返回抽象后的循环体（不含变量声明）。
    示例输入: for (h++; *h && hw != nw; hw = hw<<8 | *++h);
    输出:      for (h_idx++; arr_h[h_idx] && hw != nw; hw = hw<<8 | arr_h[++h_idx]);
    """
    ptr_vars = set()
    for match in re.finditer(r'\*\s*(\w+)', original_code):
        ptr_vars.add(match.group(1))
    for match in re.finditer(r'(\w+)\s*\+\+', original_code):
        ptr_vars.add(match.group(1))
    for match in re.finditer(r'\+\+\s*(\w+)', original_code):
        ptr_vars.add(match.group(1))

    if not ptr_vars:
        return None, {}

    code = original_code

    # Step 1: 处理复合解引用（顺序很重要！）
    for p in ptr_vars:
        # *p++ → arr_p[p_idx++]
        code = re.sub(rf'\*\s*{p}\s*\+\+', f"arr_{p}[{p}_idx++]", code)
        # *++p → arr_p[++p_idx]
        code = re.sub(rf'\*\s*\+\+\s*{p}\b', f"arr_{p}[++{p}_idx]", code)

    # Step 2: 处理普通 *p
    for p in ptr_vars:
        code = re.sub(rf'\*\s*{p}\b', f"arr_{p}[{p}_idx]", code)

    # Step 3: 处理独立递增/递减
    for p in ptr_vars:
        code = re.sub(rf'\b{p}\s*\+\+', f"{p}_idx++", code)
        code = re.sub(rf'\+\+\s*{p}\b', f"{p}_idx++", code)
        code = re.sub(rf'\b{p}\s*--', f"{p}_idx--", code)
        code = re.sub(rf'--\s*{p}\b', f"{p}_idx--", code)

    # Step 4: 检查是否还有裸指针（如单独的 'h'）
    for p in ptr_vars:
        if re.search(rf'\b{p}\b(?!\s*[\[\*\+\-\>])', code):
            return None, {}

    # ✅ 只返回循环体！
    return code, {p: f"{p}_idx" for p in ptr_vars}


def main():
    os.makedirs(ABSTRACTED_DIR, exist_ok=True)
    for fname in os.listdir(RAW_LOOPS_DIR):
        if not fname.endswith('.json'):
            continue
        with open(os.path.join(RAW_LOOPS_DIR, fname)) as f:
            loop = json.load(f)

        code = loop["original_code"]
        if not is_simple_pointer_loop(code):
            abstracted = ""
            ptr_vars = {}
        else:
            abstracted, ptr_vars = generate_abstract_c(loop["id"], code)
            if abstracted is None:
                abstracted = ""

        out = {
            "id": loop["id"],
            "ptr_vars": ptr_vars,
            "abstracted_code": abstracted
        }

        with open(os.path.join(ABSTRACTED_DIR, fname), 'w') as f:
            json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
