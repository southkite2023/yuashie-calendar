# 离线虚构样例（第二步）

**所有时间、版本、作品和来源均为虚构测试数据，不是实际更新排期，不可用于正式订阅。** 使用 2030 年日期、`sample-*` 标识和 `example.invalid` 地址，禁止抓取这些地址。UUID 已一次生成并固定；未来不要重新生成已有样例的 ID。

这些文件按 [事件规范 v1](../../docs/event-model.md) 编写。本目录只保存数据和预期结果；第三步生成器已在 src/yuashie_calendar 实现，生成命令见 [运行说明](../../docs/running.md)。不包含真实来源采集器。

| 文件 | 用途 |
| --- | --- |
| events.json | 唯一正常输入包，schema_version=1，含 12 个事件 |
| expected-projections.json | 两种显示模式的手工预期：UID、状态、SEQUENCE、起止字段及数量 |
| lifecycle.json | 同一动漫集的 6 个有序快照：首次发布、改期、待定、恢复、取消、再次核验 |
| invalid-events.json | 7 个独立非法输入及拒绝原因，不得放进正式事件包 |
| source-scenarios.json | 跨源去重、范围区分、来源冲突、抓取失败，以及原始时间转换案例 |

除 events.json 外的文件属于测试场景格式，`fixture_version` 不属于生产 CalendarEvent。

## 覆盖范围

- 原神：前瞻、版本开放、同时开放但身份不同的角色与武器卡池。
- 星穹铁道：版本开放；绝区零：跨午夜前瞻；明日方舟：仅日期、跨月且包含末日的卡池。
- 动漫：两集日本首播，周五 25:30 转为周六 01:30，UTC 日期可能是前一天。
- 发售：同一虚构作品的 PC / PS5 事件，以及仅知道季度的另一作品。
- sample-cn、sample-jp-first 等是样例专用范围，不能直接当作已核实的生产服务器 / 渠道配置。

## 预期结果

events.json 有 12 项，其中日期待定的新游不导出；每种模式 11 项。六个 feed、每种两份，未来应生成 12 个 ICS 文件，共 22 个 VEVENT 表示（不代表 22 个独立业务事件）。

| feed | 每种模式事件数 |
| --- | ---: |
| genshin | 4 |
| starrail | 1 |
| zzz | 1 |
| arknights | 1 |
| anime | 2 |
| game-releases | 2 |

expected-projections 中 dtend=null 表示省略 DTEND，不能写空属性。DATE 值不带时区；DATE-TIME 预期为 UTC。每次导出都必须保持原始输入不变。

lifecycle 必须从头按顺序运行，每步保留上一份发布历史；待定快照使用上次发布的时间输出取消标记，恢复后保留 UID。最后一次仅更新 checked_at，SEQUENCE、LAST-MODIFIED 和 DTSTAMP 都不变。所有生命周期源核验时间都设置为相应快照时间。

## 本步核验与后续边界

已检查 JSON 解析、字段与扩展、UUID 唯一性、时区偏移、时间先后关系、预期日期与 UTC 换算、各 feed 数量、生命周期 UID 和修订规则；7 个非法样例均符合各自预设的错误原因。

第三步已用这些固定预期验证生成器，并通过独立日历解析器核验序列化。真实客户端订阅、刷新、取消仍在之后验证。
