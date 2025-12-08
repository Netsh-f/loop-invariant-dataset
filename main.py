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
    }


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
        loops = precess_project(project["root_path"], project["clang_args"])

        print(f"Found {len(loops)} loop(s):")
        for i, loop in enumerate(loops):
            print(get_loop_context(loop, project))
