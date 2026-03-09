# render_action → aget_card 迁移指南

## 概述

旧系统中，每个 SCO 插件（`SCOPlugin`）通过 `render_action(action)` 方法直接发送 A2A 消息给前端。新系统中，SCO 处理器（`SCOTaskHandler`）通过 `aget_card(state, action, params)` 返回一个 `AOMCard`，由中间件统一处理消息发送。

### 核心变化

| 维度 | 旧（render_action） | 新（aget_card） |
|------|---------------------|-----------------|
| 职责 | 插件自行构建并发送 A2A 消息 | Handler 只返回 AOMCard，中间件负责发送 |
| 过渡消息 | 插件手动发 `activity-introduction` | 中间件自动发 `send_activity_introduction` |
| A2A 标识 | 多种 identifier / type | 统一 `biz-common-sco-display` / `aitutor-sco` |
| 数据结构 | 各插件自定义 params.data | 标准化 AOMCard（id / name / type / data / description） |
| 搜索元数据 | 无 | 自动生成 sf_metadata（search_text / filter_keyword） |

---

## 消息格式对比

所有插件迁移后，前端收到的 A2A 消息从多种 identifier/type 统一为一种外壳，业务差异全部收敛到 `card` 内部。

---

## 1. 多模态内容（SCOMultimodalContentPlugin → MultimodalTaskHandler）

### 1.1 播放视频（itemType=1）

**旧 JSON：**
```json
{
  "identifier": "biz-common-activity-sco-display",
  "params": {
    "type": "aitutor-video",
    "data": {
      "id": "item-001",
      "title": "第一章介绍",
      "fileId": "file-abc-123",
      "startTime": "00:00:00",
      "endTime": "00:05:30",
      "playback_rate": 1,
      "action": "播放视频"
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-001",
      "sco_name": "第一章",
      "sco_type": "multimodal",
      "card": {
        "id": "multimodal-video",
        "name": "播放视频",
        "type": "content",
        "title": "第一章-播放视频",
        "data": {
          "id": "item-001",
          "title": "第一章介绍",
          "fileId": "file-abc-123",
          "startTime": "00:00:00",
          "endTime": "00:05:30",
          "playback_rate": 1,
          "action": "播放视频"
        }
      }
    }
  }
}
```

### 1.2 播放新视频（itemType=6）

**旧 JSON：**
```json
{
  "identifier": "biz-common-activity-sco-display",
  "params": {
    "type": "aitutor-new-video",
    "data": {
      "id": "item-002",
      "title": "实操演示",
      "richText": "<p>视频富文本内容...</p>",
      "playback_rate": 1.5,
      "action": "重新播放视频"
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-001",
      "sco_name": "第一章",
      "sco_type": "multimodal",
      "card": {
        "id": "multimodal-video",
        "name": "重新播放视频",
        "type": "content",
        "title": "第一章-重新播放视频",
        "data": {
          "id": "item-002",
          "title": "实操演示",
          "richText": "<p>视频富文本内容...</p>",
          "playback_rate": 1.5,
          "action": "重新播放视频"
        }
      }
    }
  }
}
```

### 1.3 展示 PPT

**旧 JSON：**
```json
{
  "identifier": "biz-common-activity-sco-display",
  "params": {
    "type": "aitutor-ppt",
    "data": {
      "id": "item-003",
      "title": "项目管理概述",
      "contentUrl": "https://cdn.example.com/ppt/001.pdf",
      "script": "这张PPT主要讲解了项目管理的核心流程...",
      "description": "项目管理概述PPT",
      "action": "展示PPT"
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-001",
      "sco_name": "第一章",
      "sco_type": "multimodal",
      "card": {
        "id": "multimodal-ppt",
        "name": "展示PPT",
        "type": "content",
        "title": "第一章-展示PPT",
        "data": {
          "id": "item-003",
          "title": "项目管理概述",
          "contentUrl": "https://cdn.example.com/ppt/001.pdf",
          "script": "这张PPT主要讲解了项目管理的核心流程...",
          "description": "项目管理概述PPT",
          "action": "展示PPT"
        }
      }
    }
  }
}
```

### 1.4 展示所有素材

**旧 JSON：**
```json
{
  "identifier": "biz-common-activity-sco-display",
  "params": {
    "type": "aitutor-multimodal",
    "data": {
      "items": [
        {"id": "item-001", "title": "视频1", "type": 1, "fileId": "f1"},
        {"id": "item-002", "title": "PPT1", "type": 5, "contentUrl": "https://..."}
      ],
      "action": "展示所有素材"
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-001",
      "sco_name": "第一章",
      "sco_type": "multimodal",
      "card": {
        "id": "multimodal-all",
        "name": "展示所有素材",
        "type": "content",
        "title": "第一章-展示所有素材",
        "data": {
          "items": [
            {"id": "item-001", "title": "视频1", "type": 1, "fileId": "f1"},
            {"id": "item-002", "title": "PPT1", "type": 5, "contentUrl": "https://..."}
          ],
          "action": "展示所有素材"
        }
      }
    }
  }
}
```

**变化总结：**
- 旧系统通过 `params.type`（`aitutor-video` / `aitutor-new-video` / `aitutor-ppt` / `aitutor-multimodal`）区分渲染逻辑
- 新系统 `params.type` 统一为 `aitutor-sco`，前端通过 `card.id`（`multimodal-video` / `multimodal-ppt` / `multimodal-all`）或 `card.data` 中的字段区分
- `card.data` 内部结构与旧 `params.data` 保持一致

---

## 2. 问答题（SCOQuizPlugin → QuizTaskHandler）

### 2.1 开始答题

**旧 JSON：**
```json
{
  "identifier": "biz-common-activity-sco-display",
  "params": {
    "type": "aitutor-quiz",
    "data": {
      "title": "项目管理基础",
      "question": "请简述敏捷开发的核心原则是什么？",
      "explanation": "",
      "action": "开始"
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-002",
      "sco_name": "项目管理基础",
      "sco_type": "quiz",
      "card": {
        "id": "quiz-display",
        "name": "开始",
        "type": "content",
        "title": "项目管理基础-开始",
        "data": {
          "title": "项目管理基础",
          "question": "请简述敏捷开发的核心原则是什么？",
          "explanation": "",
          "action": "开始"
        }
      }
    }
  }
}
```

### 2.2 展示解析

**旧 JSON：**
```json
{
  "identifier": "biz-common-activity-sco-display",
  "params": {
    "type": "aitutor-quiz",
    "data": {
      "title": "项目管理基础",
      "question": "请简述敏捷开发的核心原则是什么？",
      "explanation": "敏捷开发的核心原则包括：1. 个体和互动高于流程和工具...",
      "action": "展示解析"
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-002",
      "sco_name": "项目管理基础",
      "sco_type": "quiz",
      "card": {
        "id": "quiz-display",
        "name": "展示解析",
        "type": "content",
        "title": "项目管理基础-展示解析",
        "data": {
          "title": "项目管理基础",
          "question": "请简述敏捷开发的核心原则是什么？",
          "explanation": "敏捷开发的核心原则包括：1. 个体和互动高于流程和工具...",
          "action": "展示解析"
        }
      }
    }
  }
}
```

**变化总结：**
- `card.data` 与旧 `params.data` 完全一致，迁移最简单
- 旧 `params.type: "aitutor-quiz"` → 新 `card.id: "quiz-display"`

---

## 3. 课程总结（SCOLectureSummaryPlugin → 待迁移）

### 3.1 基础数据

**旧 JSON：**
```json
{
  "identifier": "biz-common-activity-summary",
  "params": {
    "type": "aitutor-finish-summary-section",
    "data": {
      "activity_id": "act-001",
      "activity_name": "项目管理入门",
      "interaction_count": "15",
      "learning_duration_minutes": 45
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-003",
      "sco_name": "课程总结",
      "sco_type": "lecture-summary",
      "card": {
        "id": "lecture-summary-basic",
        "name": "基础数据",
        "type": "content",
        "title": "课程总结-基础数据",
        "data": {
          "activity_id": "act-001",
          "activity_name": "项目管理入门",
          "interaction_count": "15",
          "learning_duration_minutes": 45
        }
      }
    }
  }
}
```

### 3.2 学习亮点

**旧 JSON：**
```json
{
  "identifier": "biz-common-activity-summary",
  "params": {
    "type": "aitutor-finish-summary-section",
    "data": {
      "activity_id": "act-001",
      "activity_name": "项目管理入门",
      "learning_duration_minutes": 45,
      "interaction_count": "15",
      "highlights": [
        {"title": "深入理解Scrum", "description": "你对Scrum框架的提问展示了深度思考..."},
        {"title": "实践导向", "description": "你主动询问了实际项目中的应用场景..."}
      ]
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-003",
      "sco_name": "课程总结",
      "sco_type": "lecture-summary",
      "card": {
        "id": "lecture-summary-highlights",
        "name": "学习亮点",
        "type": "content",
        "title": "课程总结-学习亮点",
        "data": {
          "activity_id": "act-001",
          "activity_name": "项目管理入门",
          "learning_duration_minutes": 45,
          "interaction_count": "15",
          "highlights": [
            {"title": "深入理解Scrum", "description": "你对Scrum框架的提问展示了深度思考..."},
            {"title": "实践导向", "description": "你主动询问了实际项目中的应用场景..."}
          ]
        }
      }
    }
  }
}
```

### 3.3 学习建议（display_all）

**旧 JSON：**
```json
{
  "identifier": "biz-common-activity-summary",
  "params": {
    "type": "aitutor-finish-summary-section",
    "data": {
      "activity_id": "act-001",
      "activity_name": "项目管理入门",
      "learning_duration_minutes": 45,
      "interaction_count": "15",
      "highlights": [
        {"title": "深入理解Scrum", "description": "..."}
      ],
      "learning_suggestions": [
        {"title": "加强看板实践", "description": "建议通过实际项目体验看板方法..."}
      ],
      "artifact_id": "artifact-001",
      "report_name": "学习总结报告",
      "report_title": "项目管理入门-学习总结"
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-003",
      "sco_name": "课程总结",
      "sco_type": "lecture-summary",
      "card": {
        "id": "lecture-summary-full",
        "name": "学习建议",
        "type": "content",
        "title": "课程总结-学习建议",
        "data": {
          "activity_id": "act-001",
          "activity_name": "项目管理入门",
          "learning_duration_minutes": 45,
          "interaction_count": "15",
          "highlights": [
            {"title": "深入理解Scrum", "description": "..."}
          ],
          "learning_suggestions": [
            {"title": "加强看板实践", "description": "建议通过实际项目体验看板方法..."}
          ],
          "artifact_id": "artifact-001",
          "report_name": "学习总结报告",
          "report_title": "项目管理入门-学习总结"
        }
      }
    }
  }
}
```

**变化总结：**
- 旧 `identifier: "biz-common-activity-summary"` → 新统一为 `"biz-common-sco-display"`
- 旧 `params.type: "aitutor-finish-summary-section"` → 新通过 `card.id`（`lecture-summary-basic` / `lecture-summary-highlights` / `lecture-summary-full`）区分渐进阶段
- `card.data` 内部结构与旧 `params.data` 保持一致

---

## 4. 项目报告（SCOProjectReportPlugin → 待迁移）

### 4.1 报告生成中

**旧 JSON（两条消息）：**
```json
// 消息1：项目完成
{
  "identifier": "biz-common-project",
  "params": {
    "type": "aitutor-project-finish",
    "data": {}
  }
}

// 消息2（3s后）：报告生成中
{
  "identifier": "biz-common-report",
  "params": {
    "type": "aitutor-report-generating",
    "data": {}
  }
}
```

**新 JSON（一条消息）：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-004",
      "sco_name": "项目报告",
      "sco_type": "project-report",
      "card": {
        "id": "project-report-intro",
        "name": "报告生成中",
        "type": "content",
        "title": "项目报告-报告生成中",
        "data": {
          "status": "generating"
        }
      }
    }
  }
}
```

### 4.2 报告第一部分

**旧 JSON：**
```json
{
  "identifier": "biz-common-report",
  "params": {
    "type": "aitutor-report-data",
    "data": {
      "part": 1,
      "data": {
        "project_id": "proj-001",
        "artifact_id": "artifact-002",
        "report_name": "个人成长报告",
        "report_title": "Q1项目管理能力评估",
        "full_name": "张三",
        "avatar": "https://cdn.example.com/avatar/001.jpg",
        "start_time": "2025-01-01",
        "end_time": "2025-03-31",
        "total_time": 1200,
        "learning_performance": {"score": 85, "level": "优秀"},
        "cognitive_conversion": {"before": "初级", "after": "中级"},
        "skill_improvement": {"items": [{"name": "需求分析", "delta": 15}]}
      }
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-004",
      "sco_name": "项目报告",
      "sco_type": "project-report",
      "card": {
        "id": "project-report-part-1",
        "name": "报告第一部分",
        "type": "content",
        "title": "项目报告-报告第一部分",
        "data": {
          "part": 1,
          "data": {
            "project_id": "proj-001",
            "artifact_id": "artifact-002",
            "report_name": "个人成长报告",
            "report_title": "Q1项目管理能力评估",
            "full_name": "张三",
            "avatar": "https://cdn.example.com/avatar/001.jpg",
            "start_time": "2025-01-01",
            "end_time": "2025-03-31",
            "total_time": 1200,
            "learning_performance": {"score": 85, "level": "优秀"},
            "cognitive_conversion": {"before": "初级", "after": "中级"},
            "skill_improvement": {"items": [{"name": "需求分析", "delta": 15}]}
          }
        }
      }
    }
  }
}
```

### 4.3 报告第二部分

**旧 JSON：**
```json
{
  "identifier": "biz-common-report",
  "params": {
    "type": "aitutor-report-data",
    "data": {
      "part": 2,
      "data": {
        "project_id": "proj-001",
        "artifact_id": "artifact-002",
        "learning_performance": {"score": 85, "level": "优秀"},
        "cognitive_conversion": {"before": "初级", "after": "中级"},
        "skill_improvement": {"items": [{"name": "需求分析", "delta": 15}]},
        "comprehensive_evaluation": {"summary": "在项目管理领域展现出显著进步..."},
        "growth_performance_view": {"chart_data": [...]},
        "highlight_moments": [{"title": "突破性讨论", "description": "..."}]
      }
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-004",
      "sco_name": "项目报告",
      "sco_type": "project-report",
      "card": {
        "id": "project-report-part-2",
        "name": "报告第二部分",
        "type": "content",
        "title": "项目报告-报告第二部分",
        "data": {
          "part": 2,
          "data": {
            "project_id": "proj-001",
            "artifact_id": "artifact-002",
            "learning_performance": {"score": 85, "level": "优秀"},
            "cognitive_conversion": {"before": "初级", "after": "中级"},
            "skill_improvement": {"items": [{"name": "需求分析", "delta": 15}]},
            "comprehensive_evaluation": {"summary": "在项目管理领域展现出显著进步..."},
            "growth_performance_view": {"chart_data": []},
            "highlight_moments": [{"title": "突破性讨论", "description": "..."}]
          }
        }
      }
    }
  }
}
```

### 4.4 REVIEW 模式（一次性展示全部报告）

**旧 JSON：**
```json
{
  "identifier": "biz-common-report",
  "params": {
    "type": "aitutor-report-review-data",
    "data": {
      "part": 3,
      "data": {
        "project_id": "proj-001",
        "artifact_id": "artifact-002",
        "learning_performance": {},
        "cognitive_conversion": {},
        "skill_improvement": {},
        "comprehensive_evaluation": {},
        "highlight_moments": [],
        "development_advice": {"suggestions": ["...", "..."]}
      }
    }
  }
}
```

**新 JSON：**
```json
{
  "identifier": "biz-common-sco-display",
  "params": {
    "type": "aitutor-sco",
    "data": {
      "sco_id": "sco-004",
      "sco_name": "项目报告",
      "sco_type": "project-report",
      "card": {
        "id": "project-report-review",
        "name": "报告全部",
        "type": "content",
        "title": "项目报告-报告全部",
        "data": {
          "part": 3,
          "data": {
            "project_id": "proj-001",
            "artifact_id": "artifact-002",
            "learning_performance": {},
            "cognitive_conversion": {},
            "skill_improvement": {},
            "comprehensive_evaluation": {},
            "highlight_moments": [],
            "development_advice": {"suggestions": ["...", "..."]}
          }
        }
      }
    }
  }
}
```

**变化总结：**
- 旧系统两种 identifier（`biz-common-project` / `biz-common-report`）+ 多种 type（`aitutor-project-finish` / `aitutor-report-generating` / `aitutor-report-data` / `aitutor-report-review-data`）→ 新系统统一 `biz-common-sco-display`
- 前端通过 `card.id`（`project-report-intro` / `project-report-part-1` / `project-report-part-2` / `project-report-review`）区分渲染阶段
- `card.data` 内部的 `part` + `data` 结构与旧 `params.data` 保持一致
- 旧 `display_intro` 拆为两条消息（项目完成 + 生成中），新系统合并为一条，前端通过 `card.data.status` 处理

---

## 前端适配速查

| 旧 identifier | 旧 params.type | 新 card.id | card.data 变化 |
|---------------|---------------|------------|---------------|
| `biz-common-activity-sco-display` | `aitutor-video` | `multimodal-video` | 无变化 |
| `biz-common-activity-sco-display` | `aitutor-new-video` | `multimodal-video` | 无变化 |
| `biz-common-activity-sco-display` | `aitutor-ppt` | `multimodal-ppt` | 无变化 |
| `biz-common-activity-sco-display` | `aitutor-multimodal` | `multimodal-all` | 无变化 |
| `biz-common-activity-sco-display` | `aitutor-quiz` | `quiz-display` | 无变化 |
| `biz-common-activity-summary` | `aitutor-finish-summary-section` | `lecture-summary-basic` / `lecture-summary-highlights` / `lecture-summary-full` | 无变化 |
| `biz-common-project` | `aitutor-project-finish` | `project-report-intro` | `{"status":"generating"}` |
| `biz-common-report` | `aitutor-report-generating` | `project-report-intro` | 合并到上面 |
| `biz-common-report` | `aitutor-report-data` | `project-report-part-1` / `part-2` / `part-3` | 无变化 |
| `biz-common-report` | `aitutor-report-review-data` | `project-report-review` | 无变化 |
