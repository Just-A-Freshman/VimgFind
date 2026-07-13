# 代码问题回答

## Q1

A：为什么索引更新时，检查变更文件，只是检查文件的大小有没有变，而不结合实际的修改时间？
Q：这是因为，从统计学角度来看：

- 现代的图片（除了像raw这种原始图片格式）都是会采用压缩技术的。图片上任意一点变化，都会在压缩技术下产生对应的存储空间变化。因此，一张图片几乎不可能在修改后还保证存储空间不变。
- 恰恰相反，更常见的情况是你临时修改了图片，然后撤回修改，再保存。结果图片存储空间不变，修改时间却变了。在这种情况下变更这张图片的索引没有任何意义。
- 此外，只存储原始图片的大小空间而不存储修改时间，也节省了一定的索引的存储空间。

## Q2
A：在：@core/index_manager.py中，为什么要拿50000作为初始索引的大小？
Q：事实上，这个大小确实可以调小，比如调整到10000，这还可以进一步减少内存消耗。不过我认为这并不太必要，理由是：初始化一个过小的索引，会让索引更新时频繁触发扩容操作。扩容操作时需要申请新的堆内存，复制原内容，这些都会消耗一些时间。而相比之下，50000是一个平衡点，既保证了相对较小的内存消耗，又保证了不那么容易频繁触发索引扩容带来的时间消耗。


## Q3
A：@core/search_engine.py中，收集新的需要更新索引的过程非常粗暴，直接就是一次性用一个列表进行全搜集，这是不是应该优化一下？
Q：这的确是一个可以优化的点，但实际上优化价值并不高。理由很简单：即使索引真的需要一次性插满100万条索引数据，经过估算也只是大约需要110MB的内存。换言之，极限情况下的内存消耗完全在可控边界内，大不不必提前优化。与之相比，HNSW一次性加载100万条索引记录到内存中，反而才是那个真正的内存大户。

## Q4

A：@core/index_manager.py中的`VectorIndexManager`的`add_vector()`，一次只能追加一条向量。但是我们都知道，`hnsw.Index.add_items()`是可以一次性追加多条向量的，这可以提高插入向量的效率。为什么不那么干呢？

Q：这主要有两点考量：

- 数据一致性：`VectorIndexManager`和`NameIndexManager`是非常严格的伴生关系，两者的向量添加是需要同时进行的。代码中，假设我们首先通过`add_names`拿到对应的id，正准备调用`add_vectors()`插入向量时，程序如果在此时被关闭，那么这将直接引入一批数据的不一致，这批被插入的图片将永远没办法在索引中被搜索到，除非重建索引。而一次插入一条，奔溃造成的影响至多是一条索引。
- 提升有限：这其实才是最根本的原因。经过测试，图片预处理 + ONNX推理占总用时的消耗远远高于向量插入的时间，至少占比在1000:1以上。因此，优化索引插入时间几乎没有时间上的意义。
- 显示进度：编码一条就插入一条，在进度显示上比较流畅。

当然，这也引向了一个问题，我们的程序应该引入良好的奔溃恢复机制。这将在未来版本考虑。



## Q5

A：在@settings.py中，为什么要用`os.chdir()`？

```python
@property
def model(self) -> ModelConfig:
    os.chdir(Setting.models_dir / model_id)
```

Q：答案非常简单直接，因为每个模型下都有一个`model.json`文件，其中的`vector_index_path`、`name_index_path`以及模型路径等均使用的是相对路径。你当然可以在传入模型时再动态把这个相对路径转成对应的绝对路径，不过我认为没有太大必要。不过据说目前这种写法存在多线程的危险，但我还暂时不太清楚其产生实际危害的路径。



## Q6

A：在筛选框（filter_panel）中，文件去重（dedup）的实际代码为什么是用相似度 + 文件大小的方式去重，这并不能保证两个图片是一样的呀？

Q：的确，但凡是都要讲求概率。两个向量在空间中和另外一个向量的相似度完全一样，其概率低得可怕。要知道相似度本身也是浮点数类型，好几位小数都要一模一样几乎就不可能。再加上图片大小必须一样的双重保险，两个图片不同的概率将无限趋近于0。这一设计旨在避免在筛选时进行实际的图片比较，提高图片去重时的性能。

另外，这种用极低的出错概率来保障性能的设计不止一处。在verify_index_match()函数中，我们同样也是随机抽取3个向量看模型编码是否一致，来确定是否符合软重建的标准。这在软件开发中是非常常见的做法。





# 错误的尝试——目录扫描缓存

## 目标

减少每次"更新索引目录"时不必要的全量目录遍历。对于未发生结构变化的目录子树，直接跳过遍历以加速索引更新。

---

## 总体设计

三层改动：

```
utils/file_ops.py        — get_file_iterator 新增 skip_dir_fn 回调接口
core/index_manager.py    — 新增 ScanCacheManager 类，独立管理缓存
core/search_engine.py    — SearchTool 集成 ScanCacheManager，修改 __get_new_files
```

---

## 一、ScanCacheManager（core/index_manager.py）

### 职责

管理 `scan_cache.json` 的读写（与 `name_index.json` 同目录），提供安全阈值和目录存在性判断。

### 存储格式

```json
{
  "scan_start_ns": 1720784069000000000,
  "update_finish_ns": 1720784080000000000,
  "known_dirs": [
    "d:\\photos",
    "d:\\more_photos"
  ]
}
```

### 关键 API

| 方法                                | 说明                                                         |
| ----------------------------------- | ------------------------------------------------------------ |
| `threshold` (property)              | 返回 `min(scan_start_ns, update_finish_ns)`，即"最近一次确认的安全时间点" |
| `is_root_known(dir_path)`           | 判断 `dir_path` 是否位于任意 `known_dirs` 下（含根自身）。新添加的 search_dir 返回 False |
| `update(start, finish, known_dirs)` | 设置新时间戳，替换 `known_dirs` 为当前 search_dir 列表，立即写盘 |
| `forget_root(dir_path)`             | 从 `known_dirs` 中移除指定路径，用于删除 search_dir 时同步清理 |
| `reset()`                           | 清空所有数据，删除缓存文件                                   |

### 核心代码

```python
class ScanCacheManager(object):
    __slots__ = ("__cache_path", "__scan_start_ns", "__update_finish_ns", "__known_dirs")

    def __init__(self, cache_path: str) -> None:
        self.__cache_path = cache_path
        self.__scan_start_ns: int = 0
        self.__update_finish_ns: int = 0
        self.__known_dirs: set[str] = set()
        self.__load()

    @property
    def threshold(self) -> int:
        return min(self.__scan_start_ns, self.__update_finish_ns)

    def is_root_known(self, dir_path: str) -> bool:
        normalized = file_ops.normalize_path(dir_path)
        for known in self.__known_dirs:
            if normalized.startswith(known):
                return True
        return False

    def forget_root(self, dir_path: str) -> None:
        self.__known_dirs.discard(file_ops.normalize_path(dir_path))
        self.__save()

    def update(self, scan_start_ns: int, update_finish_ns: int, known_dirs: list[str]) -> None:
        self.__scan_start_ns = scan_start_ns
        self.__update_finish_ns = update_finish_ns
        self.__known_dirs = {file_ops.normalize_path(d) for d in known_dirs if d}
        self.__save()

    def reset(self) -> None:
        self.__scan_start_ns = 0
        self.__update_finish_ns = 0
        self.__known_dirs.clear()
        file_ops.delete_file(self.__cache_path)
```

---

## 二、get_file_iterator 回调接口（utils/file_ops.py）

### 改动

新增可选参数 `skip_dir_fn`，在遍历到每个子目录时回调，返回 `True` 跳过该子树：

```python
def get_file_iterator(
    target_dir: str,
    exclude_rules_list: list[str] | None = None,
    skip_dir_fn: Callable[[str], bool] | None = None  # ← 新增
) -> Iterator[str]:
```

两处调用（`while` 循环顶部 + `entry.is_dir()` 分支内）：

```python
# 位置 1：while 循环顶部，os.scandir 之前 — 提前跳过整个子树
if skip_dir_fn and skip_dir_fn(path):
    continue

# 位置 2：entry.is_dir() 分支，位于 exclude_rules 判断之后，stack.append 之前
if entry.is_dir(follow_symlinks=False):
    rel = os.path.relpath(entry.path, target_dir).replace("\\", "/")
    if rules_obj and rules_obj.is_excluded(rel, is_dir=True):
        if not rules_obj.is_affected_by_negation(rel):
            continue
    if skip_dir_fn and skip_dir_fn(entry.path):
        continue
    stack.append(entry.path)
```

---

## 三、SearchTool 集成（core/search_engine.py）

### 1. 初始化

在 `__async_init` 中创建 `ScanCacheManager`：

```python
scan_cache_path = str(
    Path(self.__setting.model.index.name_index_path).parent / "scan_cache.json"
)
self.__scan_cache = ScanCacheManager(scan_cache_path)
```

### 2. `__get_new_files` — 使用回调跳过未变更子目录

```python
def __get_new_files(self, target_dir: str, exclude_rules: list[str] | None = None) -> list[str]:
    threshold = self.__scan_cache.threshold

    def _skip_if_unchanged(dir_path: str) -> bool:
        # 新 search_dir（从未被扫描过）→ 不跳过，全量扫描
        if not self.__scan_cache.is_root_known(dir_path):
            return False
        try:
            return os.stat(dir_path).st_mtime_ns <= threshold
        except OSError:
            return False

    current_files = file_ops.get_file_iterator(target_dir, exclude_rules, _skip_if_unchanged)
    existing_files = set(
        file_ops.normalize_path(i[0])
        for i in self.__name_idx_mgr.name_index
    )
    new_files = []
    for file in current_files:
        if self.force_stop_update:
            break
        if file_ops.normalize_path(file) not in existing_files:
            new_files.append(file)
    return new_files
```

### 3. `update_index` — 首尾记录时间戳

```python
def update_index(self, image_dirs, max_workers, exclude_rules, progress_bar):
    # ...
    self.__init_event.wait()
    this_scan_start_ns = time.time_ns() if not self.force_stop_update else 0

    for image_dir in image_dirs:
        dir_files = self.__get_changed_files(image_dir) + self.__get_new_files(image_dir, exclude_rules)
        # ... 其余处理不变 ...

    progress_bar.close()
    if not self.force_stop_update:
        self.__scan_cache.update(this_scan_start_ns, time.time_ns(), image_dirs)
```

### 4. `reset_index` — 联动清空缓存

```python
def reset_index(self) -> None:
    self.__init_event.wait()
    self.__vec_idx_mgr.reset_index()
    self.__name_idx_mgr.reset_index()
    self.__scan_cache.reset()
```

### 5. `remove_files_in_directory` — 删除目录时同步清理缓存

`remove_files_in_directory` 内部调用 `forget_root` 清理缓存，无需控制器额外调用。

---

## 四、控制器同步（controllers/index_controller.py）

在 `delete_search_dir` 中删除 search_dir 时，`remove_files_in_directory` 内部已调用 `forget_root` 同步清理 `known_dirs`，无需额外操作：

```python
for dir_path in dirs_to_delete:
    self.app.search_tools.remove_files_in_directory(dir_path, remaining_dirs)
```

---

## 五、完整流程

```
用户点击"更新索引目录"
  │
  ├─ update_index() 启动
  │   ├─ 记录 this_scan_start_ns = time.time_ns()
  │   │
  │   └─ 遍历每个 search_dir：
  │       ├─ __get_changed_files()     ← 始终执行（比对 size）
  │       │
  │       └─ __get_new_files()
  │           ├─ 创建 _skip_if_unchanged(dir) 回调：
  │           │   ├─ is_root_known(dir) == False → 不跳过（新目录）
  │           │   ├─ dir.mtime ≤ threshold       → 跳过该子树
  │           │   └─ dir.mtime > threshold        → 进入扫描
  │           │
  │           └─ 传入 get_file_iterator(..., skip_dir_fn)
  │               └─ 遍历栈：每遇到子目录调一次回调
  │
  ├─ 处理完毕，未中断
  │   └─ scan_cache.update(start, finish, image_dirs)
  │       ├─ 持久化 scan_start_ns
  │       ├─ 持久化 update_finish_ns
  │       └─ 替换 known_dirs 为当前 search_dir 列表
  │
  └─ 中断 (force_stop_update)
      └─ 不推进缓存 → 下次全量重扫
```

---

## 六、安全阈值公式

```
threshold = min(scan_start_ns, update_finish_ns)
```

- `scan_start_ns`：上一次更新**开始扫描**的时间
- `update_finish_ns`：上一次更新**成功完成**的时间

使用 `min` 而非仅 `update_finish_ns` 的原因：

```
时间线：
  T_start                  T_write              T_finish
    │─────────────────────────┬──────────────────────│
  扫描开始              用户写入文件              更新完成

阈值用 min(T_start, T_finish) = T_start
T_write > T_start  → 下次更新触发扫描 ✅

阈值若仅用 T_finish：
T_write < T_finish → 跳过 → 漏掉新文件 ❌
```

---

## 七、边界情况

| 场景                          | 行为                                                         |
| ----------------------------- | ------------------------------------------------------------ |
| **首次使用**（无 cache）      | `known_dirs` 为空 + 两时间戳=0 → `is_root_known` 全 False → 全量扫描 |
| **正常更新，无变化**          | 所有子目录 mtime ≤ 阈值 + `is_root_known` True → 全部跳过    |
| **新增文件**                  | 所在目录 mtime 更新 > 阈值 → 进入该目录 → 扫描到新文件       |
| **文件内容修改（size 变）**   | dir mtime 不变 → `__get_new_files` 跳过；`__get_changed_files` 通过 size 比较捕获 |
| **文件内容修改（size 不变）** | dir mtime 不变且 size 不变 → 无影响（设计取舍，发生率极低）  |
| **更新期间写入文件**          | 目录 mtime 更新 > 阈值（即上一次 scan_start）→ 触发扫描 ✅    |
| **force_stop 中断**           | 缓存不推进 → 下次重新全量扫描                                |
| **删除 search_dir**           | `forget_root` 同步清理 `known_dirs` + `remove_files_in_directory` 清理索引 |
| **重加已删除的 search_dir**   | `known_dirs` 中已清除 → `is_root_known` 返回 False → 全量扫描 |
| **reset_index**               | `scan_cache.reset()` 清空所有数据 → 下次全量扫描             |
| **目录不存在 / 无权限**       | `os.stat` 抛异常 → `_skip_if_unchanged` 返回 False（不跳过）→ `os.scandir` 处理 |



## 八、驳回理由

文件夹的修改时间由文件夹下的直接文件所决定，而与文件夹完全无关。如果文件夹A下有文件夹B，文件夹B中的文件内容发生任何变化，均不会对文件夹A的修改时间构成影响。这意味着，通过检测文件夹的修改时间，判断其下所有层级的文件是否发生更改，是根本不成立的。

所有操作系统均是如此设计，其意在优化性能。否则一个文件的修改就需要向上传导给所有父文件夹的元信息，非常消耗性能。