# abstract_loop.py
import os
import json
import re
from config import RAW_LOOPS_DIR, ABSTRACTED_DIR


def is_simple_pointer_loop(code):
    """启发式判断是否为简单指针遍历循环（适合抽象）"""
    # 必须包含 *p 和 p++ / ++p
    if not re.search(r'\*\s*\w', code):
        return False
    if not re.search(r'\b\w+\s*\+\+|\+\+\s*\w+', code):
        return False
    # 不含复杂操作（函数调用、赋值给指针等）
    if re.search(r'=\s*\w+\s*[+\-*/]', code):  # 如 h = h + 1
        return False
    if '(' in code and not any(kw in code for kw in ['if', 'while', 'for', 'assert']):
        # 可能有函数调用（strstr, memcmp 等）
        if re.search(r'\b\w+\s*\(', code):
            return False
    return True


def generate_abstract_c(loop_id, original_code):
    """
    为简单指针循环生成合法的抽象 C 代码。
    示例输入: while (*h && *h == *n) { h++; n++; }
    输出:
        int h_idx = 0, n_idx = 0;
        unsigned char arr_h[100] = {0}, arr_n[100] = {0};
        __CPROVER_assume(arr_h[0] != 0);
        while (arr_h[h_idx] && arr_h[h_idx] == arr_n[n_idx]) {
            h_idx++;
            n_idx++;
        }
    """
    # 提取所有可能是指针的变量（出现在 *p, p++, ++p 中）
    ptr_vars = set()
    for match in re.finditer(r'\*\s*(\w+)', original_code):
        ptr_vars.add(match.group(1))
    for match in re.finditer(r'(\w+)\s*\+\+', original_code):
        ptr_vars.add(match.group(1))
    for match in re.finditer(r'\+\+\s*(\w+)', original_code):
        ptr_vars.add(match.group(1))

    if not ptr_vars:
        return None, {}

    # 拷贝原始代码用于替换
    code = original_code

    # ✅ 关键修复：按优先级顺序替换，避免生成 *整数
    # Step 1: 先处理复合形式 *p++ 和 *++p
    for p in ptr_vars:
        # *p++  →  arr_p[p_idx++]
        code = re.sub(rf'\*\s*{p}\s*\+\+', f"arr_{p}[{p}_idx++]", code)
        # *++p  →  arr_p[++p_idx]
        code = re.sub(rf'\*\s*\+\+\s*{p}\b', f"arr_{p}[++{p}_idx]", code)

    # Step 2: 处理普通解引用 *p
    for p in ptr_vars:
        code = re.sub(rf'\*\s*{p}\b', f"arr_{p}[{p}_idx]", code)

    # Step 3: 处理剩余的独立递增/递减（如语句中的 h++;）
    for p in ptr_vars:
        code = re.sub(rf'\b{p}\s*\+\+', f"{p}_idx++", code)
        code = re.sub(rf'\+\+\s*{p}\b', f"{p}_idx++", code)
        code = re.sub(rf'\b{p}\s*--', f"{p}_idx--", code)
        code = re.sub(rf'--\s*{p}\b', f"{p}_idx--", code)

    # Step 4: 检查是否还有裸指针残留（如单独出现的 'h'）
    # 如果有，则说明抽象不完整，放弃该循环
    for p in ptr_vars:
        # 匹配单词边界内的 p，且后面不是 [、*、+、- 等（即不是 arr_p[p_idx] 或 *p）
        if re.search(rf'\b{p}\b(?!\s*[\[\*\+\-\>])', code):
            return None, {}

    # 构建变量声明
    idx_decls = ", ".join([f"{p}_idx = 0" for p in ptr_vars])
    arr_decls = ", ".join([f"arr_{p}[100] = {{0}}" for p in ptr_vars])

    # 生成最终 C 代码片段（注意：这只是循环体，不含函数包装）
    c_code = f"""int {idx_decls};
unsigned char {arr_decls};
__CPROVER_assume(arr_h[0] != 0); // example assumption
{code}"""

    return c_code, {p: f"{p}_idx" for p in ptr_vars}


def main():
    os.makedirs(ABSTRACTED_DIR, exist_ok=True)
    for fname in os.listdir(RAW_LOOPS_DIR):
        if not fname.endswith('.json'):
            continue
        with open(os.path.join(RAW_LOOPS_DIR, fname)) as f:
            loop = json.load(f)

        code = loop["original_code"]
        if not is_simple_pointer_loop(code):
            # 跳过复杂循环
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
