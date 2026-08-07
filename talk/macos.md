# VimgFind → macOS 仅适用改造评估（v4，含 macOS 26 兼容性专项）

> 定位：完整改造成**仅适用于 macOS** 的程序，新开分支（如 `macos-support`）独立开发。
> 原则：不做多系统适配层、不做抽象层、不做任何"最小重构"——保留代码原有结构与写法，只把 Windows 专属实现逐一替换为 macOS 等价实现。
> 测试手段：① Windows 本地（仅限不依赖 macOS API 的模块）；② GitHub Actions macOS runner（自动化）；③ **租借 macOS 26.6 真机（人工 UI 验证）**。
> 目标系统：**macOS 26（Tahoe）**。macOS 向前兼容性差，故以最新系统为唯一目标环境，并落实三条核心规范：**不碰私有 API / 跟进废弃 API / 尽早适配新权限模型**。

---

## 0. 可测试性分级定义

| 分级 | 含义 | 说明 |
|---|---|---|
| **A 本地** | 改造完成后，模块在 Windows 本地可直接 import / pytest | 仅限不含 macOS 专属 API 的模块（见 §4） |
| **B CI** | 依赖 macOS 环境，但可脚本断言 | GitHub Actions `macos-13/14/15`，无真人，全自动 |
| **C 人工** | 视觉质量、真实交互、新系统兼容性 | 租借 macOS 26.6 一次性集中验证 |

---

## 1. 依赖核查结论（实测，macOS-only 单一选型）

| 依赖 | 现版本 | macOS 选型 | 依据 / 备注 |
|---|---|---|---|
| **hnswlib** | 0.8.0 | **conda-forge 安装**（osx-arm64/osx-64 预编译，py39–py314 齐全） | PyPI 仅 sdist 无 wheel；不走源码编译 |
| pywin32 | 311 | **删除**，替换为 `pyobjc-framework-Cocoa`、`pyobjc-framework-Quartz`（12.2.1，**2026-06 发布，活跃维护，对应最新 SDK**） | 剪贴板（NSPasteboard）、空闲检测（Quartz） |
| onnxruntime | 1.23.2 | 不变 | wheel 为 `macosx_13_0_*` → **系统要求 macOS 13+**（26 满足） |
| numpy | 2.3.5 | 不变 | 双架构 wheel 齐全 ✓ |
| tkinterdnd2 | 0.4.3 | 不变（含 osx-arm64 的 libtkdnd2.9.3.dylib） | **tkdnd 2.9.3 为 2020 年旧第三方，是新系统兼容性最高风险项**（见 §2.3） |
| send2trash / ttkbootstrap / pathspec / tqdm / Pillow | — | 不变 | 纯 Python |
| Python | 3.12 | python.org 官方 3.12 最新补丁（自带 Tk 8.6） | 不用 Homebrew python 的 Tk（macOS 26 上需单独 brew python-tk）；conda-forge hnswlib 支持 3.12 ✓ |

---

## 2. macOS 26（Tahoe）兼容性专项 —— 三条核心规范落地

> 背景：macOS 2025 年从 15 直接改版为 26（Tahoe），已是当前最新系统；租机测 macOS 26.6 即最新点版本。向后兼容性差 = **旧二进制/旧依赖随时可能在新系统上出问题**，因此要对照下列规范逐条核查。

### 2.1 规范一：不碰私有 API（替换方案全部为公共 API）

改造引入的所有 macOS API 均为**公开、稳定、有文档**的 API，逐一列明备查：

| 用途 | 选用 API | 公共性 | 明确不用的方案 |
|---|---|---|---|
| 剪贴板复制文件/读图 | `NSPasteboard`（AppKit） | ✅ 公开 | 不用 Carbon Pasteboard 旧接口 |
| 空闲检测 | `CGEventSourceSecondsSinceLastEventType`（Quartz） | ✅ 公开 | 不用 `IOHIDSystem` 的 `ioreg` hack、不用私有 `_CG*` 前缀 |
| 打开/定位文件 | `open` / `open -R` 命令（或 `NSWorkspace`） | ✅ 公开 CLI | 不用 Finder 私有 AppleScript 变体 |
| 删除到废纸篓 | send2trash（底层 `osascript`/Finder 公开自动化） | ✅ 公开 | 不用 `fsevents`/内核钩子 |
| 应用内快捷键 | Tk 事件系统（无全局监听） | ✅ | 不用 Accessibility API / `CGEventTap` 做全局热键（会触发 TCC 输入监控权限，规避） |

### 2.2 规范二：废弃 API 年度跟进清单

本项目自研代码不直接调用 Apple 废弃 API（无 Carbon/QuickDraw/10.x 旧框架），风险集中在**第三方依赖的版本落后**。每年（或每次 macOS 大版本升级后）跟进：

| 关注项 | 当前状态 | 风险 | 跟进动作 |
|---|---|---|---|
| **Tcl/Tk（python.org 捆绑）** | Tk 8.6.x | 中：历史上 macOS 大版本升级曾致 Tk 渲染/全屏异常 | 租机验证渲染；升级 Python 补丁版（捆绑新 Tk） |
| **tkinterdnd2 / tkdnd 2.9.3** | 2020 年版本 | 🔴 高：最旧的第三方，拖拽是核心功能 | 租机专项验证拖拽；若异常，跟进 tkinterdnd2 新版或自行编译 tkdnd 2.9.x 源码 |
| **pyobjc** | 12.2.1（2026-06） | 低：活跃维护 | 保持 pip 最新 |
| **onnxruntime / numpy** | 1.23.2 / 2.3.5 | 低 | 随年度 wheel 升级 |
| **hnswlib（conda-forge）** | 0.8.0 | 低 | 随 conda-forge 构建升级 |
| **send2trash** | 2.1.0 | 低 | 观察 `osascript` 在新系统行为 |

### 2.3 规范三：权限模型（TCC）与公证 —— 尽早适配

**本应用无需任何敏感 TCC 权限**（无摄像头/麦克风/定位/屏幕录制/辅助功能/输入监控），这是设计上的天然优势。但仍需处理以下权限模型变化：

| 场景 | macOS 行为 | 对本项目影响 |
|---|---|---|
| 索引用户"桌面/文稿/下载"目录 | macOS 10.15+ 起 TCC"文件与文件夹"弹窗（非沙盒应用亦会触发） | 预期行为：首次索引会弹窗一次，用户允许即可；**租机清单验证一次** |
| 本地网络访问（macOS 15+） | 访问局域网需 `NSLocalNetworkUsageDescription` | 本项目仅出站 HTTPS（GitHub/模型下载），**不涉及**；若未来模型走局域网则需补 |
| 屏幕录制 | 截图类工具触发 | 仅 CI 的 `screencapture` 冒烟涉及（TCC 可能拦截 → 截图仅 best-effort）；**应用本身不需要** |
| 输入监控 | 全局键盘钩子触发 | 本项目快捷键为应用内 Tk 事件，**不涉及**（也不应改用 CGEventTap） |
| **签名/公证（macOS 26 强制）** | Apple 宣布 macOS 26 起**所有软件（含未签名）都必须通过公证检查** | 🔴 影响打包策略：未签名/adhoc 构建在 26 上会触发 Gatekeeper 拦截/警告 → 分发必须 Developer ID 签名 + notarization；**租机测试需处理 quarantine**（见 §7） |

---

## 3. 改造清单主表（按改动范围 小→大 排序）

| # | 文件 | 改动项（Windows → macOS） | 范围 | 分级 | 验收方式 |
|---|---|---|---|---|---|
| 1 | `requirements.txt` | 删 pywin32；加 pyobjc-framework-Cocoa/Quartz；hnswlib 改 conda 安装（附环境说明） | 1 | A + B | **A**：本地静态核对；**B**：CI 双架构安装成功 |
| 2 | `utils/file_ops.py`（`extract_file_paths`） | 兼容 macOS tkdnd 返回的 `file://` URL | 2 | **B** | 所在模块顶层将 import pyobjc（§4）→ 单测在 CI 跑 |
| 3 | `utils/shortcut.py` | 修饰键映射补 `Command_L/R` → ⌘ | 2 | **A** | 纯映射，本地伪 event 单测 |
| 4 | 文档 | Ctrl→⌘、explorer→Finder、update.hta→macOS 更新包、macOS 13+ 系统要求、公证要求 | 2 | A | 文案 |
| 5 | `controllers/update_controller.py`（平台 tag） | `darwin→macos` 分支已存在 ✓ | 2 | **B** | 单测在 CI 跑 |
| 6 | 6 处 `iconbitmap(.ico)` | → `iconphoto` + PNG（备 .icns 资源） | 3 | B + C | **B**：GUI 冒烟无 TclError；**C**：图标显示 |
| 7 | `utils/idle_tracker.py` | `GetLastInputInfo` → `CGEventSourceSecondsSinceLastEventType`（公共 API） | 3 | **B** | CI：实例化 + idle 秒数 > 0 断言 |
| 8 | `controllers/search_controller.py` 快捷键 | Ctrl → ⌘（映射在 shortcut.py，本地可测） | 3 | A + B + C | **A** 映射单测；**B** 冒烟；**C** 手感 |
| 9 | `controllers/app_controller.py` 拖拽 | `__on_drop` 适配 file://（配合 #2） | 3~4 | B + **C** | **B**：#2 单测（CI）；**C**：真实拖拽（tkdnd 在新系统行为，租机重点） |
| 10 | `utils/file_ops.py`（open/copy/delete） | explorer → `open`/`open -R`；CF_HDROP → NSPasteboard；send2trash 已跨平台 | 4 | B + C | **B**：CI 命令返回码 + NSPasteboard 读写断言；**C**：Finder UX |
| 11 | `utils/image_ops.py` | CF_DIB → NSPasteboard TIFF/PNG → PIL | 4 | B + C | **B**：CI 写/读断言；**C**：⌘+V 粘贴搜图 |
| 12 | `config/settings.py`（DPI+字体） | 删 `windll.shcore` → Tk scaling 或固定值；YaHei → PingFang SC；winreg → `open <url>` | 4 | A + B + C | **A**：settings 本地可 import、TkS 数学断言；**B**：Tk 缩放比查询；**C**：Retina 渲染 |
| 13 | `controllers/update_controller.py`（更新机制） | `update.bat`+`CREATE_NEW_CONSOLE` → `update.sh`（替换 .app） | 5 | B + C | **B**：CI .app 骨架演练 update.sh；**C**：完整更新流程 |
| 14 | `config/settings.py`（数据目录） | `ROOT/config/data` → `~/Library/Application Support/VimgFind` | 6 | B + C | **B**：迁移逻辑单测；**C**：.app 真机首启 |
| 15 | `main.spec` + 打包/签名/分发 | COLLECT → BUNDLE；.ico → .icns；更新包改版 | 7 | B + C | **B**：CI 打包 + plist/codesign(adhoc)/启动冒烟；**C**：**Developer ID + 公证**真机安装（macOS 26 强制公证） |

---

## 4. import 传染边界（决定 A/B 分级）

`utils/file_ops.py` 改造后顶层 import pyobjc（AppKit），沿 `internet → core/index_manager → core/search_engine → controllers/*` 传染。

**Windows 本地可测（A）**：`utils/cmd_parser.py`、`exclude_rules.py`、`i18n.py`、`shortcut.py`、`decorators.py`、`config/settings.py`（删 windll 后）、`config/types.py`、`core/tokenizer/*`、`core/multimodal_encoder.py`。

**仅 CI 可测（B 起点）**：`file_ops.py`、`image_ops.py`、`idle_tracker.py`、`internet.py`、`index_manager.py`、`search_engine.py`、`controllers/*`。

> macOS-only 的自然结果，**不为此调整代码结构**。

---

## 5. 分级汇总

### A —— Windows 本地现在就能测
#1 静态核对 / #3 快捷键映射 / #4 文档 / #8 映射部分 / #12 settings 逻辑；存量纯逻辑回归（cmd_parser、exclude_rules、i18n、tokenizer）。

### B —— GitHub Actions 全自动
#1 conda hnswlib + pyobjc 安装 / #2 file:// 解析 / #5 tag 匹配 / #6 GUI 冒烟 / #7 Quartz 空闲 / #10 open+NSPasteboard / #11 剪贴板图片 / #12 Tk 缩放 / #13 update.sh 演练 / #14 迁移逻辑 / #15 打包冒烟（adhoc 签名）。

### C —— 必须租 macOS 26.6 人工验证（一次性清单，按优先级排）
1. **tkdnd 拖拽三入口**（#9，新系统最高风险项）
2. ⌘+V 粘贴搜图（#11）
3. Finder 联动：打开/在 Finder 中显示/复制粘贴文件（#10）
4. 右键菜单（macOS Tk `<Button-3>`）+ ⌘ 快捷键手感（#8）
5. **Tk 渲染**：Retina 图标/字体/DPI/布局/多显示器（#6/#12）
6. **TCC 文件弹窗**：首次索引桌面/文稿/下载目录的行为（§2.3）
7. 完整更新流程（#13）
8. **签名安装**：Developer ID + 公证的 .app 安装运行（#15，macOS 26 强制公证）

---

## 6. GitHub Actions 策略

**Runner**：`macos-14`（arm64）主 + `macos-13`（x86_64）辅。
**环境**：`actions/setup-python`（python.org 自带 Tk 8.6）+ `setup-miniconda` 装 hnswlib（conda-forge），其余 pip。
**注意**：CI 无法做 Developer ID 签名/公证（需付费证书 + 时间戳服务）——CI 内用 adhoc 签名做结构校验，正式签名放发布阶段。

**流水线**：① conda hnswlib + pip install（双架构）→ ② import 冒烟（windll/pywin32 崩溃暴露）→ ③ pytest（A 级模块 + #2/#5/#14）→ ④ 系统能力断言（NSPasteboard、Quartz idle、`open` 返回码）→ ⑤ GUI 冒烟（启动→程序化断言→退出，截图 best-effort）→ ⑥ pyinstaller 打包 + plist/codesign(adhoc) 校验 → ⑦ 构建更新包 + update.sh 演练。

---

## 7. 租机测试执行要点（macOS 26.6 专属注意事项）

| 事项 | 说明 |
|---|---|
| **quarantine 处理** | macOS 26 对未公证软件强制 Gatekeeper 检查。从 Windows/网盘传入的 .app 会带 `com.apple.quarantine` → 优先**在租机上直接 git clone + pyinstaller 本地打包**（无隔离属性）；或传入后 `xattr -dr com.apple.quarantine` + 右键打开 |
| **公证测试** | 若已购 Developer ID 证书：在机上执行 `codesign` + `notarytool submit` 全流程，验证 Gatekeeper 无弹窗 |
| **环境搭建** | 机上装 python.org 3.12（自带 Tk）+ conda-forge hnswlib + pip 依赖；不要用系统 python3（无 tkinter） |
| **tkdnd 重点回归** | 拖拽是 2020 年二进制在 26 上的首要风险，先于其他 UI 项验证 |
| **TCC 弹窗** | 首次索引"桌面/文稿/下载"触发系统弹窗为正常行为，验证一次后记住授权状态即可 |
| **多显示器/Retina** | macOS 26 下缩放布局、深色模式与 Windows 差异需目测 |

---

## 8. 分阶段执行计划

| 阶段 | 环境 | 内容 | 产出 |
|---|---|---|---|
| **阶段 0** | Windows 本地（现在） | 存量纯逻辑单测基线；#3/#4/#12(本地部分) | 纯逻辑改动合入 macos 分支 |
| **阶段 1** | GitHub Actions（现在） | §6 流水线全跑通；重点 conda hnswlib、import 冒烟、GUI 冒烟、打包冒烟 | macOS 无 UI 部分验证报告 |
| **阶段 2** | 租 macOS 26.6（集中一次） | §5 C 级 8 项 + §7 专项（quarantine/tkdnd/TCC/公证） | 人工验收记录 + 修复补丁（修复后用 CI 回归） |
| **阶段 3** | 发布 | 双架构打包 + Developer ID 签名 + notarization + 更新包 | 正式分发产物 |

**租机效率建议**：C 级 8 项按"风险从高到低"排（tkdnd 拖拽 → 粘贴 → Finder → 渲染 → TCC → 更新 → 签名），1~1.5 天走完；每个修复优先降级为 B 级 CI 回归。

---

## 9. 风险表

| 风险 | CI 可暴露 | 说明 |
|---|---|---|
| **tkdnd 2.9.3 在 macOS 26 拖拽异常** | ❌ | 最高风险第三方；备选：跟进新版或编译 tkdnd 2.9.x 源码 |
| **Tk 8.6 在 macOS 26 渲染异常** | ⚠️ 部分（GUI 冒烟） | 视觉走查靠租机 |
| **macOS 26 强制公证** | ❌ | 分发必须 Developer ID + notarization（需付费证书）；CI 只能 adhoc 校验 |
| **未公证软件在租机的 Gatekeeper 拦截** | ❌ | 用 §7 quarantine 处理方案规避 |
| conda-forge hnswlib 安装 | ✅ 第一步 | 双架构各验一次 |
| import 级崩溃（windll/pywin32/pyobjc） | ✅ import 冒烟 | — |
| pyobjc NSPasteboard/Quartz 在 CI 可用性 | ⚠️ 需实测 | 不可用则降级 C |
| TCC 文件弹窗行为 | ❌ | 租机验证一次 |
| 私有 API 混入 | ✅ 代码审查 | §2.1 清单约束替换方案 |
| 快捷键手感、多显示器 | ❌ | 租机 |

---

## 10. 已知问题（封存，待后续处理）

### 10.1 置顶模式下 simpledialog 弹窗闪烁（未解决）

- **现象**：主窗口置顶时，`askstring/askinteger/askfloat` 弹窗会经历"先正常显示 → 被遮住 → 再显示"的闪烁。
- **根因**：弹窗 NSWindow 在创建后约 **40ms** 才注册到 `NSApp.windows()`，期间无法通过 `setLevel_` 提升层级（level 0 < 置顶主窗口 19），先显示后被遮。
- **已尝试方案**（均未完全解决）：
  1. `after` 定时器提升 → 对话框销毁后回调触发野指针崩溃（已改用 `after(0)` 消除崩溃）
  2. BasicDialog 内 title 匹配 `setLevel_` + 300ms 维护循环 → 提升有 ~40ms 延迟
  3. `buttonbox` 同步提升 + `after(0)` → NSWindow 未注册，同步失败
  4. `withdraw` 隐藏 → 轮询提升 → `deiconify` 显示 → 仍有 ~6ms level 0 可见窗口期
- **现状**：`views/widgets/simpledialog.py` 采用方案 4（withdraw→提升→显示），闪烁窗口期从 40ms 缩短到 ~6ms，但视觉上仍可感知；非置顶场景正常。
- **涉及文件**：`views/widgets/simpledialog.py`（`BasicDialog._raise_and_show / _raise_above_main / _maintain_above_main`）
- **后续方向**：在 Tk 层面拦截窗口首次映射（如重写 Dialog 初始化流程，在 NSWindow 注册前完成提升），或研究 NSWindow 注册时序，使提升先于窗口首次可见。
