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

## GitHub 仓库所有者需要完成的设置

1. 打开 [Repository Settings → Pages](https://github.com/southkite2023/yuashie-calendar/settings/pages)。
2. 在 **Build and deployment → Source** 选择 **GitHub Actions** 并保存。暂时不需要自定义域名、DNS 或阿里云服务器。
3. 到 [Actions → Publish fictional ICS test feeds](https://github.com/southkite2023/yuashie-calendar/actions) 查看最新执行；必要时在对应 workflow 页面手动点击 **Run workflow**。若部署受 `github-pages` Environment 审批限制，请按页面提示批准。
4. 工作流绿色成功后，先检查网页和 ICS；如果 Pages 仍返回 404，核对 Pages Source 和工作流部署步骤，不能宣称已经上线。

Pages 项目地址（**只有发布成功后才有效**）：

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

**Apple Calendar**：在 iPhone / Mac 的日历设置中使用 **添加订阅日历**（不是一次性导入 ICS），粘贴上面的一个测试 URL。订阅成功后导航至 2030 年相应月份，观察是否出现 `[虚构测试]` 事件；记录设备系统版本、所用 URL、时区、显示模式与结果。订阅多个模式可能看到重复事件，测试时建议仅选一种。

**Google Calendar**：在网页版「其他日历 → + → 通过网址添加」填入同一 HTTPS 测试地址。Google 的刷新周期由 Google 控制，不能将「网页 GET 能下载」等同于「Google 已成功订阅」。记录是否导入、首次出现时间以及客户端是否更新。

**改期 / 取消 / 恢复**：当前工作流只有固定虚构基础快照，不能实际验证在线生命周期更新。须另建受控的持久化测试数据发布流程，并保持同一个 URL 和 UID，依序发布生命周期样例，再等待客户端刷新并检查 `SEQUENCE`。此项在完成真实客户端基础订阅后实施。

验收记录应写明 **实际结果**，未测试的项目保持未验证，不能根据离线 `pytest` 推定通过。
