# yuashie-calendar

游戏与动漫更新订阅日历：汇集原神、崩坏：星穹铁道、绝区零、明日方舟版本与卡池事件、动漫周更和新游戏发售，计划支持自选内容与显示模式，生成可订阅的 ICS 日历，接入 yuashie.cn。

> 当前阶段：事件规范、离线校验与 ICS 生成器已经完成。12 份 **虚构测试** ICS 已通过 GitHub Actions 成功部署至 [GitHub Pages](https://southkite2023.github.io/yuashie-calendar/)（2030 年虚构事件；仅供测试）。主站 Project 004 已有前端订阅选择器，但仍使用无效测试域名；真实数据源、任意组合 Feed API 和正式订阅尚未上线。GitHub Pages 线上 HTTP 内容类型及 Apple/Google Calendar 实机订阅有待独立验证。

## 项目目标

| 内容 | 计划覆盖 |
| --- | --- |
| 游戏版本事件 | 原神、崩坏：星穹铁道、绝区零、明日方舟的前瞻直播、版本更新、卡池更新 |
| 动漫周更 | 日本动漫每周播出及分集更新时间 |
| 新游戏发售 | 新作品发售日期，后续按平台和地区筛选 |

计划支持选择订阅内容，以及「仅开始日」和「完整持续期间」两种显示模式；具体日期与时间呈现规则将在数据模型阶段确定。

## 初步方案

数据来源 → 采集 → 统一事件数据 → ICS 生成 → 稳定 HTTPS 订阅地址 → 日历客户端。

- 日历生成：已使用 Python 和 icalendar，固定依赖见 requirements.txt；采集器后续实现。
- 网站入口：主站 Netweb 已提供 Project 004 与前端订阅选择器；URL 尚为故意无效的占位链接。
- GitHub Actions：测试工作流已跑通，能构建并发布固定虚构数据；正式定时刷新和状态持久化尚未实现。
- 发布：固定虚构 ICS 已部署 GitHub Pages；自定义组合订阅仍需动态服务或预生成策略。
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

第一步设计见 [统一事件数据规范 v1](docs/event-model.md)；第二步见 [离线虚构样例](data/samples/README.md)，第三步已实现校验与 ICS 生成。第四步的测试发布工作流已成功执行，GitHub Pages 返回部署成功；[虚构测试订阅地址](https://southkite2023.github.io/yuashie-calendar/) 已按发布流程生成，**线上 HTTP 响应与实际客户端订阅仍需独立验证**。详细步骤见 [GitHub Pages 虚构订阅测试](docs/test-pages.md)，项目范围见 [实施路线](docs/roadmap.md)，本地命令见 [运行说明](docs/running.md)。

## 数据与维护原则

- 保存来源链接、来源标识与核验时间；区分官方确认和推测日期。
- 区分游戏服务器、地区、平台与动漫播出渠道，避免混用时间。
- 事件改期时保持稳定身份，避免重复订阅事件。
- 抓取失败时保留最后有效数据，并呈现更新时间。
- 不提交密钥、令牌、真实用户订阅信息或本地环境文件。
- 仓库尚未选定开源许可证；数据内容及相关名称、商标的权利归原权利人所有。
