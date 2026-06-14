# Dashboard 迁移与上游自动同步计划

## Summary

- 目标：把 `Alas-with-Dashboard` 的完整 dashboard 功能迁移到当前 fork，并设计一套“无冲突时自动从 upstream 合并到 `master`”的机制。
- 成功标准：
  - 当前 fork 的 WebUI 中出现可折叠的 dashboard 面板，显示完整资源项，而不是只保留日志区。
  - 资源采集链路能在现有运行流程中把 OCR/状态结果写入配置并被前端展示。
  - dashboard 改动按“配置层 / 采集层 / WebUI 层 / 自动同步层”分层提交，尽量减少未来与 upstream 的冲突面。
  - 仓库新增 GitHub Action：定时或手动从 `upstream/master` 同步；无冲突则直接更新 `master`，有冲突则失败退出，不尝试自动解决。

## Current State Analysis

- 当前仓库是最新上游结构的 fork，工作区干净，默认分支为 `master`。
- 当前仓库没有 dashboard 相关实现：
  - `config/template.json` 顶层没有 `Dashboard` 配置段。
  - `module/config/config_updater.py` 只合并 `task.yaml`，没有 `dashboard.yaml` 扩展点。
  - `module/webui/app.py` 当前 overview 页面只有日志切换，没有 dashboard 区域或折叠按钮。
  - `module/webui/widgets.py` 的 `RichLog` 只有滚动状态，没有 dashboard 状态。
  - 全仓库不存在 `LogRes`、`DashboardON`、`display_dashboard` 等标识。
- 当前仓库配置参数目录完整，可承载迁移：
  - `module/config/argument/args.json`
  - `module/config/argument/argument.yaml`
  - `module/config/argument/gui.yaml`
  - `module/config/argument/override.yaml`
  - `module/config/argument/task.yaml`
- 当前仓库已有 `.github/` 目录，但没有 `.github/workflows/`，说明自动同步需要新建 workflow。
- 已确认 `Alas-with-Dashboard` 的 dashboard 功能核心不是单一前端页面，而是以下三层协同：
  - 配置模板与参数组：`config/template.json`、`module/config/argument/dashboard.yaml`、`module/config/config_updater.py`
  - 资源记录器：`module/log_res/log_res.py`
  - WebUI 渲染：`module/webui/app.py`、`module/webui/widgets.py`、`assets/gui/css/*.css`
- 已确认 `dashboard/master` 相对当前上游共同基线的 dashboard 语义改动约为 `42 files changed, 2016 insertions, 235 deletions`。这说明应“迁移 dashboard 语义改动”，而不是整体搬运该分支的所有历史与资源差异。
- 已做隔离试合并：`dashboard/master` 合并当前 `upstream/master` 时，明确文本冲突只有 `module/coalition/coalition.py`。这说明 dashboard 功能仍具备可迁移性，但要避免照搬旧分支的整树 merge。

## Assumptions & Decisions

- 迁移范围：按 `Alas-with-Dashboard` 的完整 dashboard 功能迁移，不做精简版。
- 同步方式：使用 GitHub Action 自动同步。
- 落地策略：当 upstream 无冲突时，Action 直接更新 fork 的 `master`；不走 PR 审批流。
- 冲突策略：Action 只在“Git 合并成功且验证通过”时推送；一旦出现 merge conflict 或验证失败，直接退出，不尝试自动修冲突。
- 维护策略：dashboard 迁移不采用“把旧仓库整分支 merge 进来”，而是以当前最新 `master` 为基础做语义移植，并把 dashboard 改动压缩为少量、边界清晰的提交。
- 冲突控制原则：
  - 不迁移 `Alas-with-Dashboard` 中与 dashboard 无关的历史修改、资产替换、删除操作。
  - 不保留旧分支里仅为当时上游适配而存在的杂项改动。
  - 对生成型配置文件，优先修改“源定义 + 生成产物”，避免后续每次上游更新都在大文件内产生无意义漂移。

## Proposed Changes

### 1. 建立 dashboard 配置层

- 新增 `module/log_res/log_res.py`
  - 引入 `LogRes` 资源记录器。
  - 写入目标统一为 `Dashboard.<Resource>.Value/Limit/Total/Record`。
  - 只写入 `config.modified`，由调用方在适当时机统一 `update()`，避免频繁磁盘写入。
- 修改 `config/template.json`
  - 新增顶层 `Dashboard` 区域。
  - 初始化以下资源项及颜色/时间字段：
    - `Oil`
    - `Coin`
    - `Gem`
    - `Pt`
    - `Cube`
    - `ActionPoint`
    - `YellowCoin`
    - `PurpleCoin`
    - `Core`
    - `Medal`
    - `Merit`
    - `GuildCoin`
  - 保留与 `Alas-with-Dashboard` 相同的数据结构：`Value`、可选 `Limit/Total`、`Color`、`Record`。
- 新增 `module/config/argument/dashboard.yaml`
  - 定义 dashboard 展示顺序与资源组列表。
- 修改 `module/config/config_updater.py`
  - 新增 `dashboard` cached property，读取 `dashboard.yaml`。
  - 在 `args` 构建流程中，把 `dashboard.yaml` 与现有 `task.yaml` 合并，使 dashboard 组可进入统一参数树。
- 修改 `module/config/argument/argument.yaml`
  - 新增 dashboard 资源组所需字段定义，确保 `Dashboard.*` 结构有合法 schema。
- 修改 `module/config/argument/gui.yaml`
  - 新增 `Gui.Button.DashboardON`
  - 新增 `Gui.Button.DashboardOFF`
  - 新增 `Gui.Overview.Dashboard`
  - 新增 dashboard 各资源项的 `Gui.Overview.*` 显示名称。
- 修改 `module/config/argument/override.yaml`
  - 仅在实际需要时补齐 dashboard 相关默认覆盖项；如果当前结构无需额外 override，则保持最小改动。
- 修改 `module/config/argument/args.json`
  - 作为仓库内已提交的生成产物，同步更新以匹配新的 `dashboard.yaml` 与参数定义。
- 修改 `module/config/i18n/en-US.json`
- 修改 `module/config/i18n/ja-JP.json`
- 修改 `module/config/i18n/zh-CN.json`
- 修改 `module/config/i18n/zh-TW.json`
  - 为 dashboard 开关、标题、资源名补充翻译。

### 2. 接入资源采集层

- 修改 `module/campaign/campaign_status.py`
  - 在 `get_event_pt()`、`get_coin()`、`get_oil()` 中接入 `LogRes(self.config)`。
  - `Coin` 和 `Oil` 记录 `Value + Limit`。
  - `Pt` 记录 `Value`，更新时间为识别时刻。
- 修改 `module/shop/shop_status.py`
  - 记录 `Coin`、`Gem`、`Medal`、`Merit`、`GuildCoin`、`Core`。
  - 保持现有 OCR 行为，只增加 dashboard 写入。
- 修改 `module/gacha/gacha_reward.py`
  - 记录 `Cube`，并在建造资源计算后刷新 dashboard。
- 修改 `module/os_handler/os_status.py`
  - 记录 `YellowCoin`、`PurpleCoin`。
- 修改 `module/os_handler/action_point.py`
  - 记录 `ActionPoint` 的 `Value + Total`。
  - 维持当前上游 `Oil` 语义，不让 dashboard 写入破坏业务逻辑。
- 修改 `module/raid/raid.py`
  - 在已有 PT 识别完成后写入 dashboard。
- 修改 `module/coalition/coalition.py`
  - 以当前 upstream 版本为主，保留最新的 `_coalition_has_oil_icon`、`page_campaign_menu` 等逻辑。
  - 只把 dashboard 所需的 `LogRes(self.config).Pt = pt` 写回逻辑嵌入当前函数，不回退任何上游新行为。
  - 这是当前已知最需要人工处理的冲突点，应单独提交，方便未来定位。
- 修改 `module/campaign/run.py`
  - 仅在 `config.modified` 非空时统一 `update()`，保留 dashboard 分支中“减少频繁写配置”的思路。
  - 保证 campaign 周期中 dashboard 有刷新，但不引入额外频繁落盘。

### 3. 接入 WebUI 展示层

- 修改 `module/webui/widgets.py`
  - 给 `RichLog` 增加以下状态：
    - `display_dashboard`
    - `first_display`
    - `last_display_time`
    - `dashboard_arg_group`
  - 增加 `set_dashboard_display()`。
- 修改 `module/webui/app.py`
  - 在 overview 页面增加 dashboard 区域与按钮位：
    - `dashboard_btn`
    - `dashboard`
  - 增加 dashboard 开关按钮：
    - `Gui.Button.DashboardON`
    - `Gui.Button.DashboardOFF`
  - 在页面初始化时将 `LogRes(self.alas_config).groups` 注入 `self._log.dashboard_arg_group`。
  - 新增以下方法并接入定时任务：
    - `set_dashboard_display()`
    - `_update_dashboard()`
    - `alas_update_dashboard()`
  - 保持当前上游 overview 的现有布局与任务面板逻辑，只在日志区域旁扩展 dashboard，不重写整体页面。
  - 保留 `Maa` 分支的兼容判断，避免 dashboard 误插入不支持的 UI 流程。
- 修改 `assets/gui/css/alas.css`
- 修改 `assets/gui/css/alas-mobile.css`
- 修改 `assets/gui/css/dark-alas.css`
- 修改 `assets/gui/css/light-alas.css`
  - 加入 dashboard 容器和数值字体样式。
  - 仅迁移 dashboard 相关样式块，不夹带无关视觉改动。
  - 保持当前上游现有 class/scope 命名，不额外重构 CSS 架构。
- 评估 `assets/gui/css/alas-pc.css`
  - 只有当当前布局确实需要额外 PC 样式时再改；否则保持不动，减小冲突面。

### 4. 控制迁移边界，避免引入旧分支杂质

- 明确不迁移以下类型改动：
  - `Alas-with-Dashboard` 中与 dashboard 无关的资源文件新增/删除/替换。
  - 旧分支对 campaign/event/asset 的历史性兼容补丁。
  - 与 dashboard 无关的 OCR 素材、地图、活动文件差异。
  - 旧分支里为早期上游结构服务的 merge 修补。
- dashboard 迁移以“按文件摘取语义 hunk”为准，不做全文件覆盖的目标文件：
  - `module/coalition/coalition.py`
  - `module/webui/app.py`
  - `module/config/config_updater.py`
  - `module/campaign/run.py`
- 可采用整文件移植后再按当前上游结构手动回调的目标文件：
  - `module/log_res/log_res.py`
  - `module/config/argument/dashboard.yaml`

### 5. 设计后续自动同步机制

- 新增 `.github/workflows/upstream-sync.yml`
  - 触发方式：
    - `workflow_dispatch`
    - `schedule`，建议每日一次或每 6 小时一次
  - 权限：
    - `contents: write`
  - 核心流程：
    1. checkout 当前仓库 `master`
    2. 配置 Git 用户
    3. 确认 `upstream` remote 指向 `https://github.com/LmeSzinc/AzurLaneAutoScript.git`
    4. `git fetch upstream --prune`
    5. `git merge --no-ff --no-edit upstream/master`
    6. 如果 merge conflict，直接失败退出
    7. 运行最小验证
    8. 仅在验证通过时 `git push origin HEAD:master`
- 最小验证步骤采用低成本但能发现结构性错误的组合：
  - `python -m compileall` 针对本次 dashboard 涉及目录
  - 可选：如果仓库已有现成非交互、自洽的配置生成/校验命令，则一并运行
- workflow 不自动修冲突，不自动改文件，不自动 rebase。
- workflow 只处理“上游无冲突同步”，不处理 dashboard 迁移期的首次大改。

### 6. 通过提交边界降低未来冲突

- 实施时按以下提交顺序组织：
  1. `feat(dashboard): add dashboard config schema and resource logger`
  2. `feat(dashboard): record campaign/shop/gacha/opsi resources`
  3. `feat(dashboard): add webui dashboard panel and styles`
  4. `ci(sync): add upstream auto-merge workflow`
- 这样做的目的：
  - 未来如果某层与 upstream 冲突，可以只回看对应提交。
  - 自动 merge 失败时，最容易定位冲突属于“配置层 / 采集层 / WebUI 层 / CI 层”的哪一类。

## Implementation Steps

1. 以当前 `master` 新建工作分支。
2. 先迁移配置层与 `LogRes`，并保证配置可读写。
3. 迁移资源采集埋点，优先处理 `campaign_status.py`、`shop_status.py`、`gacha_reward.py`、`os_status.py`、`action_point.py`。
4. 单独处理 `module/coalition/coalition.py`，按当前上游结构手工嵌入 dashboard 记录逻辑。
5. 迁移 WebUI 区域、dashboard 开关、定时刷新和样式。
6. 更新 `args.json` 与 i18n 文件，保证页面与配置结构闭合。
7. 做一次本地验证，确认无语法错误、页面结构存在、dashboard 值能随配置刷新。
8. 新增 GitHub Action 自动同步 workflow。
9. 再做一轮验证，确认 workflow 脚本在无冲突场景下可运行。

## Verification Steps

- 静态检查：
  - 对以下目录执行 `python -m compileall`：
    - `module/log_res`
    - `module/config`
    - `module/webui`
    - `module/campaign`
    - `module/shop`
    - `module/gacha`
    - `module/os_handler`
    - `module/raid`
    - `module/coalition`
- 配置检查：
  - 确认 `config/template.json` 中存在 `Dashboard` 顶层。
  - 确认 `module/config/argument/args.json` 能解析出 `Dashboard` 相关项。
  - 确认 `module/config/i18n/zh-CN.json` 等包含 `DashboardON/DashboardOFF` 与 `Gui.Overview.*`。
- UI 检查：
  - 启动现有 WebUI。
  - 确认日志栏出现 dashboard 折叠/展开按钮。
  - 确认收起时显示核心 4 项：`Oil`、`Coin`、`Gem`、`Pt`。
  - 确认展开时显示完整 dashboard 资源列表。
  - 确认资源更新时间能按 `Record` 渲染为相对时间。
- 功能检查：
  - 运行至少一条会更新 `Oil/Coin/Pt` 的流程，确认数值写入 `config.modified` 并展示到 dashboard。
  - 进入 shop/gacha/opsi 场景，确认对应资源项刷新。
- 同步检查：
  - 手动触发 `.github/workflows/upstream-sync.yml` 的 dry-run 等价流程。
  - 模拟无冲突 upstream 更新，确认 workflow 能 merge 并 push。
  - 模拟冲突场景时，确认 workflow 失败退出且不推送半成品。

## Risks & Mitigations

- 风险：`module/webui/app.py` 与 upstream 后续演进频繁，未来仍可能产生冲突。
  - 缓解：只插入 dashboard 相关 scope/按钮/任务，不改 overview 其他逻辑。
- 风险：`module/coalition/coalition.py` 已是已知冲突热点。
  - 缓解：单独提交并在代码中仅保留最小 `LogRes` 写入逻辑。
- 风险：`args.json` 为已提交产物，未来可能与上游生成逻辑漂移。
  - 缓解：始终保持源定义与产物同步提交，必要时补充生成说明。
- 风险：GitHub Action 直接推 `master` 需要仓库权限允许 `GITHUB_TOKEN` 写入默认分支。
  - 缓解：实施时检查仓库 Actions 权限；若 fork 权限策略不允许，再退化为同 workflow 自动建分支/PR。
