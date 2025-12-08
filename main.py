import json
import os
import clang
from clang.cindex import Index, CursorKind


def find_loops(node):
    loops = []
    if node.kind in (CursorKind.FOR_STMT, CursorKind.WHILE_STMT, CursorKind.DO_STMT):
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
                    return all_loops  # TODO 先只做一个文件
    return all_loops


def get_loop_context(loop: clang.cindex.Cursor, project_info: dict):
    return {
        "project_name": project_info["name"],
        "project_version": project_info["commit"],
        "kind": loop.kind.name,
        "file_path": loop.location.file.name,
        "line": loop.location.line,
        "column": loop.location.column,
        "source_code": get_source_code(loop),
    }


def get_loop_list_context(loop_list: list, project_info: dict):
    loop_list_context = []
    for loop in loop_list:
        loop_list_context.append(get_loop_context(loop, project_info))
    return loop_list_context


def is_simple_loop(loop: clang.cindex.Cursor) -> bool:
    def visit(node):
        # 禁用函数调用
        if node.kind == CursorKind.CALL_EXPR:
            return False
        # 禁止：结构体/联合体成员访问
        if node.kind in (CursorKind.MEMBER_REF, CursorKind.MEMBER_REF_EXPR):
            return False
        # 禁止：取地址 & 和复杂指针运算
        if node.kind == CursorKind.UNARY_OPERATOR:
            if node.spelling == "&":
                return False
        # 禁止：goto
        if node.kind == CursorKind.GOTO_STMT:
            return False
        # 禁止：嵌套循环
        if node != loop and node.kind in (
                CursorKind.FOR_STMT,
                CursorKind.WHILE_STMT,
                CursorKind.DO_STMT
        ):
            return False
        # 递归检查子节点
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
        loop_list = filter_loop_list(loop_list)
        loop_list_context = get_loop_list_context(loop_list, project)
        print(json.dumps(loop_list_context, indent=2))
