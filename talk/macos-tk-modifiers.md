# macOS Tk 8.6 修饰键实测（M2 / conda Python 3.12 / Tk 8.6 真机诊断）

> 用 `_diag_keys.py`（已删除）在 macOS 25.5 实测，记录修饰键的 keysym 与 event.state 位。
> 用途：多选逻辑（`thumbnail_grid._on_canvas_click`）、快捷键记录（`utils/shortcut.py`）的平台适配依据。

## 实测结果

| 物理键 | keysym | keysym_num | event.state 位 | 说明 |
|---|---|---|---|---|
| **⌘ Command** | `Meta_L` | 65511 (0xFFE7) | **0x0008** (Mod1) | macOS Tk 中 ⌘ 的 keysym 是 **Meta_L**，state 映射到 **Mod1** |
| ⌥ Option | `Alt_L` | 65513 (0xFFE9) | 0x0010 (Mod2) | Option 键 keysym 是 Alt_L，state 映射到 Mod2 |
| ⇧ Shift | `Shift_L` | 65505 (0xFFE1) | 0x0001 | 标准 |
| ⌃ Control | `Control_L` | — | 0x0004（推断） | Control+点击 被系统模拟为右键(Button-2) |

## 适配结论

1. **keysym**：`utils/shortcut.py` 需把 `Meta_L/R → "Cmd"`（已加），否则快捷键记录会显示 `Meta_L` 而非 `Cmd`。
2. **state 位**：多选判断需覆盖 `0x0008`（⌘ 实测位）。当前实现检查
   `ctrl = state & 0x0004`，`cmd = state & (0x0008|0x0010|0x0020|0x0040)`（宽泛覆盖不同 Tk 版本的映射）。
   副作用：Option+点击 也会触发多选（macOS 无 Option+点击标准语义，可接受）。
3. **多选操作**：macOS 上请用 **⌘+点击**（对应 Windows 的 Ctrl+点击）。Control+点击 是 macOS 系统右键，无法用于多选。
