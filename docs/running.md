# 第三步：离线校验与 ICS 生成

当前支持 Python 3.11+、macOS / Linux（包括之后可用的 Linux CI）。输出事务使用 POSIX 文件锁与符号链接，因此本版本不支持 Windows 原生命令行。尚未部署网站或接入真实数据源。

## 安装与运行

在仓库根目录执行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q

# 只校验，不写文件
PYTHONPATH=src .venv/bin/python -m yuashie_calendar \
  --input data/samples/events.json --validate-only

# 显式允许虚构样例，在独立输出目录生成日历
PYTHONPATH=src .venv/bin/python -m yuashie_calendar \
  --input data/samples/events.json \
  --output dist/sample-calendar --allow-samples
```

仅运行生成器可安装 requirements.txt。运行与开发依赖分别固定版本；本次核验环境为 Python 3.14、icalendar 7.3.0，其他受支持 Python 版本尚未逐一实测。独立解析器 vobject 仅用于测试，不进入运行依赖。

## 产物

`dist/sample-calendar/current/calendar/v1/` 下有六个目录：genshin、starrail、zzz、arknights、anime、game-releases。每个包含 `start.ics` 和 `span.ics`，总计 12 份。

全部排期均为虚构测试数据；尚无真实可订阅 URL。start 是按事件时区取开始日期的全天标记；span 保留精确时间或完整日期区间。不要把样例用于正式订阅。

## 状态与失败处理

- 输出目录 `generations/` 保存完整文件集及 state.json；`current` 是指向最近一次成功生成的链接。先写完所有文件和状态，再原子替换链接。
- state.json 保存原始事件、修订号和每种模式最后发布的时间，支持进程退出后继续处理改期、待定、恢复和取消。
- 若配置 Web 服务，未来只应暴露 `current/calendar/`，不公开整个输出目录或 state.json。部署与 HTTP 缓存仍属下一步。
- 保留整个输出目录作为发布历史；不要单独复制 ICS 后丢弃状态。若历史损坏，程序报错，不自动重建身份。恢复应使用可信备份。
- 非法输入、重复 ID、来源身份冲突、修订回退、意外空输入以及切换前写入失败，都不会替换原 current。失败返回非零退出码。
- 同一输出目录有进程锁，第二个同时运行的写入者立即失败。不要使用不保证 POSIX 链接替换语义的网络文件系统。
- 完全相同输入可复用原 generation；只更新 checked_at 会更新内部状态，但 ICS 字节保持不变。
- 未出现在本次输入中的历史事件保留，不能把来源缺失当作取消；取消必须使用原 ID 显式提交。
- 新事件必须从 revision=0 开始；已有事件内容变化时需更高 revision 和更晚 updated_at。调用方负责提供稳定 ID 和明确修订，不会根据标题自动猜测事件身份。
- 旧 generations 不自动删除，暂不提供清理命令；后续部署需要制定备份和空间管理策略。原子切换保证应用层构建失败不替换旧版本，不等同于掉电持久性保证。

## 已验证与未验证

39 项自动测试覆盖固定样例的 22 组字段预期、生命周期快照、非法输入、空输入、来源身份映射、修订一致性、中文转义与长行折叠、独立解析、失败保留、并发锁和跨进程状态恢复。

测试使用 icalendar 读取字段，并通过另一套解析器 vobject 交叉解析生成文件；这不替代 Apple Calendar / Google Calendar 的真实订阅测试。尚未实现爬虫、来源冲突裁决、原始时间文字解析、网站筛选或自动部署。

序列化由 [icalendar 官方库](https://icalendar.readthedocs.io/en/latest/how-to/usage.html) 完成；业务语义以 [本项目事件规范](event-model.md) 为准。
