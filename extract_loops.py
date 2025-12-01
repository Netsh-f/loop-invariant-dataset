# extract_loops.py
import os
import json
import clang.cindex
from clang.cindex import CursorKind

import config


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

    # 检查是否来自同一文件（必要）
    if not start.file or not end.file or start.file.name != end.file.name:
        return ""

    lines = file_content.splitlines()
    num_lines = len(lines)

    # 保护：Clang 可能返回 line=0 表示无效位置
    if start.line <= 0 or end.line <= 0:
        return ""

    # 行号越界检查（Clang 行号从 1 开始）
    if start.line > num_lines or end.line > num_lines:
        return ""

    try:
        if start.line == end.line:
            line_str = lines[start.line - 1]
            # 列也是 1-based，且可能超出当前行长度
            start_col = max(0, min(start.column - 1, len(line_str)))
            end_col = max(start_col, min(end.column, len(line_str)))
            return line_str[start_col:end_col]
        else:
            # 第一行（从 start.column 到行尾）
            first_line = lines[start.line - 1]
            start_col = max(0, min(start.column - 1, len(first_line)))
            first = first_line[start_col:]

            # 中间行（完整行）
            middle_start = start.line
            middle_end = end.line - 1
            # 确保 middle 范围有效
            if middle_start < num_lines and middle_end >= middle_start:
                middle = lines[middle_start:middle_end]
            else:
                middle = []

            # 最后一行（从行首到 end.column）
            last_line = lines[end.line - 1]
            end_col = max(0, min(end.column, len(last_line)))
            last = last_line[:end_col]

            return "\n".join([first] + middle + [last])
    except Exception:
        # 任何异常都安全返回空字符串
        return ""


def extract_loops_from_file(filepath, project_prefix):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    index = clang.cindex.Index.create()
    tu = index.parse(filepath, args=config.CLANG_ARGS)
    if not tu:
        print(f"Parse failed: {filepath}")
        return []

    loops = []

    def walk(node, func_name=""):
        nonlocal loops
        if node.kind == CursorKind.FUNCTION_DECL:
            new_func_name = node.spelling or "anonymous"
            for child in node.get_children():
                walk(child, new_func_name)
        elif node.kind in [CursorKind.FOR_STMT, CursorKind.WHILE_STMT, CursorKind.DO_STMT]:
            code = get_source_code(node, content)
            if not code.strip():
                return
            # 生成带项目前缀的 ID
            clean_path = filepath.replace('./', '').replace('/', '_').replace('.', '_')
            loop_id = f"___{project_prefix}_{clean_path}_{node.location.line}"
            loops.append({
                "id": loop_id,
                "project": project_prefix,
                "file": filepath,
                "function": func_name,
                "line": node.location.line,
                "column": node.location.column,
                "original_code": code,
                "ast_kind": str(node.kind).split('.')[-1]
            })
        else:
            for child in node.get_children():
                walk(child, func_name)

    walk(tu.cursor)
    return loops


def process_project(repo_path, source_dirs, project_prefix):
    all_loops = []
    for root, _, files in os.walk(repo_path):
        rel = os.path.relpath(root, repo_path)
        # 跳过非源码目录
        if rel == ".":
            in_source = True
        else:
            in_source = any(rel.startswith(d) for d in source_dirs)
        if not in_source:
            continue
        for f in files:
            if f.endswith('.c'):
                filepath = os.path.join(root, f)
                try:
                    loops = extract_loops_from_file(filepath, project_prefix)
                    all_loops.extend(loops)
                    if loops:
                        print(f"[{project_prefix}] Extracted {len(loops)} loops from {filepath}")
                except Exception as e:
                    print(f"[{project_prefix}] Error processing {filepath}: {e}")
    return all_loops


def main():
    os.makedirs(config.RAW_LOOPS_DIR, exist_ok=True)

    all_loops = []

    # Process musl
    print("🔍 Processing musl...")
    musl_loops = process_project(
        repo_path=config.MUSL_REPO,
        source_dirs=config.MUSL_SOURCE_DIRS,
        project_prefix="musl"
    )
    all_loops.extend(musl_loops)

    # Process busybox
    print("🔍 Processing busybox...")
    busybox_loops = process_project(
        repo_path=config.BUSYBOX_REPO,
        source_dirs=config.BUSYBOX_SOURCE_DIRS,
        project_prefix="busybox"
    )
    all_loops.extend(busybox_loops)

    # Process coreutils
    print("🔍 Processing coreutils...")
    coreutils_loops = process_project(
        repo_path=config.COREUTILS_REPO,
        source_dirs=config.COREUTILS_SOURCE_DIRS,
        project_prefix="coreutils"
    )
    all_loops.extend(coreutils_loops)

    # Save all raw loops
    for loop in all_loops:
        out_path = os.path.join(config.RAW_LOOPS_DIR, loop["id"] + ".json")
        with open(out_path, 'w') as f:
            json.dump(loop, f, indent=2)

    print(f"\n✅ Total loops extracted: {len(all_loops)}")
    if len(all_loops) < 100:
        print("⚠️ Warning: Less than 100 loops extracted!")
    else:
        print("🎉 Met minimum requirement (≥100 loops)!")


if __name__ == "__main__":
    setup_clang()
    main()
