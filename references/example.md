# 新内容示例

这只是格式参考。实际应用时替换成用户提供的内容，不固定题号和函数。

将以下内容写为任务目录的 `notes.md`：

```markdown
## 振子

$$
\ddot x+\omega_0^2x=0
$$

$$
\begin{aligned}
x(t)&=A\cos(\omega_0t+\phi),\\
v(t)&=-A\omega_0\sin(\omega_0t+\phi),\\
E&=\frac12m v^2+\frac12m\omega_0^2x^2.
\end{aligned}
$$

![轨迹](figures/oscillator.png)

## 统计

$$
\bar x=\frac{1}{n}\sum_{i=1}^{n}x_i
$$

| $i$ | 1 | 2 | 3 |
| --- | --- | --- | --- |
| $x_i$ | 2 | 3 | 4 |

$$
\bar x=3
$$
```

对应 `plots.json`：

```json
{
  "diagrams": [{
    "name": "oscillator",
    "width": 1800,
    "panel_height": 600,
    "panels": [{
      "type": "curve",
      "x_range": [0, 6.283185307179586],
      "y_range": [-1.2, 1.2],
      "x_label": "t",
      "y_label": "x(t)",
      "x_ticks": [[0, "0"], [3.141592653589793, "π"], [6.283185307179586, "2π"]],
      "y_ticks": [-1, 0, 1],
      "curves": [{"expression": "cos(x)"}]
    }]
  }]
}
```

运行绘图命令，再运行渲染命令。检查 manifest 中所有列的 used_height 不超过 available_height；预览应是蓝色笔迹、黑色函数图、无框数据表、左对齐且缩进两字的公式。默认自动分栏，不需要 `<columnbreak>`。
