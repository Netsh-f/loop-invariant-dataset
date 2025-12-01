# abstract_loop.py
import os
import json
import re
from config import RAW_LOOPS_DIR, ABSTRACTED_DIR


def is_simple_pointer_loop(code):
    # 现有检查逻辑保持不变...

    # 新增: 检查并拒绝包含指针递减的循环
    if re.search(r'\b\w+\s*--|--\s*\w+|\+\s*-\d+|-\s*\d+\s*\+', code):
        return False

    # 同样拒绝 p += -1, p -= 1 这种模式
    if re.search(r'\b\w+\s*[+-]=\s*-?\d+', code):
        # 允许 p += 1, p -= 1? 保守处理: 只允许 ++ 和 += 正数
        lines = code.split(';')
        for line in lines:
            # 如果是 += 操作，检查右侧是否为正数常量或变量
            if re.search(r'\b(\w+)\s*\+=', line):
                if not re.search(r'\+=\s*[1-9]\d*', line):  # 仅允许 += 后跟正数
                    return False
            # 直接拒绝 -- 模式
            if re.search(r'\b(\w+)\s*--|--\s*\b\w+', line):
                return False

    # 如果以上所有条件都未被触发，则返回 True 表示该循环通过了简单指针循环的检查
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
