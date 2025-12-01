# config.py
import os

MUSL_REPO = "../musl"
BUSYBOX_REPO = "../busybox"
OUTPUT_DIR = "output"
RAW_LOOPS_DIR = os.path.join(OUTPUT_DIR, "raw_loops")
ABSTRACTED_DIR = os.path.join(OUTPUT_DIR, "abstracted")
VERIFIED_DIR = os.path.join(OUTPUT_DIR, "verified")

# 源码子目录（根据项目结构调整）
MUSL_SOURCE_DIRS = ["src"]
BUSYBOX_SOURCE_DIRS = ["libbb", "coreutils", "networking", "arch", "console-tools", "e2fsprogs", "editors", "findutils",
                       "loginutils", "mail", "miscutils", "modutils", "procps", "runit", "selinux", "shell", "sysklogd",
                       "util-linux"]

CLANG_ARGS = ['-I./musl/include', '-I./busybox/include', '-D__MUSL__', '-D_GNU_SOURCE']

RAW_LOOPS_DIR = "output/raw_loops"
