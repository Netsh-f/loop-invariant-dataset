import os

# 固定 musl 版本（确保可复现）
MUSL_REPO = "../musl"
MUSL_VERSION = "v1.2.5"  # musl 官方 release tag

# 搜索的源码子目录（避免测试/文档）
SOURCE_DIRS = [
    "src/string",
    "src/stdio",
    "src/stdlib",
    "src/time",
    "src/multibyte",
]

# 输出路径
OUTPUT_DIR = "output"
RAW_LOOPS_DIR = os.path.join(OUTPUT_DIR, "raw_loops")
ABSTRACTED_DIR = os.path.join(OUTPUT_DIR, "abstracted")
VERIFIED_DIR = os.path.join(OUTPUT_DIR, "verified")

# CBMC 配置
CBMC_UNWIND = 20
CBMC_TIMEOUT = 30  # seconds per loop

# Clang 配置
CLANG_ARGS = ["-I./musl/include", "-D_XOPEN_SOURCE=700"]