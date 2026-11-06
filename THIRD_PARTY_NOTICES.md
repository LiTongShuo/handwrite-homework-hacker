# 第三方代码、字体与依赖

本仓库的项目级 MIT 许可证适用于项目原创代码和文档，不会覆盖或替换第三方许可。

| 内容 | 来源与许可 |
| --- | --- |
| MarkdownToHandwrite 核心源码 | 固定提交 `634cf07987a9c84c59f808e03f879c9d93485374`，保留 [MIT 许可证](vendor/MarkdownToHandwrite/LICENSE)及 cygni 版权声明 |
| DejaVu Serif 字体 | 保留 [LICENSE_DEJAVU](assets/fonts/LICENSE_DEJAVU) |
| AP 手写字体 `2_APHandwriting.ttf` | 用户提供并按编号规范重命名；随仓库保存，未附开源授权，不受项目 MIT 许可证覆盖；来源和 SHA-256 见资源清单的 `bundled_user_assets` |
| 离线 Python wheel | 版本见 [requirements.txt](requirements.txt)，版权和许可文件保留在各 wheel 的 `.dist-info` 目录中 |
| 上游手写字体与 SDT 轨迹 | 不随本仓库分发，来源与哈希见 [asset-sources.json](assets/asset-sources.json)，原许可状态见[上游资产声明](vendor/MarkdownToHandwrite/ASSET_LICENSES.md) |

恢复脚本从固定上游地址或本地副本获取字体/轨迹并验证 SHA-256。资源可下载不等于已获再分发许可，不应将恢复后的文件加入公开发布包。

上游项目：https://github.com/lyc07/MarkdownToHandwrite

本项目与 Notability 官方无隶属或赞助关系，相关名称及商标归原权利人所有。
