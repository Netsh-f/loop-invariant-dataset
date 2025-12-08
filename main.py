import json
import os
import re

import clang
from clang.cindex import Index, CursorKind


def find_loops(node):
    loops = []
    # 暂时排除掉 do-while: CursorKind.DO_STMT，往往是一些宏展开
    if node.kind in (CursorKind.FOR_STMT, CursorKind.WHILE_STMT):
        loops.append(node)
    for child in node.get_children():
        loops.extend(find_loops(child))
    return loops


def extract_loops_from_file(filepath: str, clang_args: list):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    index = Index.create()
    tu = index.parse(filepath, args=clang_args)

    loops = find_loops(tu.cursor)
    return loops


def precess_project(root_path: str, clang_args: list):
    all_loops = []
    files_count = 0
    for dir_path, dir_names, filenames in os.walk(root_path):
        for file in filenames:
            if file.endswith('.c'):
                files_count += 1
                filepath = os.path.join(dir_path, file)
                loops = extract_loops_from_file(filepath, clang_args)
                if loops:
                    all_loops.extend(loops)
                    print(f"[{files_count}] {filepath} → {len(loops)} loops")
                    # return all_loops  # TODO 先只做一个文件
    return all_loops


def get_loop_context(loop: clang.cindex.Cursor, project_info: dict):
    source_code = get_source_code(loop)
    abstract_code, ptr_map = abstract_loop_code(source_code, loop)
    return {
        "project_name": project_info["name"],
        "project_version": project_info["commit"],
        "kind": loop.kind.name,
        "file_path": loop.location.file.name,
        "line": loop.location.line,
        "column": loop.location.column,
        "source_code": source_code,
        "abstract_code": abstract_code,
        "ptr_map": ptr_map,
    }


def get_loop_list_context(loop_list: list, project_info: dict):
    loop_list_context = []
    for loop in loop_list:
        loop_list_context.append(get_loop_context(loop, project_info))
    return loop_list_context


def is_simple_loop(loop: clang.cindex.Cursor) -> bool:
    """
    判断是否为“简单循环”：仅含基本控制流、数组下标、简单算术。
    排除：函数调用、结构体成员访问、取地址、goto、嵌套循环等。
    """
    source_code = get_source_code(loop)
    if '->' in source_code:
        return False

    def visit(node):
        # 禁止函数调用
        if node.kind == CursorKind.CALL_EXPR:
            return False

        # 禁止结构体/联合体成员访问（包括 a.b 和 a->b）
        if node.kind == CursorKind.MEMBER_REF_EXPR:
            return False

        # 禁止取地址操作 &
        if node.kind == CursorKind.UNARY_OPERATOR:
            # 检查操作符是否为 &
            # 注意：node.spelling 对 UNARY_OPERATOR 可能为空，需通过 displayname 或 token
            # 更可靠方式：检查 tokens
            try:
                tokens = list(node.get_tokens())
                if tokens and tokens[0].spelling == '&':
                    return False
            except Exception:
                pass  # 容错

        # 禁止 goto
        if node.kind == CursorKind.GOTO_STMT:
            return False

        # 禁止嵌套循环（排除自身）
        if node != loop and node.kind in (
                CursorKind.FOR_STMT,
                CursorKind.WHILE_STMT,
                CursorKind.DO_STMT
        ):
            return False

        # 递归检查所有子节点：只要有一个子树非法，整个就非法
        for child in node.get_children():
            if not visit(child):
                return False

        return True

    return visit(loop)


def filter_loop_list(loop_list: list):
    filtered_loop_list = []
    for loop in loop_list:
        if is_simple_loop(loop):
            filtered_loop_list.append(loop)
    return filtered_loop_list


def get_source_code(cursor: clang.cindex.Cursor):
    start = cursor.extent.start
    end = cursor.extent.end
    filepath = start.file.name
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines(keepends=True)
    start_line_idx = start.line - 1
    end_line_idx = end.line - 1
    if start_line_idx == end_line_idx:
        line = lines[start_line_idx]
        return line[start.column - 1: end.column]
    else:
        snippet = [lines[start_line_idx][start.column - 1:]]
        for i in range(start_line_idx + 1, end_line_idx):
            snippet.append(lines[i])
        snippet.append(lines[end_line_idx][:end.column])
        return ''.join(snippet)


def abstract_loop_code(code: str, cursor: clang.cindex.Cursor) -> tuple[str | None, dict]:
    """
    输入: 原始循环代码字符串 + Clang Cursor
    输出: (抽象后代码, 指针映射 {"p": "p_idx"})
    """
    ptr_vars = set()
    keywords = {'if', 'else', 'for', 'while', 'do', 'return', 'break', 'continue',
                'switch', 'case', 'default', 'goto', 'sizeof', 'typedef', 'struct',
                'union', 'enum', 'const', 'volatile', 'static', 'extern'}

    def get_underlying_decl_ref(expr_cursor):
        """递归穿透 UNEXPOSED_EXPR 等，找到最底层的 DECL_REF_EXPR"""
        if expr_cursor.kind == CursorKind.DECL_REF_EXPR:
            return expr_cursor
        # 常见包装节点
        if expr_cursor.kind == CursorKind.UNEXPOSED_EXPR:
            for child in expr_cursor.get_children():
                result = get_underlying_decl_ref(child)
                if result:
                    return result
        return None

    # === Step 1: 识别指针变量===
    def collect_ptrs(node):
        if node.kind == CursorKind.ARRAY_SUBSCRIPT_EXPR:
            children = list(node.get_children())
            if len(children) >= 1:
                base_expr = children[0]
                decl_ref = get_underlying_decl_ref(base_expr)
                if decl_ref:
                    var = decl_ref.spelling
                    if var and var not in keywords and re.match(r'^[a-zA-Z_]', var):
                        ptr_vars.add(var)

        # 处理 *p
        if node.kind == CursorKind.UNARY_OPERATOR and node.spelling == "*":
            for child in node.get_children():
                decl_ref = get_underlying_decl_ref(child)
                if decl_ref:
                    var = decl_ref.spelling
                    if var not in keywords:
                        ptr_vars.add(var)

        # 递归
        for child in node.get_children():
            collect_ptrs(child)

    collect_ptrs(cursor)
    if not ptr_vars:
        return None, {}

    # === Step 2: 字符串替换（按名字长度降序，避免部分匹配）===
    for p in sorted(ptr_vars, key=len, reverse=True):
        p_esc = re.escape(p)

        # *p++ → arr_p[p_idx++]
        code = re.sub(rf'\*\s*{p_esc}\s*\+\+', f'arr_{p}[{p}_idx++]', code)
        # *++p → arr_p[++p_idx]
        code = re.sub(rf'\*\s*\+\+\s*{p_esc}\b', f'arr_{p}[++{p}_idx]', code)
        # *p-- → arr_p[p_idx--]
        code = re.sub(rf'\*\s*{p_esc}\s*--', f'arr_{p}[{p}_idx--]', code)
        # *--p → arr_p[--p_idx]
        code = re.sub(rf'\*\s*--\s*{p_esc}\b', f'arr_{p}[--{p}_idx]', code)
        # *p → arr_p[p_idx]
        code = re.sub(rf'\*\s*{p_esc}\b', f'arr_{p}[{p}_idx]', code)

        # p[i] → arr_p[i]
        code = re.sub(rf'\b{p_esc}\s*(\[[^\]]*\])', rf'arr_{p}\1', code)

        # p++ → p_idx++
        code = re.sub(rf'\b{p_esc}\s*\+\+', f'{p}_idx++', code)
        code = re.sub(rf'\+\+\s*{p_esc}\b', f'++{p}_idx', code)
        code = re.sub(rf'\b{p_esc}\s*--', f'{p}_idx--', code)
        code = re.sub(rf'--\s*{p_esc}\b', f'--{p}_idx', code)

    # === Step 3: 检查是否还有裸指针未替换 ===
    for p in ptr_vars:
        p_esc = re.escape(p)
        # 如果存在独立的 p（非 [ * ++ -- -> .）
        if re.search(rf'\b{p_esc}\b(?!\s*[\[\*\+\-\>])', code):
            return None, {}  # 抽象不完整，放弃

    return code, {p: f"{p}_idx" for p in ptr_vars}


def remove_not_abstract_loop(loop_list_context: list) -> list:
    return [loop for loop in loop_list_context if loop.get("abstract_code") is not None]


if __name__ == "__main__":
    project_list = [
        {
            "name": "musl",
            "commit": "0784374d561435f7c787a555aeab8ede699ed298",
            "root_path": "../musl",
            "clang_args": ['-I./musl/include'],
        }
    ]

    for project in project_list:
        loop_list = precess_project(project["root_path"], project["clang_args"])
        print(f"===before filter len = {len(loop_list)}===")
        loop_list = filter_loop_list(loop_list)
        loop_list_context = get_loop_list_context(loop_list, project)
        loop_list_context = remove_not_abstract_loop(loop_list_context)
        print(f"===after filter len = {len(loop_list_context)}===")

        os.makedirs("output", exist_ok=True)
        with open("output/loop_dataset.json", "w", encoding="utf-8") as f:
            json.dump(loop_list_context, f, indent=2, ensure_ascii=False)
