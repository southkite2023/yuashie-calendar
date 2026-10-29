# 真实日本 TV 动漫分集日历（AniList 公共数据）

## 2026-10-29 首次上线

- 已接通 AniList 的 `https://graphql.anilist.co` 公开 GraphQL API。
- 首次 GitHub Actions 构建：[40840186011](https://github.com/southkite2023/yuashie-calendar/actions/runs/40840186011)，成功获取 **174 个**近两周日本 TV/TV_SHORT 动漫分集事件，覆盖日本时间 2026-10-29 至 2026-11-12。这个数字会随日期和排期改变。
- 与 2030 年的 **12 份虚构基础日历及两份生命周期测试日历完全隔离**。
- GitHub Pages 自动发布两种模式：
  - [真实动漫 · 精确播出时间（span）](https://southkite2023.github.io/yuashie-calendar/calendar/real/v1/anime/span.ics)
  - [真实动漫 · 仅开始日（start）](https://southkite2023.github.io/yuashie-calendar/calendar/real/v1/anime/start.ics)
- 工作流 `.github/workflows/publish-test-pages.yml` 每天 **00:37 和 12:37 UTC** 运行，另有相关代码推送或手动触发机制。GitHub Actions 定时执行可能延迟或被停用；不能保证到秒。
- 真实事件经 `src/yuashie_calendar/anilist.py` 获取、过滤、规范化并严格验证，再由 `scripts/build_real_anime.py` 生成 ICS。仅查询未来约两周播出安排，每次最多 8 页 × 50 项；并非对 AniList 进行全站或长期批量抓取。

## 可信度与内容边界

本批是 **AniList 社区维护的播出排期**，不是制作方或日本电视台官方信息；AniList 声明只重点保障未来播出数据。只纳入 AniList 标注 `countryOfOrigin=JP` 的非成人 TV/TV_SHORT 动画，源时间戳由 Unix UTC 转为 `Asia/Tokyo`。没有播出时间或身份信息的条目不会猜测日期，也不会根据固定每周周期预测后续分集。

- 一个事件 = `AniList mediaId + episode`；初次建档生成 UUIDv4；将 UUID、事件修订号、核验来源等持久化在版本库的 `data/real/anime-events.json`（仅公开排期元数据，无个人信息或密钥）。
- 重新核验但内容不变，不增加 `SEQUENCE`；排期或标题变更时保留 UID 并递增 `SEQUENCE`。
- 从来源列表消失 **不会自动认定为取消**。旧事件最多保留约 45 天；本阶段尚未实现 AniList 与日本官方渠道的跨源判定或由来源驱动的“待定”撤回。
- 数据源报错、超限、返回空或分页不完整时，工作流失败并**不部署空日历**，先前 GitHub Pages 上的最后成功发布版本保留。
- 发布产物只有 `.ics`、入口 `index.html` 和基础静态文件；`data/real/anime-events.json` 等状态和本地历史 **不会放入 Pages 发布目录**。

**使用限制**：用户订阅的是 **全部已抓取到的非成人日本 TV 动漫分集**，目前不能逐个选择番剧，也未接通国内视频平台的实际更新时间。订阅时只需使用 URL，不要下载后单次导入。 `span` 保留精确开播时刻；`start` 把每集转换为所属日期的全天事件。

官方开发资料与条款：
- [AniList GraphQL 使用指南](https://docs.anilist.co/guide/graphql/)
- [AiringSchedule 数据定义](https://docs.anilist.co/reference/object/airingschedule)
- [API 调用频率限制](https://docs.anilist.co/guide/rate-limiting)
- [AniList API Terms of Use](https://docs.anilist.co/guide/terms-of-use)

## 待办及正式验收

1. 通过 Mac/iPhone 实际**订阅**上述真实 `span.ics` URL，验证当前/未来两周分集正常出现（不与虚构测试混淆）。
2. 验证下一次定时任务是否继续成功，并检查当前源的可用性；GitHub Pages 在线 `Content-Type` 尚未由当前工具直接读取。
3. 通过有记录的真实数据变更，实机验证事件更新与修订；此前已验证的是**虚构测试**日历的生命周期，并非此 AniList 真实订阅。
4. 为四款游戏建立来源核验和人工确认机制；新游发售需另行对接官方或许可 API；在没有这些来源前，绝不公布猜测日期。
5. 使主站 `yuashie.cn/projects/004` 提供本批真实动漫订阅入口；任意类别/番剧组合的动态 Feed API 尚待实现。

如果未来将此服务用于商业用途或拓展为竞争性动漫追踪网站，应先复核 AniList API 使用条款及许可要求。
