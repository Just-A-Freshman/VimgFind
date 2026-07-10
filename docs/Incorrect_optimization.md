# 内存
## 1. 缩略图缓存策略（`_visible_image_data` 设计取舍）

**决定**：搜索结果缩略图加载后不主动清理，即使其已滚出可视区域。

**背景**：

`ThumbnailGridView._visible_image_data` 存储所有已加载缩略图的 `PhotoImage` 对象。当用户滚动时，滚动出视野的缩略图并不会被删除。

**理由**：

1. **结果数量有硬上限**：`max_match_count` 被限制为最大 100（见 [search_controller.py:216](controllers/search_controller.py#L216)），因此 `_visible_image_data` 最多持有 100 个 `PhotoImage` 对象。即使全部驻留，内存占用上限也完全可控。

2. **用户体验优先**：若滚动出视野就销毁缩略图，用户快速滚回时又会看到"图片加载中..."的占位符，必须等待重新解码、重新创建 `PhotoImage`。对于超过 100ms 的滚动回调间隔，频繁加载会产生明显的闪烁和延迟。保留已加载的缩略图可以保证无论怎么滚动，视野内的图片都能即时显示。

3. **PhotoImage 的特殊性**：`PhotoImage` 是 Tkinter 的 C 层面对象，销毁和重建的成本远高于普通 Python 对象。避免反复销毁重建有利于保持 UI 响应流畅。

**结论**：保留全部已加载缩略图是一种"以可控空间换时间"的策略，在结果上限为 100 的前提下，优先保证了滚动体验的流畅性。



### 2. ImageLoader 和索引更新线程池不共存

**错误判断**：ImageLoader 常驻 10 线程在搜索缩略图，索引更新又开一个线程池，认为两者会争抢 CPU。

**否决理由**：

- 搜索操作只编码一张图片或一段文字，单次推理耗时约几十到几百毫秒，瞬间完成，不存在"搜索进行中"的长窗口
- ImageLoader 加载缩略图是在搜索结果返回后异步进行，与搜索编码不在同一时间窗口
- 索引更新期间，[search_controller.py:109-112](controllers/search_controller.py#L109-L112) 明确阻塞了搜索操作的入口：

  ```python
  if self.app.index_controller.is_updating:
      if not messagebox.askyesno("提示", "索引正在更新中，是否终止索引更新？"):
          return
  ```

  要么用户终止索引，要么放弃搜索，不存在两者同时运行的路径

**结论**：两个线程池的实际执行窗口互斥，不存在并发争抢 CPU 的场景。



### 3. `_process_one` 中 `_loading_tasks` 不会泄露

**错误判断**：认为 `ImageOps.exif_transpose()` 或 `img.thumbnail()` 抛出未捕获异常时，对应 item 会永久留在 `_loading_tasks` 中。

**否决理由**：

- `parse_image_from_path()` 内部已有完善的 `try/except` 兜底（捕获 `UnidentifiedImageError`、`OSError`、`FileNotFoundError`），见 [image_ops.py:31-35](utils/image_ops.py#L31-L35)
- 只要 `Image.open()` 成功返回合法的 `Image` 对象，后续操作（读取 EXIF、缩略图）均为纯内存计算，在 PIL 主流版本中不存在可证实的失败路径
- "EXIF 损坏导致 `exif_transpose` 抛出 `OSError`"属于过于理论化的边缘情况，实际发生概率极低

**结论**：`_loading_tasks` 的清理机制在正常使用中是可靠的，无需额外防护。



### 4. `remove_nonexists` 批处理改造（否决）

**错误判断**：将 `remove_nonexists` 中逐文件 `Path.exists()` 改为按父目录分组 + `os.scandir` 批量检测，认为能从 O(文件数) 降到 O(目录数)。

**否决理由**：

- **扫描浪费**：`os.scandir(dir)` 会返回目录下所有文件名，但其中大部分可能并非索引文件（图片目录可能混有文档、配置文件等）。为了检查 200 个索引文件是否存在，需要扫描 1000 个无关文件，做了更多无用功。
- **集合空间开销**：构建文件名集合需要存储目录下所有文件名，哈希表的内存消耗不低。对于几千个文件的大目录，集合本身的内存开销可能就接近 MB 级别。
- **路径标准化问题**：scandir 返回的文件名（如 `IMG_001.JPG`）与 name_index 中存储的路径（如 `D:\Photos\IMG_001.JPG`）需要 normalize 后才能判存。字符串操作或 `Path` 对象创建的开销会抵消掉部分甚至全部收益。
- **操作性质**：`remove_nonexists` 是用户主动触发的维护操作，不在热路径上。当前逐文件 `Path.exists()` 方案配合 `tqdm` 进度条，对合理规模的索引已经够用。

**结论**：批处理改造得不偿失，保持原有逐文件判断逻辑不变。



