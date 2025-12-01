# 工业级循环不变式数据集构建工具链（musl）

## 环境准备

```shell
apt install cbmc clang libclang-dev
pip install -r requirements.txt
```

## 使用步骤

## musl源码获取

本项目使用musl v1.2.5版本，仓库中不包含该源码，请自行获取，方法如下

```shell
git clone git://git.musl-libc.org/musl
cd musl
git checkout v1.2.5
```

## busybox源码获取

```shell
git clone https://github.com/mirror/busybox.git
cd busybox
git checkout 1_36_stable
```

## coreutils源码获取

```shell
git clone https://git.savannah.gnu.org/git/coreutils.git
```

## 查找运行环境中libclang.so文件位置

```shell
find /usr -name "libclang.so*" 2>/dev/null
```