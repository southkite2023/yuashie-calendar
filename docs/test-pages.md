# 第四步：公开虚构 ICS 测试（GitHub Pages）

> **仅供客户端兼容性测试**：这是 2030 年的虚构数据，不是任何游戏、动漫或新游的真实日程。正式组合订阅服务尚未上线。

## 发布代码与公开边界

[GitHub Actions 工作流](../.github/workflows/publish-test-pages.yml) 在 `main` 中相关文件变更或手动触发时：

1. 安装固定版本的 Python 开发依赖，运行 `pytest`。
2. 显式传入 `--allow-samples` 生成 12 个虚构 ICS。
3. 运行 `scripts/stage_sample_pages.py` 再次解析和校验 12 个 ICS，核对 22 个 VEVENT 的数量、虚构标题、`example.invalid` 来源、稳定 UID。
4. 只将 12 个 `.ics`、入口 `index.html`、`robots.txt` 和 `.nojekyll` 放入 Pages artifact 并部署。

**绝不将 `state.json`、`generations/`、完整的 `dist/sample-calendar` 或任何凭据发布。**

GitHub Actions 的每次运行都是新的工作目录；目前只有固定的虚构基础快照。真实改期/取消后发布需要持久化 generation 和 state.json 的可信存储及备份，不能以当前测试 workflow 代替生产同步机制。

## 当前部署状态（2026-10-08）

仓库所有者已在 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
[此工作流的第二次执行](https://github.com/southkite2023/yuashie-calendar/actions/runs/37714362645) 在 GitHub 上显示 **success**：
`pytest`、12 份 ICS 构建、22 个 VEVENT 校验、公开文件暂存、Pages 配置、artifact 上传及部署均成功。部署日志显示 Pages URL 为 `https://southkite2023.github.io/yuashie-calendar/`。

**已验证（2026-10-08）**：用户按订阅 URL 操作后提供了 Apple Calendar 桌面月视图截图；其中原神测试前瞻在 2030-01-25 20:00、版本在 01-30 11:00，角色/武器卡池两个跨日条带均截止 02-20 14:59。这证明 Apple Calendar 可显示本次 `span.ics` 样例事件，且用户反馈的订阅流程可用。截图仅作为人工验收记录，不上传个人日历截图至公开仓库。

**未验证项目**：当前自动化环境无法独立 GET `github.io` 链接，尚无法单独确认线上 HTTP 状态和 `Content-Type`。Apple Calendar 的后续自动刷新、改期和取消、Google Calendar 订阅均未测试。

后续可在 [Actions](https://github.com/southkite2023/yuashie-calendar/actions) 手动重新运行工作流。如果 Pages 出现 404，核对 [Pages 设置](https://github.com/southkite2023/yuashie-calendar/settings/pages) 的 Source 仍为 GitHub Actions，并检查部署日志。

Pages 项目地址（GitHub 已报告部署成功）：

- 测试说明：`https://southkite2023.github.io/yuashie-calendar/`
- 原神：`https://southkite2023.github.io/yuashie-calendar/calendar/v1/genshin/span.ics`
- 日本动漫：`https://southkite2023.github.io/yuashie-calendar/calendar/v1/anime/start.ics`
- 其余 10 个：在测试说明主页中获取。

所有样例位于 2030 年，并且 `SUMMARY` 以 `[虚构测试]` 开头。初版 **六类基础订阅 × 两种模式**；不支持任意条件组合，也不提供正式 `/v1/feed.ics?... ` API。主站 Project 004 的 `calendar.example.invalid` URL 仍然故意不可访问，不应切换为这里的固定文件链接冒充组合订阅。

## HTTP 与订阅验收

访问测试网址时核对：

- HTTPS 正常，`GET` 返回 200，响应体以 `BEGIN:VCALENDAR` 开头、包含 `VERSION:2.0`。
- `Content-Type` 最好为 `text/calendar`（可能带 `charset`），若 GitHub Pages 返回其他 MIME 类型，记录并在生产部署时通过可控服务器配置修正，**不要**仅以文件扩展名认定已满足。
- 仅有 12 个公开样例 ICS，没有 `state.json` 等内部状态。
- `UID`、`SEQUENCE` 在多次相同内容发布后保持稳定。

## 实机验证清单（需要用户操作）

**Apple Calendar**：已通过 Mac 桌面月视图确认基础显示；仍需验证 iPhone 及自动刷新。若重新测试，请在 iPhone / Mac 的日历设置中使用 **添加订阅日历**（不是一次性导入 ICS），粘贴上面的一个测试 URL。订阅成功后导航至 2030 年相应月份，观察是否出现 `[虚构测试]` 事件；记录设备系统版本、所用 URL、时区、显示模式与结果。订阅多个模式可能看到重复事件，测试时建议仅选一种。

**Google Calendar**：在网页版「其他日历 → + → 通过网址添加」填入同一 HTTPS 测试地址。Google 的刷新周期由 Google 控制，不能将「网页 GET 能下载」等同于「Google 已成功订阅」。记录是否导入、首次出现时间以及客户端是否更新。

**改期 / 取消 / 恢复**：当前工作流只有固定虚构基础快照，不能实际验证在线生命周期更新。须另建受控的持久化测试数据发布流程，并保持同一个 URL 和 UID，依序发布生命周期样例，再等待客户端刷新并检查 `SEQUENCE`。此项在完成真实客户端基础订阅后实施。

验收记录应写明 **实际结果**，未测试的项目保持未验证，不能根据离线 `pytest` 推定通过。

## 独立生命周期订阅测试（准备就绪后由用户操作）

另设两份 **与基础六类 Feed 完全隔离** 的订阅 URL（用于同 UID 改期、延期、取消、恢复）：

- `https://southkite2023.github.io/yuashie-calendar/calendar/v1/lifecycle-test/span.ics`
- `https://southkite2023.github.io/yuashie-calendar/calendar/v1/lifecycle-test/start.ics`

测试事件是虚构动漫单集 `anime-episode-2`，默认首播 `2030-01-12 01:30`（日本时间），且 `UID` 固定。**请只订阅其中一种模式**。此测试源内容未来会变更；之前已经订阅的原神 `genshin/span.ics` **不会受影响**。

### 控制阶段

由版本控制中的 [`config/lifecycle-stage.txt`](../config/lifecycle-stage.txt) 指定。仅在用户已确认收到上一阶段后，按以下严格顺序逐个修改并提交，由 GitHub Actions 自动重新部署同一 URL：

| stage | 预期变化 | SEQUENCE | 事件状态 |
| --- | --- | ---: | --- |
| `initial` | 2030-01-12 01:30 JST | 0 | CONFIRMED |
| `rescheduled` | 改为 2030-01-19 01:30 JST | 1 | CONFIRMED |
| `postponed-tbd` | 延期，时间待定，取消此前日期 | 2 | CANCELLED |
| `restored` | 恢复为 2030-01-26 01:30 JST | 3 | CONFIRMED |
| `cancelled` | 取消该次播出 | 4 | CANCELLED |
| `checked-only` | 来源再次核查，不改动事件定义 | 4 | CANCELLED |

工作流通过 `scripts/build_lifecycle_test.py` 在隔离的目录中从初始快照按序回放到当前阶段，以重建必要的历史，而不是上传私有 `state.json`。此方法只适用于有限、固定的公开虚构测试；真实数据生产系统仍需要可靠的持久化历史存储与备份。

**观测要求**：每次发布完成后，用日历客户端订阅刷新功能等待服务端拉取，记录同一 UID 是否移动日期或显示取消（部分客户端会隐藏已取消事件）。Apple/Google 对 URL 订阅有自主的刷新频率，可能需要较长时间；打开 `.ics` 文件/重新导入无法证明客户端的自动更新行为。未观察到刷新，不代表 ICS 已错误；保留测试阶段直至有明确结果。公开 GitHub Pages 不能强制客户端即时刷新。

