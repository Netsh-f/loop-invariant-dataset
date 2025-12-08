import os
import json
import clang.cindex
from clang.cindex import Index, CursorKind, TranslationUnit

clang.cindex.Config.set_library_file("/usr/lib/llvm-14/lib/libclang.so")

base_dir = "/home/aimall/workspace"
MUSL_REPO = os.path.join(base_dir, "musl")
BUSYBOX_REPO = os.path.join(base_dir, "busybox")
COREUTILS_REPO = os.path.join(base_dir, "coreutils")

REPOSITORIES = {
    "musl": MUSL_REPO,
    "busybox": BUSYBOX_REPO,
    "coreutils": COREUTILS_REPO,
}

OUTPUT_JSON_FILE = "extracted_loops_ast.json"


def mock_get_project_version(repo_path):
    # 模拟获取项目版本信息，与原脚本相同
    repo_name = os.path.basename(repo_path)
    if repo_name == 'musl':
        return "v1.2.4 (Mock Commit Hash: abcd1234)"
    elif repo_name == 'busybox':
        return "v1.36.1 (Mock Commit Hash: fghi5678)"
    elif repo_name == 'coreutils':
        return "v9.4 (Mock Commit Hash: jklm9012)"
    return "Unknown Version (Mock)"


def find_c_files(repo_path):
    # 递归查找 .c 和 .h 文件，与原脚本相同
    c_files = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            # 仅处理 .c 文件以减少复杂性，并避免重复处理头文件中的宏
            if file.endswith('.c'):
                c_files.append(os.path.join(root, file))
    return c_files


def get_source_code_fragment(lines, start_line, end_line):
    """根据行号范围（基于1）从文件中提取源代码片段。"""
    # 转换为基于0的索引
    start_idx = start_line - 1
    end_idx = end_line  # 结束行（含）的下一行

    # 确保索引在范围内
    if start_idx < 0 or end_idx > len(lines):
        return ""

    return "".join(lines[start_idx:end_idx]).strip()


def find_parent_function_name(cursor):
    """通过 AST 向上查找循环所在的函数名。"""
    current_cursor = cursor.semantic_parent
    while current_cursor:
        if current_cursor.kind == CursorKind.FUNCTION_DECL:
            return current_cursor.spelling
        current_cursor = current_cursor.semantic_parent
    return "Global/Unknown Scope"


def get_context_variables(cursor, lines):
    """
    通过 AST 查找循环前声明的局部变量。
    这里简化为获取父函数体中循环前所有变量声明的代码。
    """
    context_lines = []

    # 找到最近的函数声明 (FUNCTION_DECL)
    function_cursor = cursor.semantic_parent
    while function_cursor and function_cursor.kind != CursorKind.FUNCTION_DECL:
        function_cursor = function_cursor.semantic_parent

    if not function_cursor:
        return ""  # 找不到函数，可能是全局作用域或宏

    # 循环在函数中的起始行号
    loop_start_line = cursor.extent.start.line

    # 遍历函数体内的所有子节点
    for child in function_cursor.get_children():
        child_start_line = child.extent.start.line

        # 只关心在循环开始前声明的变量
        if child_start_line < loop_start_line:
            # 捕获变量声明 (VAR_DECL) 和其他语句，作为上下文
            if child.kind == CursorKind.VAR_DECL or child.kind == CursorKind.DECL_STMT:
                # 获取声明的源代码
                start = child.extent.start.line
                end = child.extent.end.line

                # 排除宏定义的行，只保留实际代码行
                code_fragment = get_source_code_fragment(lines, start, end)
                if code_fragment:
                    context_lines.append(code_fragment)
        else:
            # 已经超过循环的起始位置，停止扫描
            break

    # 简单地连接这些上下文代码行，并去重
    return "\n".join(sorted(list(set(context_lines)))).strip()


def extract_loops_recursive(cursor, file_path, lines, repo_name, version_info, all_extracted_loops):
    """递归遍历 AST 查找循环节点。"""

    try:
        # 1. 检查当前节点是否是循环
        if cursor.kind in [CursorKind.FOR_STMT, CursorKind.WHILE_STMT, CursorKind.DO_STMT]:

            # 排除系统头文件中的循环（如 stdio.h 中的宏）
            if not cursor.extent.start.file or cursor.extent.start.file.name != file_path:
                return

            start_line = cursor.extent.start.line
            end_line = cursor.extent.end.line

            # 确保循环体至少包含一行代码
            if start_line >= end_line:
                return

            original_loop_code = get_source_code_fragment(lines, start_line, end_line)
            function_name = find_parent_function_name(cursor)
            context_code = get_context_variables(cursor, lines)

            # 仅当代码和上下文不为空时才记录
            if original_loop_code and context_code:
                loop_data = {
                    "project": repo_name,
                    "version_info": version_info,
                    "file_path": file_path,
                    "function_name": function_name,
                    "loop_type": cursor.kind.name.replace("_STMT", "").lower(),
                    "line_start": start_line,
                    "line_end": end_line,
                    "context_code": context_code,
                    "original_loop_code": original_loop_code,
                    # 留出字段用于后续任务
                    "abstracted_loop_code": "",
                    "ground_truth_invariant": "",
                    "verification_log": "",
                    "sample_state": {},
                    "abstraction_notes": "",
                    "variable_set": [],
                    "guard_condition": "",
                    "update_list": [],
                    "atomic_predicates": [],
                }
                all_extracted_loops.append(loop_data)
                return  # 一旦找到一个循环，不必再检查其内部的子节点作为独立循环 (避免重复)
    except ValueError as e:
        # 捕获 ValueError: Unknown template argument kind 280 (或其他未知ID)
        # 打印警告信息，但继续遍历 AST 的其余部分
        print(f"警告: 忽略 AST 节点 ({cursor.location.file}:{cursor.extent.start.line})，原因: {e}")
        # 不返回，继续递归遍历子节点

    # 2. 递归遍历子节点
    for child in cursor.get_children():
        extract_loops_recursive(child, file_path, lines, repo_name, version_info, all_extracted_loops)


def process_file_ast(repo_name, file_path, version_info, all_extracted_loops):
    """使用 clang AST 处理单个 C 文件。"""

    # 尝试读取文件内容
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return

    # Clang 解析参数：-I. 用于查找头文件，-std=gnu11 用于兼容 C99/C11 扩展
    # 对于复杂的项目，可能需要提供特定的编译参数（如 -D宏定义，-I头文件路径）
    args = ['-I.', '-std=gnu11']

    index = Index.create()

    try:
        # 解析文件，生成 AST
        tu = index.parse(file_path, args=args)
    except Exception as e:
        print(f"警告: Clang 解析 {file_path} 失败: {e}")
        return

    # 递归遍历 AST 并提取循环
    extract_loops_recursive(tu.cursor, file_path, lines, repo_name, version_info, all_extracted_loops)


def main():
    """主执行函数。"""
    all_extracted_loops = []

    print("--- C 语言循环体 AST 抽取开始 ---")

    for repo_name, repo_path in REPOSITORIES.items():
        if not os.path.isdir(repo_path):
            print(f"警告: 仓库路径 {repo_path} 不存在或不是目录。跳过 {repo_name}。")
            continue

        print(f"\n正在处理项目: {repo_name} ({repo_path})")

        version_info = mock_get_project_version(repo_path)
        print(f"  版本信息: {version_info}")

        c_files = find_c_files(repo_path)
        print(f"  找到 {len(c_files)} 个 .c 文件。")

        # 迭代处理找到的C文件
        for i, file_path in enumerate(c_files):
            # 限制文件数量以避免运行时间过长，直到达到目标
            if len(all_extracted_loops) >= 150:
                print(f"!!! 已达到 {len(all_extracted_loops)} 条循环的抽取目标。停止扫描。")
                break

            print(f"    [{i + 1}/{len(c_files)}] 正在扫描 {os.path.basename(file_path)}...")
            process_file_ast(repo_name, file_path, version_info, all_extracted_loops)

    print(f"\n--- AST 抽取完成 ---")
    print(f"总共抽取到 {len(all_extracted_loops)} 条循环。")

    # 3. 保存为 JSON 文件
    try:
        with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_extracted_loops, f, indent=4, ensure_ascii=False)
        print(f"数据已成功保存到文件: {OUTPUT_JSON_FILE}")
    except Exception as e:
        print(f"保存 JSON 文件时出错: {e}")


if __name__ == "__main__":
    main()
