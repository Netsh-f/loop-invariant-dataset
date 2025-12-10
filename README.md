# 工业级循环不变式数据集构建工具链

## 目录说明

- extract_loops.py
- abstract_loop.py
- verify_invariant.py
- clean_data.py
- output/
  - dataset.json

## 使用步骤

### 1. 准备环境

```shell
apt install cbmc clang libclang-dev
pip install -r requirements.txt
```

### 2. 获取分析项目源码

本项目已通过 git submodule 管理 musl、busybox、coreutils 源码，请执行以下指令以获取源码：

```shell
git submodule update --init --recursive
```

musl 使用 v1.2.5 分支，busybox 使用 1_36_stable 分支。

### 3. 配置项目

* `config.py`:设置三个要分析项目的根目录`MUSL_REPO`, `BUSYBOX_REPO`, `COREUTILS_REPO`
* `extract_loops.py`中`setup_clang`函数检查`libclang.so`文件路径配置是否正确
> 查找运行环境中libclang.so文件位置
> ```shell
> find /usr -name "libclang.so*" 2>/dev/null
> ```

### 4. 执行脚本

```shell
python build_dataset.py
```