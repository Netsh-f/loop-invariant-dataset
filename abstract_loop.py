# abstract_loop.py
import os
import json
import re
from config import RAW_LOOPS_DIR, ABSTRACTED_DIR


def is_simple_pointer_loop(code):
    # 拒绝明显复杂的结构
    if re.search(r'\b(?!if|while|for|assert|return|else)\w+\s*\(', code):
        return False  # 有函数调用（除控制关键字）
    if '->' in code or '.' in code:
        return False  # 结构体访问
    if re.search(r'\b(errno|stdout|stderr|stdin)\s*=', code, re.IGNORECASE):
        return False  # 全局变量赋值

    # 允许以下任一模式：
    #   - 指针递增: p++, ++p, p += 1
    #   - 数组索引: arr[i], i++
    has_ptr_inc = re.search(r'\b\w+\s*\+\+|\+\+\s*\w+|\b\w+\s*\+=\s*1', code)
    has_array_access = re.search(r'\w+\s*\[\s*\w+\s*\]', code)

    return bool(has_ptr_inc or has_array_access)


def generate_abstract_c(loop_id, original_code):
    """
    仅返回抽象后的循环体（不含变量声明）。
    示例输入: for (h++; *h && hw != nw; hw = hw<<8 | *++h);
    输出:      for (h_idx++; arr_h[h_idx] && hw != nw; hw = hw<<8 | arr_h[++h_idx]);
    """
    ptr_vars = set()
    keywords = {'if', 'else', 'for', 'while', 'do', 'return', 'break', 'continue',
                'switch', 'case', 'default', 'goto', 'sizeof', 'typedef', 'struct',
                'union', 'enum', 'const', 'volatile', 'static', 'extern', 'auto', 'register'}

    # Step 0: 精确识别指针/数组变量
    # (1) 解引用 *p —— 但排除乘法 y * x
    # 使用负向后瞻 (?<!\w) 确保 * 前不是字母/数字/下划线
    for match in re.finditer(r'(?<!\w)\*\s*(\w+)', original_code):
        var = match.group(1)
        if var not in keywords:
            ptr_vars.add(var)

    # (2) 数组名: arr[expr]
    for match in re.finditer(r'\b([a-zA-Z_]\w*)\s*(?=\[)', original_code):
        var = match.group(1)
        if var not in keywords:
            ptr_vars.add(var)

    # ❌ 移除：不再根据 p++, --p 判断指针！(n, i, count 等标量会误入)

    if not ptr_vars:
        return None, {}

    code = original_code

    # Step 1: 处理复合解引用（*p++ 和 *++p）
    for p in sorted(ptr_vars, key=len, reverse=True):  # 长名字优先，避免部分匹配
        p_esc = re.escape(p)
        code = re.sub(rf'\*\s*{p_esc}\s*\+\+', f"arr_{p}[{p}_idx++]", code)
        code = re.sub(rf'\*\s*\+\+\s*{p_esc}\b', f"arr_{p}[++{p}_idx]", code)

    # Step 2: 处理普通解引用 *p
    for p in sorted(ptr_vars, key=len, reverse=True):
        p_esc = re.escape(p)
        code = re.sub(rf'\*\s*{p_esc}\b', f"arr_{p}[{p}_idx]", code)

    # Step 3: 处理数组访问 days[expr] → arr_days[expr]
    for p in sorted(ptr_vars, key=len, reverse=True):
        p_esc = re.escape(p)
        # 替换 arr[expr] 为 arr_arr[expr]，但避免重复替换 arr_arr[...]
        code = re.sub(rf'\b{p_esc}\s*(\[[^\]]*\])', rf'arr_{p}\1', code)

    # Step 4: 处理独立递增/递减（仅对真正指针变量）
    for p in sorted(ptr_vars, key=len, reverse=True):
        p_esc = re.escape(p)
        code = re.sub(rf'\b{p_esc}\s*\+\+', f"{p}_idx++", code)
        code = re.sub(rf'\+\+\s*{p_esc}\b', f"{p}_idx++", code)
        code = re.sub(rf'\b{p_esc}\s*--', f"{p}_idx--", code)
        code = re.sub(rf'--\s*{p_esc}\b', f"{p}_idx--", code)

    # Step 5: 检查是否还有裸指针或裸数组名（未被抽象）
    for p in ptr_vars:
        p_esc = re.escape(p)
        # 如果存在单独的 'p'（后面不是 [, *, ++, --, ->），说明抽象不完整
        if re.search(rf'\b{p_esc}\b(?!\s*[\[\*\+\-\>])', code):
            return None, {}

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