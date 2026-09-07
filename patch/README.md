-- 2026.09.08 --
文件：tk86t.dll
目的：由于tk=8.6.15中，TTK_STATE_OPEN 不再映射到 user1，而是映射到了一个新引入的 widget 状态（或者不再映射到任何 widget 状态），这直接导致Treeview自定义identifier相关代码无法工作；该文件是通过修改tk的源代码后重新编译得到的，这使得如下写法仍然能正常工作：

```
self._style.element_create(
    el_name, "image", self._img_close,
    ("user1", "!user2", self._img_open),
    ("user2", self._img_empty),
    sticky=tk.W, width=size, border=0,
)
```

Tip：使用tk=8.6.14版本，该问题虽然能够解决，但引入两个问题：Treeview组件的下边框会在滚动内容超出区域时被遮挡，该BUG恰好在tk=8.6.15修复。此外，已有的release打包环境已经使用了tk=8.6.15，降级不是明智之选。

位置：如果你是使用conda创建虚拟环境，假设创建的虚拟环境为vimgfind，你需要找到：`Anaconda\envs\vimgfind\Library\bin`文件夹，并将该：tk86t.dll替换文件夹中原来的tk86t.dll