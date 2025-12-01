import os
import json
import clang.cindex
from clang.cindex import CursorKind

import config


# 设置 libclang（适配常见路径）
def setup_clang():
    paths = [
        "/usr/lib/llvm-14/lib/libclang.so",
        "/usr/lib/x86_64-linux-gnu/libclang-14.so",
        "/usr/lib/libclang.so"
    ]
    for p in paths:
        if os.path.exists(p):
            clang.cindex.Config.set_library_file(p)
            return
    raise RuntimeError("libclang not found")


def get_source_code(cursor, file_content):
    start = cursor.extent.start
    end = cursor.extent.end
    if not start.file or start.file.name != end.file.name:
        return ""
    lines = file_content.splitlines()
    if start.line == end.line:
        return lines[start.line - 1][start.column - 1:end.column]
    else:
        first = lines[start.line - 1][start.column - 1:]
        middle = lines[start.line:end.line - 1]
        last = lines[end.line - 1][:end.column] if end.line <= len(lines) else ""
        return "\n".join([first] + middle + [last])


def extract_loops_from_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    index = clang.cindex.Index.create()
    tu = index.parse(filepath, args=config.CLANG_ARGS)
    if not tu:
        print(f"Parse failed: {filepath}")
        return []

    loops = []

    def walk(node, func_cursor=None, func_name=""):
        nonlocal loops
        if node.kind in [CursorKind.FUNCTION_DECL]:
            func_cursor = node
            func_name = node.spelling
        if node.kind in [CursorKind.FOR_STMT, CursorKind.WHILE_STMT, CursorKind.DO_STMT]:
            code = get_source_code(node, content)
            if not code.strip():
                return
            loop_id = f"{filepath.replace('/', '_').replace('.', '_')}_{node.location.line}"
            loops.append({
                "id": loop_id,
                "file": filepath,
                "function": func_name,
                "line": node.location.line,
                "column": node.location.column,
                "original_code": code,
                "ast_kind": str(node.kind).split('.')[-1]
            })
        for child in node.get_children():
            walk(child, func_cursor, func_name)

    walk(tu.cursor)
    return loops


def main():
    os.makedirs(config.RAW_LOOPS_DIR, exist_ok=True)
    all_loops = []
    for root, _, files in os.walk(config.MUSL_REPO):
        rel = os.path.relpath(root, config.MUSL_REPO)
        if not any(rel.startswith(d) for d in config.SOURCE_DIRS):
            continue
        for f in files:
            if f.endswith('.c'):
                filepath = os.path.join(root, f)
                try:
                    loops = extract_loops_from_file(filepath)
                    all_loops.extend(loops)
                    print(f"Extracted {len(loops)} loops from {filepath}")
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

    # 保存原始循环
    for loop in all_loops:
        out_path = os.path.join(config.RAW_LOOPS_DIR, loop["id"] + ".json")
        with open(out_path, 'w') as f:
            json.dump(loop, f, indent=2)

    print(f"Total loops extracted: {len(all_loops)}")
    if len(all_loops) < 100:
        print("⚠️ Warning: Less than 100 loops extracted!")


if __name__ == "__main__":
    setup_clang()
    main()
