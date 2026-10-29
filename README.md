# yuashie-calendar

游戏与动漫更新订阅日历：汇集原神、崩坏：星穹铁道、绝区零、明日方舟版本与卡池事件、动漫周更和新游戏发售，计划支持自选内容与显示模式，生成可订阅的 ICS 日历，接入 yuashie.cn。

> 当前阶段：**日本 TV 动漫真实排期已接入 AniList API**，首次查询成功获取 174 个未来分集事件，发布独立的真实 ICS 订阅路径，并通过 GitHub Actions 安排每天两次自动更新。12 份 2030 年虚构测试日历仍独立保留，Mac Apple Calendar 已通过基础订阅及延期/恢复同步测试；游戏、发售及任意组合订阅尚未接通真实数据。

## 已上线的真实动漫订阅

- [日本 TV 动漫 · 精确播出时间（span）](https://southkite2023.github.io/yuashie-calendar/calendar/real/v1/anime/span.ics)
- [日本 TV 动漫 · 仅开始日（start）](https://southkite2023.github.io/yuashie-calendar/calendar/real/v1/anime/start.ics)

这是 AniList 社区维护的未来播出数据，并非制作方或电视台官方公告；事件可以更改。以上两个地址与旧版 2030 年虚构测试源完全独立。动态组合生成器尚未上线，不要将 `.invalid` 域名当作真实地址。

## 项目目标

| 内容 | 计划覆盖 |
| --- | --- |
| 游戏版本事件 | 原神、崩坏：星穹铁道、绝区零、明日方舟的前瞻直播、版本更新、卡池更新 |
| 动漫周更 | 日本动漫每周播出及分集更新时间 |
| 新游戏发售 | 新作品发售日期，后续按平台和地区筛选 |

计划支持选择订阅内容，以及「仅开始日」和「完整持续期间」两种显示模式；具体日期与时间呈现规则将在数据模型阶段确定。

## 初步方案

数据来源 → 采集 → 统一事件数据 → ICS 生成 → 稳定 HTTPS 订阅地址 → 日历客户端。

- 日历生成：Python + icalendar；已实现 AniList 公开播出时间采集器、规范化、持久化 UUID 与修订；游戏采集器仍待实现。
- 网站入口：主站 Netweb Project 004 已加入独立真实动漫订阅入口；原有任意组合 URL 仍是故意无效的演示链接。
- GitHub Actions：虚构样例与真实动漫 ICS 均可构建部署；每 12 小时计划刷新 AniList API，成功后提交公开排期快照并持久化 UID/SEQUENCE，失败不覆盖旧版。
- 发布：GitHub Pages 分别提供虚构测试和真实动漫日历；自定义组合订阅仍需动态服务或预生成策略。
- 数据来源：优先结构化 API 与官方公告，Wiki 为候选补充来源；可用性、许可、限流和维护成本仍需核实。

这些是规划方向，并不表示已实现或已验证所有数据源。

## 目录结构

```text
yuashie-calendar/
├── README.md
├── .gitignore
├── requirements.txt     # 固定运行依赖
├── requirements-dev.txt # 测试依赖
├── pyproject.toml       # 测试配置
├── docs/
│   ├── roadmap.md       # 实施顺序与当前进度
│   ├── event-model.md   # 统一事件数据规范 v1
│   └── running.md       # 本地运行与持久化说明
├── config/              # 后续放置内容与来源配置
├── data/
│   └── samples/         # 后续放置明确标记的虚构测试数据
├── src/
│   ├── yuashie_calendar/ # 已实现：校验、投影、生成、发布历史、CLI
│   ├── fetchers/        # 后续实现数据采集
│   ├── normalizers/     # 后续实现事件标准化
│   └── calendars/       # 后续实现 ICS 生成
├── tests/               # 已实现：样例、序列化、生命周期与失败保留测试
├── web/                 # 后续网站订阅选择入口
└── dist/                # 后续生成的发布产物（不纳入 Git）
```

预留目录使用 `.gitkeep` 占位；`dist/` 在生成本地产物时创建，不纳入 Git。

## 实施顺序

1. 确认统一事件模型、事件类型、UID、时区及日期规则。
2. 准备少量虚构样例，验证 JSON 到 ICS 的转换。
3. 发布测试订阅地址，验证 Apple Calendar / Google Calendar 的订阅与更新行为。
4. 逐个验证并接入真实数据源。
5. 实现内容选择、显示模式及主站入口。
6. 配置定时刷新、失败监控与发布流程。

第一步设计见 [统一事件数据规范 v1](docs/event-model.md)，测试数据见 [离线虚构样例](data/samples/README.md)。2026-10-29 已完成 [真实动漫日历接入](docs/real-anime.md)，通过 GitHub Actions 构建与发布；Mac Apple Calendar 已人工验证虚构源基本订阅和生命周期。在线独立 HTTP/MIME 与真实动漫订阅的实机验收仍待确认。后续详见 [实施路线](docs/roadmap.md)、[测试说明](docs/test-pages.md) 与 [本地生成](docs/running.md)。

## 数据与维护原则

- 保存来源链接、来源标识与核验时间；区分官方确认和推测日期。
- 区分游戏服务器、地区、平台与动漫播出渠道，避免混用时间。
- 事件改期时保持稳定身份，避免重复订阅事件。
- 抓取失败时保留最后有效数据，并呈现更新时间。
- 不提交密钥、令牌、真实用户订阅信息或本地环境文件。
- 仓库尚未选定开源许可证；数据内容及相关名称、商标的权利归原权利人所有。
