# Handwrite Homework Hacker · 手写作业扫荡机

> 本项目基于 lyc07/MarkdownToHandwrite
> 
> 一键扫荡大学作业

高数、概率论、信号与系统……算完还得再抄一遍？把整理好的文字、公式和 Markdown 喂进来，蓝色手写、双栏排版、高清 PNG 一条龙。

这是一个把中文、公式和 Markdown 排版为蓝色手写风格 PNG 的 Codex 技能。采用内置模板与确定性渲染器，支持双栏、多页、无框表格和标准黑色数学图。

## 效果与能力

- 蓝色手写正文与公式，默认一页两栏；内容过长时自动续页。
- 默认导出 **9276 × 6474** 高清 PNG，并生成便于浏览的缩略预览。
- 支持常用 LaTeX 数学子集，以及本地图片、无框表格。
- 根据 JSON 图形描述绘制黑色坐标、曲线和数学图。
- 不依赖运行中的 WebUI、云端 OCR 或图像生成 API。

复杂 LaTeX 宏包不在支持范围内；遇到不支持的公式，需要等价改写并检查结果。

## 安装与首次运行

需要 **64 位 CPython 3.12**。仓库附带 Windows x64 / CPython 3.12 的离线依赖包；首次配置仍需联网获取经哈希校验的上游字体和笔迹资产，或从已有上游项目离线恢复。

```powershell
git clone https://github.com/LiTongShuo/handwrite-homework-hacker.git
cd handwrite-homework-hacker
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -WorkDir .\.work
& .\.work\.notability-venv\Scripts\python.exe .\scripts\render_notes.py --input .\examples\basic.md --output-dir .\.work\output
```

`bootstrap.ps1` 会先创建虚拟环境，再安装锁定依赖、恢复资源并检查环境。若系统默认 Python 不是 3.12，可加 `-Python "实际的 Python 3.12 路径"`。

把 `examples/basic.md` 换成自己的 Markdown 文件即可生成新笔记。输出位于 `.work/output/`。

## 在 Codex 中使用

将整个仓库放入 Codex 的 `handwrite-homework-hacker` 技能目录，保留 [SKILL.md](SKILL.md)、脚本、模板与依赖文件。Windows 用户级安装示例：

```powershell
git clone https://github.com/LiTongShuo/handwrite-homework-hacker.git "$env:USERPROFILE\.codex\skills\handwrite-homework-hacker"
```

随后可提供文字或截图，并说明“使用 handwrite-homework-hacker 制作蓝色双栏手写笔记”。截图内容由使用技能的模型辨读和整理，渲染脚本本身不执行 OCR。

## 数学图与版式

用 `<columnbreak>` 显式换栏，用 `<newpage>` 换页。未指定时默认自动分栏。

```powershell
& .\.work\.notability-venv\Scripts\python.exe .\scripts\plot_diagrams.py --spec .\plots.json --output-dir .\.work\figures
& .\.work\.notability-venv\Scripts\python.exe .\scripts\render_notes.py --help
```

在 Markdown 中以相对路径引用生成的图片。图形 JSON 格式见[图形说明](references/plot-schema.md)。

## 其他平台与离线使用

macOS / Linux 需安装 Python 3.12，并允许从包索引下载相同版本的依赖：

```sh
PYTHON=python3.12 NOTABILITY_ALLOW_DOWNLOAD=1 sh scripts/bootstrap.sh .work
.work/.notability-venv/bin/python scripts/render_notes.py --input examples/basic.md --output-dir .work/output
```

已有上游资源时，可在 Windows bootstrap 中使用 `-AssetsFrom "上游项目目录" -Offline`。其他平台未作完整验证，详细依赖、缓存与故障处理见[运行说明](references/runtime.md)。

## 文档与目录

| 路径 | 内容 |
| --- | --- |
| [SKILL.md](SKILL.md) | 技能工作流与样式约定 |
| [examples/basic.md](examples/basic.md) | 可直接渲染的入门示例 |
| [references/example.md](references/example.md) | 包含图形的完整使用示例 |
| `scripts/` | 环境准备、资源校验、绘图与渲染 |
| `assets/` | 模板、配置、资源来源清单与备用字体 |
| `vendor/MarkdownToHandwrite/` | 保留原许可的上游代码 |
| `wheelhouse/` | Windows / Python 3.12 离线依赖 |

## 许可证与资源说明

项目原创代码和文档采用 [MIT 许可证](LICENSE)。上游 MarkdownToHandwrite 源码保留其 [MIT 许可与版权声明](vendor/MarkdownToHandwrite/LICENSE)，DejaVu 字体保留[字体许可](assets/fonts/LICENSE_DEJAVU)。其他依赖按各自许可分发。

上游手写字体和 SDT 轨迹没有随仓库重新分发，恢复清单记录了固定提交和 SHA-256。恢复下载不改变这些资源原有的使用与分发条款，见[第三方说明](THIRD_PARTY_NOTICES.md)及[上游资产声明](vendor/MarkdownToHandwrite/ASSET_LICENSES.md)。

本项目是独立的笔记排版工具，与 Notability 官方无隶属或赞助关系；相关名称和商标属于其权利人。
