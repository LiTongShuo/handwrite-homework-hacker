# 运行与依赖

## 固定运行环境

- CPython **3.12**，64 位；不捆绑 Python 解释器或复制旧虚拟环境。
- `requirements.txt` 固定七个包及版本；`wheelhouse/` 包含 Windows x64 / CPython 3.12 离线轮子。
- PNG 模板、核心 MIT 源代码与许可说明内置。上游版本为 `634cf07987a9c84c59f808e03f879c9d93485374`，来源 [MarkdownToHandwrite](https://github.com/lyc07/MarkdownToHandwrite)。
- 不需要 handright、PyMuPDF、onnxruntime、ReportLab 以外的 PDF 工具或系统 TeX。ReportLab 因上游模块顶层导入仍需安装；本技能只交付 PNG。
- 标准图的字体按 Windows Times/Cambria、macOS/Linux 常见衬线字体探测；还内置允许再分发的 DejaVu Serif 作为兜底，许可在 `assets/fonts/LICENSE_DEJAVU`。可通过绘图脚本 `--font` 指定本机字体。

## 字体与笔迹资产

旧字体及 SDT 轨迹的上游声明并未授予明确再分发许可，所以压缩包不重发这些上游资产。`assets/asset-sources.json` 保存原仓库固定提交、URL、字节数与 SHA-256。首次 bootstrap 自动从原地址恢复并校验；本机已安装的技能缓存可直接复用。详见 `vendor/MarkdownToHandwrite/ASSET_LICENSES.md`，不能把这些资产笼统称为 MIT。

用户提供的“AP 手写”已按 `1_SDT.ttf` 的“编号_名称”格式命名为 `assets/fonts/2_APHandwriting.ttf`，随个人技能包保存。其来源、字节数和 SHA-256 记录于 `assets/asset-sources.json` 的 `bundled_user_assets`；未附开源授权，不归入代码的 MIT 许可。运行时直接读取技能内资源，不依赖原附件的绝对路径。

已有原仓库时可离线恢复：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<skill>/scripts/bootstrap.ps1" -WorkDir "<work>" -AssetsFrom "<existing-MarkdownToHandwrite>" -Offline
```

本机资源路径只是可选缓存来源，不写入技能的运行依赖；没有原项目也能按固定来源恢复。

资产下载仅限声明的四个字体/轨迹文件；缺失或哈希不符时停止，不使用未知替代资产。普通后续渲染无需联网。

## 默认字体混排

`render_notes.py` 默认启用 `--font-mode mixed`：以下范围内，每次出现的字符独立以 50% 概率选用新字体 `2_APHandwriting.ttf` 或旧字体 `1_SDT.ttf`。同一个字符在不同位置可以使用不同字体；不强制机械交替，也不要求短句刚好各半。

- 数字、英文字母 `A–Z / a–z`、汉字。
- 符号：`！ @ # ￥ % & * （ ） - = + 【 】 { } ； ： ’ “ ” 《 》 / \ _ ^ | · ~ ， 。`。
- 上述标点经现有排版流程转换出的半角形式也包含在内。

其余字符（含希腊字母和 `∫ × ≤ ≈ ∞` 等数学符号）只使用旧字体链；新字体缺字时也回退旧字体链。新字体不会被混入旧字体的兜底链。

两种字体均用中心线/旧 SDT 轨迹，经同一渲染器按同一笔宽重绘。笔宽由旧字体的 `sdt_stroke_width` 和正文像素字号确定，默认 720 DPI、6.6 pt 时为 **2.578125 px**；两者共同关闭笔压宽度、收笔粗细与二次字重变化，并使用 6 倍抗锯齿。保留各自字形，不以字号缩放或单纯加粗新字体代替等线宽。

`--seed <整数>` 控制可复现随机选择；省略时沿用配置中的 seed。测量和落图使用缓存与同一位置标记，重复公式在不同位置也会分别选择字体。`manifest.json` 的 `font_mixing` 记录字体名称、seed、共同笔宽、使用统计及逐字符字体统计。旧字体单独使用时加 `--font-mode old`；更换新字体时可加 `--new-font <字体路径>`。

## 其他平台

同为 Python 3.12 的其他平台可在 Windows bootstrap 加 `-AllowDownload`，或在 shell 设置 `NOTABILITY_ALLOW_DOWNLOAD=1`，从包索引安装同一版本。默认先尝试离线轮子。未验证的平台应执行 doctor 和一张新内容试图后再交付。

若虚拟环境创建或包安装被沙箱的临时目录权限阻止，只放行本任务的虚拟环境安装步骤；不要改全局 Python 或关闭系统安全设置。一次安装失败后根据错误修正环境，不能无意义重复下载。

## 输入与排版

渲染器接受任意 Markdown，不绑定题号。标题、短段落、展示/行内公式、无框表格、本地图均可使用。用 `<columnbreak>` 明确换栏，`<newpage>` 明确换图；通常保留自动分栏。`--split-heading` 可指定右栏开始的标题。

参数以 `render_notes.py --help` 为准：默认两栏、720 DPI；`--columns 1` 单栏。较低 DPI 可试排，但最终必须检查全分辨率结果，低 DPI 的字形留白量不总是严格等比。

渲染失败时先看具体公式错误。常见处理是用 `aligned` 分行、展开宏、使用支持的关系/运算符；不能将失败公式删掉。无框答案是渲染器默认，输入包含 `\boxed` 也不会绘制框。

模板已内置，不需要再次调用 image_gen。只有用户要求更换模板并且需要图像编辑时，才按相应图像编辑流程处理新模板。
