# CalendarEvent 统一事件规范 v1

状态：第一步设计基线。本文定义后续样例、校验与生成器的输入契约；尚未实现业务代码。实际 API 的可用性仍需单独验证。

## 1. 范围与结构

统一记录三类事件：游戏版本事件、动漫分集播出、新游戏发售。中间数据采用 UTF-8 JSON。顶层为 `schema_version: 1` 与 `events: CalendarEvent[]`；发布信息、抓取日志与原始响应独立保存，不混入事件。

事件中的 `game`、`anime`、`release` 扩展对象只能出现与类别相符的一个。未知可选值省略；下面明确允许为空的字段使用 `null`。不允许用空字符串代替未知日期。

| 字段 | 类型 / 必填 | 规则 |
| --- | --- | --- |
| id | string / 是 | 首次建档生成 UUID v4，持久化后不可更换；不从标题或日期生成 |
| category | enum / 是 | `game`、`anime`、`release` |
| event_type | enum / 是 | 见类型表，必须与 category 匹配 |
| title | string / 是 | 非空可读标题；不用于判定身份 |
| description | string / 否 | 补充说明，按纯文本处理 |
| status | enum / 是 | `tentative`、`confirmed`、`cancelled` |
| schedule_state | enum / 是 | `scheduled`、`tbd`；是否有可用开始时间，与 status 独立 |
| time_kind | enum / 是 | `datetime`、`date`、`unknown` |
| start | string 或 null / 是 | datetime 为带偏移的 RFC 3339 秒精度；date 为 YYYY-MM-DD；unknown 为 null |
| end | string 或 null / 是 | 与 start 同类型；非空时为排他结束边界且严格晚于 start |
| timezone | string / 是 | IANA 时区；指事件所属日历的时间语境，不是浏览者设备时区 |
| date_hint | string / 否 | 如“2027 年第二季度”；仅说明，不作为真实日期导出 |
| url | HTTPS URL / 是 | 用户可访问的事件详情或主要来源页面 |
| sources | object[] / 是 | 至少一项；格式见来源规则 |
| revision | integer / 是 | 初始 0；影响导出内容的变更递增 |
| created_at | UTC timestamp / 是 | 首次入库时间，固定 |
| updated_at | UTC timestamp / 是 | 最近一次语义修订时间，无变化时保持不变 |
| game / anime / release | object / 是 | 对应类别的扩展对象 |

`schedule_state=scheduled` 要求 start 非空且 time_kind 不为 unknown；`tbd` 要求 start/end 为 null、time_kind=unknown。曾发布事件的历史时间保留在持久化记录中，供取消与待定处理使用。

## 2. 类型与专属字段

| category | event_type | 含义 |
| --- | --- | --- |
| game | `livestream` | 前瞻直播开始时间；已知时可含结束时间 |
| game | `version_update` | 新版本计划开放时间，不表示维护开始时间或整个版本周期 |
| game | `banner` | 单个卡池的开放区间；同期角色池与武器池分别记录 |
| anime | `episode_airing` | 某个播出渠道的一集播出事件 |
| release | `game_release` | 某作品在某平台、地区的正式发售事件 |

- `game`：`game_id`、`server`、`version` 必填；game_id 为 `genshin`、`starrail`、`zzz`、`arknights`。server 使用持久化来源配置中的稳定标识，不能笼统用 UTC+8 代替服务器。banner 另需 `banner_id`，标识单个卡池实例；不能仅用上架角色名称作键。
- `anime`：`series_id`、`episode_id`、`episode_label`、`channel` 必填。作品标识使用带命名空间的 ID，例如 `anilist:123`；episode_id 可覆盖特别篇，episode_label 负责“第 1 集 / SP”等显示。初版一个作品只选择一个明确的播出渠道；不能把日本首播与国内平台上线合并。
- `release`：`game_id`、`platform`、`region`、`release_stage` 必填。game_id 使用带命名空间的稳定 ID；platform/region 使用配置表固定标识。初版 release_stage 固定 `full_release`；抢先体验与正式发售不能共用一个事件。

这些扩展标识为项目业务键。版本名、集数标签等更正时，通过人工确认或来源映射保留原 id。

## 3. 来源、去重与身份

每项 sources 包含 `provider`、`source_id`、`url`、`checked_at`、`authority`。authority 为 `official`、`wiki`、`aggregator`、`manual`；source_id 是来源内稳定的事件标识。缺少来源 ID 时人工分配并保存映射，不能每次抓取随机生成。checked_at 为 UTC 秒精度时间，每次成功核验可更新，但不单独触发 revision。

持久化身份映射以“provider + source_id + 业务范围”关联内部 UUID。业务范围包含服务器、单个卡池实例，或作品 / 集 / 渠道，或作品 / 平台 / 地区 / 发售阶段。一个来源条目拆成多个事件时必须有独立范围。

更换数据源时先关联已有事件再添加来源映射。禁止仅按标题、日期或来源 URL 自动合并。来源冲突按同服务器、同平台、同渠道的官方信息优先，无法判定时保留最后有效记录并标记人工核验，不把冲突结果直接发布。

ICS UID 固定为 `<id>@calendar.yuashie.cn`。此后即使标题、日期、来源改变也不变；域名部分是身份命名空间，不要求该子域名已部署。不同显示模式保留同一 UID；建议用户只订阅同一内容的一种模式，跨日历重复显示由客户端决定。

## 4. 日期与时区

- datetime 输入必须携带 `Z` 或数字时区偏移；偏移须与 timezone 在该日期一致。拒绝无时区时间及含糊夏令时本地时间，待来源核实后再入库。
- 中间层保留带偏移的时间；ICS 精确时间统一转 UTC。全天日期不经 UTC 转换。
- 游戏按所选服务器的真实时间规则配置。动漫日本首播通常用 `Asia/Tokyo`，不能直接当成北京时间；发售以对应地区来源的日期语境为准。
- 日期已知、钟点未知：使用 date，不伪造 00:00 精确时间。只知月份、季度或完全待定：使用 unknown + date_hint，不发布虚构日期。
- 动漫“周五 25:30”转换为该周六 01:30，再按时区处理；原始播出表达可保存在 description 中。
- 所有区间采用 `[start, end)`。来源标注“截至 10 月 7 日（含当天）”时，date 的 end 存 10 月 8 日。精确到秒的终点不随意加一天或一秒。
- end 未知则为 null，不假定下个版本日期、固定直播长度或动画集长。后续补齐结束时间属于修订。

## 5. 两种订阅显示模式

原始事件只存一份，模式在导出时应用，不改写 start/end。

| 输入 | `start`：仅开始日 | `span`：完整持续期间 |
| --- | --- | --- |
| date，有结束日期 | 开始日期的一天 | 原始日期区间 |
| date，无结束日期 | 开始日期的一天 | 开始日期的一天，说明结束未知 |
| datetime，有结束时间 | 按事件 timezone 取开始日期，显示全天一天；描述保留原始时间范围 | 保留原始精确起止时间 |
| datetime，无结束时间 | 按事件 timezone 取开始日期，显示全天一天；描述保留已知开始时间 | 导出精确开始时间，不设置 DTEND；说明结束未知 |
| unknown | 不创建新的日历事件 | 不创建新的日历事件 |

“仅开始日”明确是全天标记；需要直播、动漫准确钟点时使用 span。跨度不明的事件不能假装显示整个持续期间。

六类基础订阅源分别为 genshin、starrail、zzz、arknights、anime、game-releases；每类两种模式，共 12 个文件。计划路径为 `/calendar/v1/{feed}/{start|span}.ics`，这只是路径契约，尚不是可访问 URL。初版游戏源使用中国大陆服范围，动漫采用日本首播；其他服务器、播出渠道与任意组合地址留待来源验证及前端阶段设计。

## 6. 修订、取消和抓取失败

初次发布 revision=0。标题、说明、时间、状态、用户可见来源或业务字段变化时递增，并更新 updated_at；只重新抓取、重新构建或来源核验时间变化不递增。

取消保留 UID，导出 `CANCELLED` 状态，不直接从文件删除。未发布过且没有时间的取消事件只留内部记录。改期仍有明确日期时更新原事件。

已发布后改成待定：内部置 tbd，并在每种 feed 的发布历史中保留最近一次导出时间，以同一 UID 输出“延期，时间待定”的取消记录；日期恢复后同 UID 恢复对应状态，并再次递增 revision。标题不反复累加前缀。初版不清理已发布事件与取消记录，待客户端验证后再制定保留窗口。

事件从来源页面消失不等于取消。来源超时、解析失败或异常空结果不能覆盖现有 feed；保留最后有效产物，单独记录失败与数据更新时间。持久化身份、revision 和发布历史是后续实现的必要条件，不能依赖每次运行的内存。

## 7. ICS 映射与生成约束

| 数据 / 项目决策 | ICS 输出 |
| --- | --- |
| id | UID，按上面的固定规则 |
| title / description / url | SUMMARY / DESCRIPTION / URL |
| 按模式转换的 start/end | DTSTART / DTEND；结束未知的精确时间事件省略 DTEND |
| status | CONFIRMED / TENTATIVE / CANCELLED |
| revision | SEQUENCE |
| created_at / updated_at | CREATED / LAST-MODIFIED；DTSTAMP 使用该导出表示的修订时间，普通重建不变 |
| 提醒偏好 | 初版不主动添加 VALARM；TRANSP=TRANSPARENT |

容器使用 VERSION:2.0 和固定 PRODID，不添加会议邀请 METHOD。序列化使用成熟库处理 UTF-8、CRLF、文本转义和长行折叠；DATE 的 DTEND 为排他日期。精确时间用 UTC 输出，初版不输出浮动时间。动漫每集独立 VEVENT，不用 RRULE 推测未来集数。

标准依据：[RFC 5545](https://www.rfc-editor.org/rfc/rfc5545)，重点为 3.1（序列化）、3.6.1（VEVENT）、3.8.2（时间）、3.8.4.7（UID）、3.8.7（修订）。以上订阅模式、取消保留及发布历史是项目策略，客户端是否及时刷新仍需实际订阅验证。

## 8. 下一步样例与验收清单

第二步再编写独立的虚构数据文件；本步只定义应覆盖的情形：

1. 前瞻直播精确时间与结束未知；版本开放时间与卡池区间。
2. 两集动漫，以及 25:30、延播到待定、恢复日期。
3. 仅日期的发售事件与仅季度的待定发售。
4. 跨月区间、含末日日期转换、上海 / 东京时间换算。
5. 相同事件改期仍同 UID，语义变化 revision 增加，重复抓取不增加。
6. 同期不同卡池、同作品不同平台独立身份；跨源重复条目映射为一个事件。
7. 两种模式不会改动原始记录；取消保留，来源失败保留最后有效数据。
8. 非法时间、end 不晚于 start、缺少来源、类别与扩展不符时拒绝发布并给出明确错误。

完成样例与生成器后，再实际验证客户端订阅、更新和取消行为。当前目录结构继续沿用 README，暂不添加运行依赖或自动部署工作流。
