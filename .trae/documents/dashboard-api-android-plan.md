# Dashboard API 与安卓小部件适配实施计划

## Summary
- 在现有 `Dashboard` 资源采集能力基础上，新增一个独立手动启动的 REST API 服务，用于接收脚本推送的数据、支持手机主动查询、支持多用户令牌、并为后续安卓图表与桌面小部件提供稳定的数据契约。
- 脚本侧复用现有 `LogRes` 作为唯一资源变更出口，在不改动现有 OCR/采集调用点语义的前提下，把资源快照异步推送到 API；时间戳统一由脚本端提供，格式为 Unix 毫秒时间戳。
- WebUI 侧通过现有配置生成链路，把 `Dashboard设置` 挂到 `Alas` 树下，按实例保存 API 地址和令牌；另外补充一份面向后续安卓端开发的详细 API 文档与项目背景说明。

## Current State Analysis

### 已有 Dashboard 数据流
- `module/log_res/log_res.py` 已经是 Dashboard 资源写入的中心入口；当前职责是把 `Dashboard.*` 资源值与 `Record` 时间写入 `config.modified`，时间来源是脚本本地 `datetime.now()`。
- 多个资源采集点已经通过 `LogRes(self.config).Xxx = ...` 写入资源，例如 `module/campaign/campaign_status.py`、`module/shop/shop_status.py`、`module/gacha/gacha_reward.py`、`module/os_handler/action_point.py`、`module/os_handler/os_status.py`、`module/raid/raid.py`、`module/coalition/coalition.py`。
- `module/webui/app.py` 的 overview 页面通过读取 `Dashboard.*` 配置展示资源面板，说明当前仓库已经存在“脚本采集 -> 配置持久化 -> WebUI 展示”的完整本地数据链。

### 已有配置与左侧栏生成链路
- `module/config/argument/argument.yaml` 定义参数组结构，`module/config/argument/task.yaml` 定义 `Alas` 树中的任务页与参数组绑定。
- `module/config/config_updater.py` 会基于 `argument.yaml`、`task.yaml`、`gui.yaml` 生成 `module/config/argument/args.json`、`module/config/argument/menu.json`、`module/config/config_generated.py` 和各语言 i18n。
- `module/webui/app.py` 的 `alas_set_menu()` 与 `alas_set_group()` 读取 `menu.json` / `args.json` 自动渲染左侧菜单与设置表单，因此新增一个 `Dashboard设置` 页面不需要重写整套 UI，只要正确接入配置生成链路即可。

### 已有服务与依赖条件
- 仓库已经依赖 `starlette`、`uvicorn`、`pydantic`，并且有 `module/webui/fastapi.py` 这类现成 ASGI/uvicorn 启动封装，适合复用同类技术栈实现独立 API。
- 当前依赖中没有 MySQL/ORM 相关库；若要同时支持 SQLite 与 MySQL，需要补充数据库访问依赖，并同步考虑 `requirements-in.txt`、`requirements.txt`、`deploy/headless/requirements.txt`、`deploy/docker/requirements.txt`、`deploy/AidLux/0.92/requirements.txt`。
- `doc/Readme.md` 目前只是 Wiki 跳转说明，因此新增面向安卓端开发的文档放在 `doc/` 目录不会与现有文档结构冲突。

## Assumptions & Decisions
- API 服务为独立进程，采用单独命令手动启动，不嵌入现有 WebUI 进程。
- API 技术栈优先复用现有依赖：以 `Starlette + Uvicorn + Pydantic` 为主，不引入新 Web 框架。
- 数据库层采用统一 ORM/方言方案来同时支持 SQLite 与 MySQL；建议实施时使用 `SQLAlchemy 1.4.x` + `PyMySQL`，避免分别维护两套 SQL 分支。
- 多用户模型采用“管理员 API 管理用户令牌”的方案：
  - API 服务启动配置中提供一个 bootstrap admin token。
  - 管理员通过 REST API 创建/禁用用户、轮换令牌。
  - 普通脚本与手机查询只使用用户令牌。
- 脚本侧 API 地址与令牌按 Alas 实例独立保存，不做全局共享。
- 历史数据策略为“每次推送都入库”，用于后续图表查询；同时维护一份最新快照表，专供手机首页/桌面小部件轻量读取。
- 脚本推送时间戳采用 Unix 毫秒时间戳，来源固定为脚本侧；API 服务不得自行重写业务记录时间，只能额外记录服务端接收时间。
- 小部件适配范围限定为“提供专用轻量查询接口与文档”，不在本仓库内开发安卓代码。

## Proposed Changes

### 1. 新增独立 API 服务

#### 新文件
- `module/dashboard_api/__init__.py`
  - 建立独立包，承载 API 服务实现。
- `module/dashboard_api/__main__.py`
  - 提供独立启动入口，命令格式定为：
    - `python -m module.dashboard_api --config ./config/dashboard_api.yaml`
  - 使用 `argparse` 解析 `--config`、`--host`、`--port` 等参数。
- `module/dashboard_api/app.py`
  - 构建 `Starlette` 应用与路由注册。
  - 路由分为公共、用户、管理员三类。
- `module/dashboard_api/config.py`
  - 读取独立 API 配置文件，例如 `config/dashboard_api.yaml`。
  - 配置项至少包含：监听地址、端口、数据库 URL、admin token、日志级别、可选 CORS 设置。
- `module/dashboard_api/auth.py`
  - 解析 `Authorization: Bearer <token>`。
  - 区分管理员令牌与普通用户令牌。
  - 普通用户令牌在数据库中仅保存哈希值，响应里只在创建/轮换时返回一次明文。
- `module/dashboard_api/models.py`
  - 定义 API 请求/响应数据模型。
  - 至少覆盖：admin user create/update/list、push payload、latest snapshot、history item、widget overview。
- `module/dashboard_api/db.py`
  - 初始化 engine / session / metadata。
  - 统一处理 SQLite 与 MySQL URL。
- `module/dashboard_api/repository.py`
  - 封装数据库读写逻辑，避免路由层直接拼 ORM 操作。
- `module/dashboard_api/service.py`
  - 处理“推送写历史 + 更新最新快照 + 查询历史 + 组装 widget 概览”的核心业务。
- `module/dashboard_api/utils.py`
  - 放置 token 生成、哈希、时间戳与资源名校验等通用函数。

#### 新增配置文件
- `config/dashboard_api.template.yaml`
  - 提供独立服务模板配置。
  - 默认配置使用 SQLite，例如 `sqlite:///./data/dashboard_api.db`。
  - 文档中说明切换 MySQL 时改为 `mysql+pymysql://...`。

#### API 设计定稿
- 公共接口
  - `GET /api/v1/health`
    - 返回服务状态、数据库类型、版本信息。
- 管理员接口
  - `GET /api/v1/admin/users`
    - 列出所有用户及状态，不回传明文 token。
  - `POST /api/v1/admin/users`
    - 创建用户并返回一次性明文 token。
  - `GET /api/v1/admin/users/{user_id}`
    - 查看单个用户详情。
  - `PATCH /api/v1/admin/users/{user_id}`
    - 启用/禁用用户、修改显示名。
  - `POST /api/v1/admin/users/{user_id}/rotate-token`
    - 轮换令牌并返回新的明文 token。
- 用户数据接口
  - `GET /api/v1/me`
    - 返回当前 token 绑定的用户信息。
  - `POST /api/v1/pushes`
    - 接收脚本推送的资源快照批次。
    - 请求体固定包含 `recorded_at_ms`，服务端只校验与存储，不改写。
  - `GET /api/v1/resources/latest`
    - 返回当前用户全部最新资源值。
  - `GET /api/v1/resources/{resource_name}/history`
    - 返回指定资源的时间序列，支持 `from_ms`、`to_ms`、`limit`、`order` 查询参数。
  - `GET /api/v1/widget/overview`
    - 返回适合安卓桌面小部件的轻量聚合结果，包括常用资源的最新值、辅助值、颜色、记录时间、距今毫秒数。

#### 推送请求体定稿
- 统一为批量资源快照：

```json
{
  "source": {
    "instance": "alas",
    "config": "alas",
    "producer": "AzurLaneAutoScript"
  },
  "recorded_at_ms": 1750000000000,
  "resources": {
    "Oil": {
      "value": 1200,
      "limit": 25000,
      "color": "#000000"
    },
    "ActionPoint": {
      "value": 40,
      "total": 200,
      "color": "#0000FF"
    }
  }
}
```

#### 数据库存储定稿
- 用户表 `dashboard_api_users`
  - `id`
  - `user_key` 唯一业务标识
  - `display_name`
  - `token_hash`
  - `is_active`
  - `created_at_ms`
  - `updated_at_ms`
- 历史表 `dashboard_resource_samples`
  - `id`
  - `user_id`
  - `resource_name`
  - `recorded_at_ms`
  - `received_at_ms`
  - `value`
  - `limit_value` 可空
  - `total_value` 可空
  - `color` 可空
  - `source_instance` 可空
  - `source_config` 可空
- 最新表 `dashboard_resource_latest`
  - `user_id`
  - `resource_name`
  - `recorded_at_ms`
  - `received_at_ms`
  - `value`
  - `limit_value`
  - `total_value`
  - `color`
  - 仅当新推送的 `recorded_at_ms >= 当前最新 recorded_at_ms` 时更新，避免旧数据回灌覆盖最新状态。

#### 兼容与校验策略
- 资源名不在服务端硬编码白名单内时，不直接拒绝；只要求满足基本命名规则（字母/数字/下划线），以兼容后续新资源扩展。
- 单条推送可携带一个或多个资源，历史表逐资源拆分落库。
- `recorded_at_ms` 缺失或非法时返回 400。
- 用户被禁用时返回 403。
- API 不负责去重；“每次推送都入库”由客户端调用频率决定。

### 2. 脚本侧新增 API 推送能力

#### 新文件
- `module/dashboard_sync/__init__.py`
  - 建立脚本侧同步包。
- `module/dashboard_sync/client.py`
  - 封装对 API 的 HTTP 调用。
  - 使用仓库已有的 `requests`，设置短超时并捕获异常。
  - 对外提供：
    - `push_dashboard_snapshot(config, recorded_at_ms, resources)`
    - `build_api_headers(token)`
- `module/dashboard_sync/dispatcher.py`
  - 提供进程内异步队列或轻量后台线程。
  - 目标是把网络 I/O 从 `LogRes.__setattr__` 主流程中隔离出去，避免 OCR/战斗逻辑被 API 慢响应阻塞。
- `module/dashboard_sync/payload.py`
  - 负责把当前 `Dashboard.*` 结构转换为 API 侧统一的资源快照结构。

#### 修改文件
- `module/log_res/log_res.py`
  - 保持其“资源写入口”的定位不变。
  - 新增能力：
    - 在本地 `config.modified` 写值后，提取该资源的脚本侧快照。
    - 统一生成 `recorded_at_ms`。
    - 如果实例配置中已启用 API 且填入地址/令牌，则把资源快照提交给 `dashboard_sync.dispatcher`。
  - 这里继续保留当前本地 `Dashboard.Record` 的写入，确保 WebUI Overview 现有面板不受影响。
- 不额外大面积修改各资源采集点
  - 由于 `LogRes` 已覆盖当前资源采集主路径，实施时应优先保证“只要走 `LogRes` 就自动具备 API 推送能力”，避免重复改动 `campaign/shop/gacha/os/raid/coalition` 等调用点。
  - 仅在发现某些资源更新未经过 `LogRes` 时，再补最小必要修复。

#### 脚本侧失败策略
- 推送失败只写日志，不中断主脚本任务，不回滚本地 `Dashboard` 配置更新。
- 后台发送队列不做磁盘持久化；若 API 宕机，数据可丢失，但不影响主脚本运行。
- 如果同一资源短时间内多次更新，后台队列允许按资源名做覆盖式合并，以减少无意义请求风暴；但最终实施以“最小侵入 + 易维护”为优先。

### 3. 在 Alas 树下新增 `Dashboard设置`

#### 修改文件
- `module/config/argument/argument.yaml`
  - 新增一组实例级参数组，命名定为 `DashboardAPI`：
    - `Enable`：是否启用 API 推送。
    - `BaseURL`：API 基地址。
    - `Token`：当前 Alas 实例使用的用户令牌。
    - `Timeout`：请求超时秒数，默认给一个安全值，例如 `3`。
  - 这组配置专用于脚本推送，不与 API 服务端自己的数据库/管理员配置混用。
- `module/config/argument/task.yaml`
  - 在 `Alas` 任务组下新增一个任务页 `DashboardSettings`。
  - 该任务页只绑定 `DashboardAPI` 参数组，不需要 `Scheduler`。
- `module/config/argument/default.yaml`
  - 如有必要，为 `DashboardAPI.Enable` / `DashboardAPI.Timeout` 设默认值。
- `module/config/argument/gui.yaml`
  - 仅在需要新增 GUI 专用按钮/提示文案时追加；如果只是配置页标签，则主要由 i18n JSON 承接。
- `module/config/config_updater.py`
  - 不改变生成逻辑本身，但实施时需要重新运行生成器，刷新派生文件。

#### 生成/更新的派生文件
- `module/config/argument/args.json`
- `module/config/argument/menu.json`
- `module/config/config_generated.py`
- `config/template.json`

#### 多语言文案
- `module/config/i18n/zh-CN.json`
- `module/config/i18n/zh-TW.json`
- `module/config/i18n/en-US.json`
- `module/config/i18n/ja-JP.json`
  - 需要为以下键提供可读文案：
    - `Task.DashboardSettings.name`
    - `Task.DashboardSettings.help`
    - `DashboardAPI._info.name`
    - `DashboardAPI._info.help`
    - `DashboardAPI.Enable.name`
    - `DashboardAPI.BaseURL.name`
    - `DashboardAPI.Token.name`
    - `DashboardAPI.Timeout.name`

#### WebUI 影响说明
- `module/webui/app.py` 预计不需要专门新增左栏渲染代码，因为其已通过 `menu.json` / `args.json` 自动渲染任务页。
- 若实施后发现 `DashboardSettings` 需要额外的掩码输入或帮助提示显示微调，再最小修改 `module/webui/widgets.py` 或 `module/webui/app.py`，但这不应作为首选路径。

### 4. 输出 Android 端可用的详细 API 文档

#### 新文件
- `doc/dashboard-api.md`
  - 作为单一主文档，包含“项目背景 + 数据来源 + 鉴权模型 + REST API 规范 + 错误码 + 示例请求响应 + 安卓端建议”的完整说明，避免把背景与接口拆成多个零散文件。

#### 文档应覆盖的内容
- 项目背景
  - 本仓库是 Azur Lane 自动脚本。
  - 当前资源数据来源于脚本运行过程中的 OCR/状态识别。
  - 资源首先进入本地 `Dashboard.*` 配置，再推送到独立 API。
  - 安卓端不直接接触游戏，也不反向控制脚本，仅消费该 API。
- 数据语义
  - 当前已知资源类型与字段含义，例如 `Value`、`Limit`、`Total`、`Color`、`recorded_at_ms`。
  - 时间戳由脚本端提供，语义为“脚本识别到该资源值的时间”。
- 鉴权说明
  - admin token 的作用。
  - user token 的作用。
  - 令牌创建/轮换流程。
- 接口说明
  - 每个 endpoint 的路径、方法、请求头、参数、请求体、响应体、错误码。
- 数据库与部署说明
  - SQLite 与 MySQL 的配置方式。
  - 独立 API 的启动命令。
- 安卓端建议
  - 图表页建议调用的历史接口。
  - 桌面小部件建议调用的 `widget/overview` 接口。
  - 建议的轮询频率、缓存策略、旧数据处理方式。

### 5. 依赖与部署补充

#### 修改文件
- `requirements-in.txt`
  - 新增数据库依赖。
- `requirements.txt`
  - 同步锁定依赖版本。
- `deploy/headless/requirements.txt`
- `deploy/docker/requirements.txt`
- `deploy/AidLux/0.92/requirements.txt`
  - 若这些文件在当前仓库流程中作为可直接安装的提交产物，则需要同步补齐新依赖，避免不同部署渠道缺包。

#### 依赖建议
- `SQLAlchemy==1.4.x`
- `PyMySQL==1.1.x`
- 若实施时确认无需额外序列化库，则不再新增其他 Web 依赖。

## Implementation Steps
1. 建立 `module/dashboard_api/` 包、独立启动入口与 `config/dashboard_api.template.yaml`。
2. 完成数据库层与三张表模型，先打通 SQLite，再确保 MySQL URL 与方言兼容。
3. 实现 admin/user/widget 三组 REST 路由，并固定请求/响应格式。
4. 新建 `module/dashboard_sync/`，实现脚本侧异步推送客户端。
5. 修改 `module/log_res/log_res.py`，让资源写入本地 Dashboard 后自动向 API 异步推送。
6. 在 `argument.yaml` / `task.yaml` 中加入 `DashboardSettings` + `DashboardAPI`，重新生成配置派生文件。
7. 补齐多语言文案，使左侧栏与配置页显示为可读名称。
8. 编写 `doc/dashboard-api.md`，把背景、接口、部署、安卓端建议一次性写全。
9. 做 SQLite 端到端验证，再做 MySQL 方言/连接路径验证，最后执行全仓编译检查。

## Verification Steps
- 配置生成验证
  - 运行 `python -m module.config.config_updater`。
  - 确认 `DashboardSettings` 出现在生成后的 `module/config/argument/menu.json` 与 `args.json` 中。
  - 确认 `config/template.json` 中出现 `Alas` 实例级的 `DashboardAPI` 设置。
- API 启动验证
  - 使用 SQLite 模板配置启动：
    - `python -m module.dashboard_api --config ./config/dashboard_api.yaml`
  - 访问 `GET /api/v1/health`，确认服务与数据库初始化成功。
- 管理员接口验证
  - 使用 admin token 创建用户。
  - 校验创建响应返回一次性 token，列表接口不泄露明文 token。
  - 轮换 token 后，旧 token 失效，新 token 生效。
- 数据写入验证
  - 使用用户 token 调用 `POST /api/v1/pushes` 写入包含多个资源的样例快照。
  - 确认 `GET /api/v1/resources/latest` 返回最新值。
  - 确认 `GET /api/v1/resources/Oil/history` 返回按时间排序的历史点。
  - 确认 `GET /api/v1/widget/overview` 返回轻量概览字段。
- 脚本集成验证
  - 在某个 Alas 实例里填写 `Dashboard设置` 的 API 地址与 token。
  - 手动触发一个已经会写 `LogRes` 的资源更新路径，确认服务端收到数据，且本地 WebUI Dashboard 仍正常刷新。
- MySQL 支持验证
  - 若环境可用 MySQL，执行一轮真实连通性与建表验证。
  - 若环境没有 MySQL 服务，至少验证 MySQL URL 解析、engine 初始化、metadata 编译路径无语法错误，并在文档中标记“真实连通性需在目标部署环境复验”。
- 静态验证
  - 运行 `python -m compileall` 覆盖 `module/dashboard_api`、`module/dashboard_sync`、`module/log_res`、`module/config`、`module/webui`。

## Acceptance Criteria
- 可以用独立命令手动启动 REST API。
- API 支持多用户令牌管理，并能区分 admin token 与 user token。
- API 同时支持 SQLite 与 MySQL 配置。
- 脚本在不破坏现有 Dashboard 本地展示的前提下，可以自动把资源快照推送到 API。
- `Alas` 左侧树下能看到 `Dashboard设置`，且设置项按实例保存。
- 手机端可以主动查询最新资源、单资源历史序列和小部件概览。
- 仓库中存在一份完整文档，足够给后续安卓端开发提供上下文与接口依据。

## Risks & Mitigations
- 数据库依赖新增会影响多种部署路径：
  - 通过同步更新各套 requirements 并在文档中明确安装方式降低风险。
- `LogRes` 直接联网可能阻塞主脚本：
  - 通过 `module/dashboard_sync/dispatcher.py` 做异步发送隔离。
- 旧时间戳回灌可能覆盖最新状态：
  - 最新表更新按 `recorded_at_ms` 比较，只允许更“新”的记录覆盖。
- 明文 token 泄露风险：
  - 数据库存储哈希值，只有创建/轮换时回传一次明文。
- Android 小部件轮询过频：
  - 在文档中明确推荐轮询频率，并提供轻量 `widget/overview` 接口，避免客户端滥用通用历史接口。
