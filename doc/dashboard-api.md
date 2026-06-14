# Dashboard API 文档

## 1. 项目背景

本仓库是 `AzurLaneAutoScript` 的一个自动化脚本项目，核心职责是通过设备控制、OCR 与页面状态识别来执行《碧蓝航线》的重复性操作。当前仓库已经具备本地 Dashboard 能力：脚本在识别到资源值后，会把资源写入实例配置中的 `Dashboard.*`，然后由内置 WebUI 展示石油、物资、钻石、魔方、行动力等信息。

本次新增的 `Dashboard API` 的定位不是替代现有 WebUI，而是把这些已经采集到的资源数据对外标准化输出，供手机端主动查询。这样后续安卓端应用可以在不直接操作游戏、不接入模拟器、不理解脚本内部 OCR 细节的前提下，仅通过 REST API 获取资源最新值、历史时间序列以及适合桌面小部件的轻量概览数据。

整个数据链如下：

1. 脚本在运行中识别游戏资源。
2. 识别结果通过 `module/log_res/log_res.py` 写入本地 `Dashboard.*`。
3. `LogRes` 在写本地 Dashboard 的同时，把相同的资源快照异步推送到独立的 `Dashboard API`。
4. 独立 API 把每次推送写入历史表，并维护最新快照表。
5. 安卓端通过用户令牌查询最新值、历史值和小部件概览。

## 2. 设计原则

- API 是独立进程，独立命令手动启动，不与现有 WebUI 共进程。
- API 使用 RESTful 风格，所有接口都在 `/api/v1` 下。
- 支持多用户并发记录，通过不同用户令牌区分各自的数据空间。
- 业务时间戳由脚本端提供，字段为 `recorded_at_ms`，语义是“脚本识别到该资源值的时间”。
- 服务端可以记录 `received_at_ms` 作为接收时间，但不得覆盖脚本提供的业务时间。
- 数据库存储同时支持 SQLite 与 MySQL。
- 安卓桌面小部件不需要自己拼装复杂聚合逻辑，直接调用专用轻量接口即可。

## 3. 鉴权模型

API 有两类令牌：

- `admin token`
  - 只用于服务管理。
  - 在 API 服务配置文件里设置。
  - 可创建用户、禁用用户、轮换用户 token。
- `user token`
  - 由管理员创建或轮换后发给脚本实例或手机端。
  - 脚本用它推送数据。
  - 手机端用它查询当前用户的数据。

所有受保护接口都使用以下请求头：

```http
Authorization: Bearer <token>
```

用户 token 在数据库里只保存哈希值；明文 token 只会在“创建用户”或“轮换 token”的响应里返回一次。

## 4. 数据模型

### 4.1 资源快照

单个资源对象的标准结构如下：

```json
{
  "value": 1200,
  "limit": 25000,
  "color": "#000000"
}
```

或：

```json
{
  "value": 40,
  "total": 200,
  "color": "#0000FF"
}
```

字段含义：

- `value`
  - 主值，必填。
- `limit`
  - 上限值，可选，常用于石油、物资、活动 PT。
- `total`
  - 总量值，可选，常用于行动力这类“当前值 / 总值”结构。
- `color`
  - 颜色字符串，可选，脚本侧会把现有的 `^RRGGBB` 格式转成 `#RRGGBB`。

### 4.2 推送批次

脚本向 API 推送的是一个“同一时刻的资源快照批次”：

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

字段含义：

- `source.instance`
  - 脚本实例名。
- `source.config`
  - 当前脚本配置名。
- `source.producer`
  - 固定写为 `AzurLaneAutoScript`，方便手机端或调试工具识别数据来源。
- `recorded_at_ms`
  - 业务时间戳，单位毫秒，由脚本端提供。
- `resources`
  - 以资源名为 key 的资源快照集合。

### 4.3 数据库表

#### `dashboard_api_users`

- `id`
- `user_key`
- `display_name`
- `token_hash`
- `is_active`
- `created_at_ms`
- `updated_at_ms`

#### `dashboard_resource_samples`

- `id`
- `user_id`
- `resource_name`
- `recorded_at_ms`
- `received_at_ms`
- `value`
- `limit_value`
- `total_value`
- `color`
- `source_instance`
- `source_config`

这个表保存完整历史，用于图表查询。

#### `dashboard_resource_latest`

- `id`
- `user_id`
- `resource_name`
- `recorded_at_ms`
- `received_at_ms`
- `value`
- `limit_value`
- `total_value`
- `color`

这个表保存每个资源的最新值，用于首页与桌面小部件快速查询。

## 5. 服务配置

推荐先复制模板：

```bash
cp config/dashboard_api.template.yaml config/dashboard_api.yaml
```

模板内容示例：

```yaml
server:
  host: 0.0.0.0
  port: 22367
  log_level: info

database:
  url: sqlite:///./data/dashboard_api.db
  # mysql example:
  # url: mysql+pymysql://user:password@127.0.0.1:3306/dashboard_api?charset=utf8mb4

auth:
  admin_token: change-me-admin-token

cors_allowed_origins: []
```

### SQLite

```yaml
database:
  url: sqlite:///./data/dashboard_api.db
```

### MySQL

```yaml
database:
  url: mysql+pymysql://user:password@127.0.0.1:3306/dashboard_api?charset=utf8mb4
```

## 6. 启动方式

独立启动命令：

```bash
python -m module.dashboard_api --config ./config/dashboard_api.yaml
```

可选参数：

- `--host`
  - 覆盖配置文件中的监听地址。
- `--port`
  - 覆盖配置文件中的监听端口。

## 7. REST API

### 7.1 健康检查

#### `GET /api/v1/health`

用途：

- 检查服务是否启动成功。
- 检查当前数据库类型。

响应示例：

```json
{
  "status": "ok",
  "database": "sqlite",
  "user_count": 1,
  "generated_at_ms": 1750000000000
}
```

### 7.2 管理员接口

#### `GET /api/v1/admin/users`

请求头：

```http
Authorization: Bearer <admin_token>
```

响应示例：

```json
{
  "users": [
    {
      "id": 1,
      "user_key": "main-account",
      "display_name": "主号",
      "is_active": true,
      "created_at_ms": 1750000000000,
      "updated_at_ms": 1750000000000
    }
  ]
}
```

#### `POST /api/v1/admin/users`

请求头：

```http
Authorization: Bearer <admin_token>
Content-Type: application/json
```

请求体：

```json
{
  "user_key": "main-account",
  "display_name": "主号"
}
```

响应示例：

```json
{
  "user": {
    "id": 1,
    "user_key": "main-account",
    "display_name": "主号",
    "is_active": true,
    "created_at_ms": 1750000000000,
    "updated_at_ms": 1750000000000
  },
  "token": "returned-once-only"
}
```

说明：

- `token` 只会在创建响应中返回一次。
- `user_key` 必须唯一。

#### `GET /api/v1/admin/users/{user_id}`

请求头：

```http
Authorization: Bearer <admin_token>
```

响应示例：

```json
{
  "id": 1,
  "user_key": "main-account",
  "display_name": "主号",
  "is_active": true,
  "created_at_ms": 1750000000000,
  "updated_at_ms": 1750000000000
}
```

#### `PATCH /api/v1/admin/users/{user_id}`

请求体：

```json
{
  "display_name": "主号-安卓",
  "is_active": true
}
```

用途：

- 修改显示名。
- 启用或禁用用户。

#### `POST /api/v1/admin/users/{user_id}/rotate-token`

响应示例：

```json
{
  "user": {
    "id": 1,
    "user_key": "main-account",
    "display_name": "主号",
    "is_active": true,
    "created_at_ms": 1750000000000,
    "updated_at_ms": 1750000100000
  },
  "token": "new-token-returned-once-only"
}
```

用途：

- 令牌泄露时立即更换。
- 安卓端和脚本端同步替换新 token。

### 7.3 用户接口

#### `GET /api/v1/me`

请求头：

```http
Authorization: Bearer <user_token>
```

响应示例：

```json
{
  "id": 1,
  "user_key": "main-account",
  "display_name": "主号",
  "is_active": true,
  "created_at_ms": 1750000000000,
  "updated_at_ms": 1750000000000
}
```

#### `POST /api/v1/pushes`

请求头：

```http
Authorization: Bearer <user_token>
Content-Type: application/json
```

请求体：

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
    "Gem": {
      "value": 120,
      "color": "#FF3333"
    }
  }
}
```

响应示例：

```json
{
  "accepted": 2,
  "recorded_at_ms": 1750000000000,
  "received_at_ms": 1750000001234
}
```

说明：

- `resources` 可以只包含一个资源，也可以包含多个资源。
- API 会把批次拆成多条历史记录。
- 最新快照表只会被“更晚或相同 `recorded_at_ms`”的记录覆盖。

#### `GET /api/v1/resources/latest`

请求头：

```http
Authorization: Bearer <user_token>
```

响应示例：

```json
{
  "resources": [
    {
      "resource_name": "Oil",
      "recorded_at_ms": 1750000000000,
      "received_at_ms": 1750000001234,
      "value": 1200,
      "limit": 25000,
      "total": null,
      "color": "#000000"
    },
    {
      "resource_name": "Gem",
      "recorded_at_ms": 1750000000000,
      "received_at_ms": 1750000001234,
      "value": 120,
      "limit": null,
      "total": null,
      "color": "#FF3333"
    }
  ]
}
```

用途：

- 手机首页加载当前全部最新资源。
- 手动刷新资源面板。

#### `GET /api/v1/resources/{resource_name}/history`

查询参数：

- `from_ms`
  - 可选，起始业务时间戳。
- `to_ms`
  - 可选，结束业务时间戳。
- `limit`
  - 可选，默认 `500`，最大 `5000`。
- `order`
  - 可选，`asc` 或 `desc`，默认 `desc`。

请求示例：

```http
GET /api/v1/resources/Oil/history?from_ms=1749900000000&to_ms=1750000000000&order=asc&limit=1440
Authorization: Bearer <user_token>
```

响应示例：

```json
{
  "resource_name": "Oil",
  "items": [
    {
      "resource_name": "Oil",
      "recorded_at_ms": 1749990000000,
      "received_at_ms": 1749990000321,
      "value": 1320,
      "limit": 25000,
      "total": null,
      "color": "#000000"
    },
    {
      "resource_name": "Oil",
      "recorded_at_ms": 1750000000000,
      "received_at_ms": 1750000001234,
      "value": 1200,
      "limit": 25000,
      "total": null,
      "color": "#000000"
    }
  ]
}
```

用途：

- 安卓图表页拉取时间序列。
- 统计最近 24 小时、7 天、30 天的资源变化趋势。

#### `GET /api/v1/widget/overview`

请求头：

```http
Authorization: Bearer <user_token>
```

响应示例：

```json
{
  "generated_at_ms": 1750000002000,
  "resources": [
    {
      "resource_name": "Oil",
      "recorded_at_ms": 1750000000000,
      "received_at_ms": 1750000001234,
      "value": 1200,
      "limit": 25000,
      "total": null,
      "color": "#000000",
      "age_ms": 2000
    },
    {
      "resource_name": "Gem",
      "recorded_at_ms": 1750000000000,
      "received_at_ms": 1750000001234,
      "value": 120,
      "limit": null,
      "total": null,
      "color": "#FF3333",
      "age_ms": 2000
    }
  ]
}
```

用途：

- 安卓桌面小部件直接轮询。
- 轻量首页卡片快速显示。

说明：

- 响应里额外提供 `age_ms`，便于安卓侧判断数据是否过旧。
- 返回顺序优先使用当前 Dashboard 常用资源顺序，未知新资源会追加到后面。

## 8. 错误处理

常见状态码：

- `400`
  - 请求体不合法。
  - `recorded_at_ms` 缺失或非法。
  - `resource_name` 不合法。
- `401`
  - 缺失 bearer token。
- `403`
  - token 无效。
  - 用户已被禁用。
- `404`
  - 用户不存在。
- `409`
  - 创建用户时 `user_key` 重复。

错误响应格式：

```json
{
  "error": "message"
}
```

或在 Pydantic 校验失败时：

```json
{
  "error": [
    {
      "loc": ["recorded_at_ms"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## 9. 脚本侧接入说明

脚本配置项位于 WebUI 左侧 `Alas` 树下的 `Dashboard设置` 页面，按实例保存：

- `Enable`
  - 是否启用 API 推送。
- `BaseURL`
  - API 基地址，例如 `http://127.0.0.1:22367`。
- `Token`
  - 当前实例对应的用户 token。
- `Timeout`
  - HTTP 推送超时秒数。

脚本仍会继续维护本地 `Dashboard.*`，因此：

- WebUI 原有 Dashboard 面板仍可正常显示。
- API 推送失败不会中断脚本主任务。
- 日志会记录推送失败原因，便于排查。

## 10. 安卓端开发建议

### 图表页

推荐使用：

- `GET /api/v1/resources/{resource_name}/history`

建议做法：

- 日、周、月视图分别传不同的 `from_ms/to_ms`。
- 如果需要客户端降采样，可在安卓端本地按分钟或小时聚合。
- 若 `recorded_at_ms` 与当前时间差过大，应明确显示“数据可能已过期”。

### 首页资源面板

推荐使用：

- `GET /api/v1/resources/latest`

适合：

- 资源总览页。
- 详情页进入前的预览数据。

### 桌面小部件

推荐使用：

- `GET /api/v1/widget/overview`

原因：

- 这个接口已经是轻量聚合结果。
- 安卓侧不需要自己计算 `age_ms`。
- 适合定时轮询并直接映射到 RemoteViews。

推荐轮询频率：

- 前台界面：15 到 60 秒。
- 桌面小部件：15 分钟左右，或结合系统刷新策略。

## 11. 安全与运维建议

- 上线前必须修改 `admin_token`。
- 不要把 user token 写入公开仓库或公开日志。
- 若手机丢失或 token 泄露，直接调用管理员接口轮换 token。
- 若使用公网访问，建议在反向代理层增加 HTTPS。
- 若使用 MySQL，建议单独建立库与最小权限账号。

## 12. 兼容性说明

- 资源名不是写死白名单，后续脚本新增资源时，API 允许按通用规则继续接收。
- 当前历史接口返回原始时间序列，不做服务器端聚合，方便安卓端按自己 UI 需求绘图。
- 当前仓库不包含安卓实现；本文件的目标是为安卓端后续开发提供足够上下文与稳定数据契约。
