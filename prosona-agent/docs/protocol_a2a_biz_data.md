# A2A 业务数据消息标准协议（A2A Biz Data Message Protocol）

本文档约定通过 `A2ABizDataMessage` 下发的业务数据消息的 **identifier** 与 **params** 结构，便于前端/客户端与 Agent 侧对齐。

消息载体为 `A2ABizDataMessage`，其 `content` 结构为：

```json
{
    "type": "biz",
    "identifier": "<identifier>",
    "params": {
        ...
    }
}
```

以下仅规范 **identifier** 与 **params** 的语义与字段。

---

## 1. Activity 生命周期（biz-common-activity-lifecycle）

在 **Activity** 维度的生命周期节点（进入、暂停、继续、中断、恢复、结束）需要向客户端发送一次业务数据，用于埋点、统计或 UI 状态同步。

### 1.1 协议标识

- **identifier**: `biz-common-activity-lifecycle`

### 1.2 params 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 模式：`start` / `pause` / `resume` / `interrupt` / `recover` / `end` |
| `activity_id` | string | 是 | 活动 ID |
| `activity_name` | string | 是 | 活动名称 |
| `activity_type` | string | 是 | 活动类型（如 lecture / report 等） |


### 1.3 示例

```json
{
    "type": "biz",
    "identifier": "biz-common-activity-lifecycle",
    "params": {
        "type": "start",
        "activity_id": "<activity_id>",
        "activity_name": "<activity_name>",
        "activity_type": "<activity_type>"
    }
}
```

---

## 2. SCO 生命周期（biz-common-sco-lifecycle）

在 **SCO** 维度的生命周期节点（进入、暂停、继续、中断、恢复、结束）需要向客户端发送业务数据，与 Activity 协议类似，但携带 SCO 及顺序信息。

### 2.1 协议标识

- **identifier**: `biz-common-sco-lifecycle`

### 2.2 params 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 生命周期类型，见下表 |
| `data` | object | 是 | 详见 data 字段说明 |

**data 字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 模式：`start` / `pause` / `resume` / `interrupt` / `recover` / `end` |
| `sco_id` | string | 是 | SCO ID |
| `sco_name` | string | 是 | SCO 名称 |
| `sco_type` | string | 是 | SCO 类型 |
| `activity_id` | string | 是 | 所属活动 ID |
| `order` | number | 是 | 当前 SCO 在活动内的顺序（从 1 开始） |

### 2.3 示例

```json
{
    "type": "biz",
    "identifier": "biz-common-sco-lifecycle",
    "params": {
        "type": "start",
        "data": {
            "type": "start",
            "sco_id": "<sco_id>",
            "sco_name": "<sco_name>",
            "sco_type": "<sco_type>",
            "activity_id": "<activity_id>",
            "order": 1
        }
    }
}
```

---

## 3. 布局（biz-common-layout）

在内容展示前，向客户端发送布局切换消息，用于 UI 切换到对应的展示布局。

### 3.1 协议标识

- **identifier**: `biz-common-layout`

### 3.2 params 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 布局类型：`canvas` / `speaker` |

### 3.3 示例

```json
{
    "type": "biz",
    "identifier": "biz-common-layout",
    "params": {
        "type": "canvas"
    }
}
```

---

## 4. 内容展示（biz-common-display）

向客户端发送内容卡片，用于 UI 渲染展示内容（如导练卡、演练卡、复盘卡、报告卡）。

### 4.1 协议标识

- **identifier**: `biz-common-display`

### 4.2 params 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 固定为 `card` |
| `data` | object | 是 | 详见 data 字段说明 |
| `ref` | object | 否 | 关联实体，含 `id`（实体 ID）、`name`（实体名称）、`group`（任务分组）、`params`（实体参数）、`mode`（任务模式） |

**data 字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 卡片 ID |
| `name` | string | 是 | 卡片名称 |
| `type` | string | 是 | 卡片类型（如 content / record / report） |
| `data` | object | 是 | 卡片业务数据 |

### 4.3 示例

```json
{
    "type": "biz",
    "identifier": "biz-common-display",
    "params": {
        "type": "card",
        "data": {
            "id": "<card_id>",
            "name": "内容卡",
            "type": "content",
            "data": {}
        },
        "ref": {
            "id": "<task_id>",
            "name": "<task_name>",
            "group": "project/activity/sco",
            "params": {
                "id": "<project_id>/<activity_id>/<sco_id>"
            },
            "mode": "start"
        }
    }
}
```