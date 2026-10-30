# 标准黑色图形 JSON

仅在内容需要函数、包络或冲激频谱时读取本页。使用技能虚拟环境运行：

```powershell
<venv-python> <skill>/scripts/plot_diagrams.py --spec figures.json --output-dir figures
```

输出透明 PNG 和 `{"files":["绝对路径",...]}`。Markdown 用本地图片路径引用。线条、箭头、刻度和标签均为标准黑色，不采用手写扰动。

## 根对象与组合图

根对象为 `{"diagrams":[...]}`，至少一图。每个图包含：

| 字段 | 默认值与含义 |
| --- | --- |
| `name` | 必填；1～80 个 ASCII 字母、数字、点、横线或下划线，首字符为字母/数字；不含目录 |
| `width` | 1800；整图像素宽度，360～6000 |
| `columns` | 1；每行面板数，1～6 |
| `panel_height` | 480；每面板高度，180～3000 像素 |
| `gap` | 24；面板间距，0～200 像素 |
| `supersample` | 3；抗锯齿倍率，1～4；内存过大的组合会报错 |
| `panels` | 必填；1～36 个面板，从左到右、从上到下排列 |

## 面板公共字段

| 字段 | 默认值与含义 |
| --- | --- |
| `type` | `curve` 或 `impulses`，默认 `curve` |
| `x_range` | `[-pi,pi]` 的数值形式；JSON 中必须为有限递增数对 |
| `y_range` | `[-1.2,1.2]`；有限递增数对 |
| `axes_zero` | true；坐标轴穿过 0。0 不在范围内时贴近最近边界；false 时放左下 |
| `arrows` | true；正向坐标轴加箭头 |
| `title` | 可选；面板短标题，尽量用数学变量 |
| `x_label`,`y_label` | 可选；坐标轴标签，例如 `x = Ωt`、`s_1` |
| `x_ticks`,`y_ticks` | 默认均匀 5 个；可给数值数组，或 `[[数值,"标签"],...]`；空数组不画刻度 |
| `labels` | 可选；`[{"text":"...","x":0,"y":1,"anchor":"lt","scale":0.9,"italic":false}]`，坐标为数据单位 |

标签不是完整 LaTeX。支持 Unicode 数学符号和简单双下标：`s_1`、`S_{out}`、`s^{-1}`、`π/2`。`anchor` 为横向 `l/c/r` 加纵向 `t/c/b`，例如 `cb` 表示底边居中。避免把必要长说明放进图中。

字体自动探测 Windows Times/Cambria、Linux DejaVu/Liberation Serif 或 macOS Times，并以包内 DejaVu Serif 兜底。也可通过 `--font` 显式指定；不重发 Windows 系统字体。

## 曲线

`curves` 为 `[{"expression":"sin(x)","style":"solid"},...]`。`style` 仅支持 `solid`、`dashed`；虚线可用于包络。`samples` 默认 `max(1200,面板宽×2)`，范围 100～20000。非有限值和超出纵轴范围的区间断开，避免跨越渐近线。

表达式采用受限 AST 解释器，不执行 Python 代码：

- 变量 `x` 或 `t`，常数 `pi`、`e`，有限数字。
- 运算 `+ - * / % **`、一元正负号和括号；幂指数绝对值最多 32。
- 单参数函数 `sin cos tan exp sqrt abs log log10 sinh cosh`。
- 不支持属性访问、下标、导入、lambda、列表、比较、条件表达式和任意函数。不得将整段 Python 放进 expression。

## 冲激频谱

`impulses` 可为 `[[位置,权重],...]`，或 `[{"x":5,"weight":0.5,"label":"π/2"},...]`。箭头从 y=0 指向权重，位置与权重必须落在范围内；需让 `y_range` 包含 0。`label` 默认为权重数值，设为空字符串可隐藏。

## 示例

```json
{
  "diagrams": [{
    "name": "oscillation-and-spectrum",
    "width": 1800,
    "columns": 2,
    "panel_height": 520,
    "panels": [{
      "type": "curve",
      "x_range": [0, 6.283185307179586],
      "y_range": [-1.2, 1.2],
      "x_label": "x",
      "y_label": "s(x)",
      "x_ticks": [[0,"0"],[3.141592653589793,"π"],[6.283185307179586,"2π"]],
      "y_ticks": [-1, 1],
      "curves": [
        {"expression":"cos(x)*cos(4*x)"},
        {"expression":"cos(x)","style":"dashed"},
        {"expression":"-cos(x)","style":"dashed"}
      ]
    }, {
      "type": "impulses",
      "x_range": [-5, 5],
      "y_range": [0, 1],
      "x_label": "ω/Ω",
      "y_label": "|S(ω)|",
      "x_ticks": [-4, -3, 0, 3, 4],
      "y_ticks": [],
      "impulses": [
        {"x":-4,"weight":0.5,"label":"π/2"},
        {"x":-3,"weight":0.5,"label":"π/2"},
        {"x":3,"weight":0.5,"label":"π/2"},
        {"x":4,"weight":0.5,"label":"π/2"}
      ]
    }]
  }]
}
```
