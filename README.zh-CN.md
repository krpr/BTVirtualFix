# BTVirtualFix

[English](README.md)

一个实验性 Lilu 插件，用于让**没有真实蓝牙硬件的 macOS 虚拟机**完成系统原生虚拟蓝牙控制器的初始化。

**0.1.1 已在一台符合下述配置的虚拟机上完成初始化，并停止已观察到的 `bluetoothd` 反复退出重启。** 它不提供蓝牙无线收发能力，不是 QEMU USB 蓝牙设备模拟器，也不是所有宿主机 CPU 尖峰的通用修复。

## 已验证配置

| 组件 | 已验证值 |
| --- | --- |
| 客体系统 | macOS 15.4.1，构建 `24E263`，x86_64 |
| 内核 | Darwin `24.4.0` |
| 引导 | OpenCore 1.0.8 |
| Lilu | 1.7.2 |
| 虚拟机检测过滤 | VMHide 1.1.3，仅为 `bluetoothd` 添加例外 |
| 机型 / board ID | MacPro7,1 / `Mac-27AD2F918AE68F61` |
| 虚拟化 | QEMU 10.2.1 / libvirt 12.0.0；4 vCPU、8 GiB 内存 |
| 蓝牙硬件 | 无 |

这张表记录实际验证的组合，不代表兼容范围。插件限制精确内核版本和原始代码页；构建过程还检查完整目标二进制。其他系统构建、架构、board ID 与依赖版本尚未验证。

## 修复内容

已验证的配置通过 `bt-transport-override=10` 选择 Apple 原生虚拟传输，并允许 `bluetoothd` 检测到虚拟机环境。插件随后对 `/usr/sbin/bluetoothd` 已通过验证的内存代码页做两处修改：

1. 跳过阻止虚拟控制器 LinkAgent 激活的一处内部诊断提前返回：**6 字节**。
2. 将 `APPLE_VIRTUAL`（chipset 6000）加入已有的“跳过实体芯片固件查询”分支：**1 字节**。

插件必须显式添加 `-btvirtfix` 才会启用。它先调用原代码页验证器，保留验证输出，再检查路径、偏移、完整原始页面与唯一签名。磁盘上的 Apple 文件不改动。两个页面独立处理，不保证两页修改具备原子性。

详见 [设计与精确目标](docs/design.md)。

## 构建

需要 macOS、完整 Xcode 和 Python 3。输入必须来自受支持客体的、未经修改的 universal `/usr/sbin/bluetoothd`。构建机可以使用其他 macOS 版本，但其自身的 daemon 通常不会匹配。

```sh
git clone https://github.com/krpr/BTVirtualFix.git
cd BTVirtualFix
python3 scripts/bootstrap.py
bash build.sh --bluetoothd /path/to/supported/bluetoothd
```

输出为 `build/Release/BTVirtualFix.kext` 及本地校验清单。本仓库不分发 Apple 二进制、完整 Apple 参考页或预编译 kext；参考页在本地通过校验后生成，并被 Git 忽略。

不提供 Apple 二进制也可运行守卫测试：

```sh
python3 scripts/test_guards.py --synthetic
```

Python 辅助工具测试可使用 `python3 -m unittest discover -s tests -p 'test_*.py' -v`。合成数据守卫测试验证页面保护逻辑和修改范围，不等于验证实际 macOS 二进制或证明能够启动。

已提供 [GitHub Actions 模板](ci/README.md)，尚未启用。上述检查已在本地通过，暂未验证 GitHub 托管运行。

## 安装与验证

编辑 EFI 前，请先阅读 [安装及完整回退说明](docs/installation.md)。[OpenCore 配置片段](examples/opencore-fragment.plist) 仅供合并参考，不能替换完整 `config.plist`。原试验安装器锁定了单台机器的配置，不适合作为其他机器的通用安装器。

可先执行只读检查：

```sh
python3 scripts/check_target.py
python3 scripts/check_target.py --oc-dir /Volumes/EFI/EFI/OC
```

不指定 `--oc-dir` 时不会检查 EFI。即使检查通过，也不能证明固件实际从该 EFI 启动，或保证下一次启动成功。

保持蓝牙和音频服务正常启用。验收需要确认 `Stack initialization complete`、服务进程持续稳定，以及原 HCI 失败/重启序列消失。显示 `APPLE_VIRTUAL` 不意味着具备无线配对或蓝牙音频能力。

## 实测结果

2026 年 11 月 18 日的验证中，蓝牙栈成功初始化，蓝牙、音频和 Hearing 服务保持相同进程近 20 分钟。严格六分钟窗口内，HCI 初始化失败、HCI 超时、reason-108 重启，以及相关音频/Hearing 蓝牙 XPC 中断均为零。

宿主机仍有其他短时尖峰。六分钟窗口里，该 VM 平均占 **16 线程宿主机总 CPU 的 3.375%**，0.25 秒分辨率峰值为 **21.502%**。停止客体采样后的另一个 45 秒窗口，平均为 **1.232%**。这些是不同观察窗口，不是受控的修复前后对比；整机最高尖峰主要来自另外两台 VM。

[脱敏验证记录](docs/validation.md) 包含测量口径、采样开销和局限，不能据此宣称普遍降低了某个百分比的 CPU 消耗。

## 维护

升级 macOS 或调整已验证配置前，需要重新检查和验证。本版本不会自动适配新二进制。`-btvirtfixoff` 只停用插件，不撤销原生虚拟传输参数或 VMHide 例外；恢复原配置请执行完整回退。

提交改进时应说明精确系统构建、二进制哈希、初始化行为和回归测试。不要提交序列号、个人 EFI 配置、凭据或未脱敏日志。

[版本记录](CHANGELOG.md) · [许可证](LICENSE) · [第三方声明](NOTICE.md)
