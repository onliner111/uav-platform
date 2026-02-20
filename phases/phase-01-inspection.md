# Phase 01 — 城市巡查基础版（B 主线）

## Goal

实现“巡查最小闭环”：

模板 → 创建巡查任务 → 产生成果 → 地图展示 → 导出巡查记录单

完成后系统必须支持：

- 城管巡查模板管理
- 地图区域创建巡查任务
- 巡查成果结构化存储
- 地图展示成果点位
- 导出巡查记录（HTML）

---

# Scope (Strict)

本阶段只实现：

- inspection_templates
- inspection_template_items
- inspection_tasks
- inspection_observations
- inspection_exports
- UI 页面：
  - /ui/inspection
  - /ui/inspection/tasks/{task_id}
- demo_inspection_phase1.py
- e2e 接入

禁止实现：

- 缺陷流转（Phase 02）
- 工单系统
- 应急模式
- 微服务拆分
- 新增基础设施服务

---

# Data Model

所有表必须包含：
- id (UUID)
- tenant_id (UUID)
- created_at (timestamp with timezone)

## 1️ inspection_templates

- id UUID PK
- tenant_id UUID NOT NULL
- name VARCHAR(100)
- category VARCHAR(50)
- description TEXT
- is_active BOOLEAN DEFAULT true
- created_at TIMESTAMPTZ

## 2️ inspection_template_items

- id UUID PK
- tenant_id UUID NOT NULL
- template_id UUID FK → inspection_templates.id
- code VARCHAR(50)
- title VARCHAR(100)
- severity_default INT
- required BOOLEAN DEFAULT true
- sort_order INT
- created_at TIMESTAMPTZ

## 3️ inspection_tasks

- id UUID PK
- tenant_id UUID NOT NULL
- name VARCHAR(100)
- template_id UUID FK
- mission_id UUID FK → missions.id (nullable)
- area_geom GEOMETRY(POLYGON, 4326)
- status VARCHAR(20) (DRAFT, SCHEDULED, RUNNING, DONE)
- created_at TIMESTAMPTZ

## 4️ inspection_observations

- id UUID PK
- tenant_id UUID NOT NULL
- task_id UUID FK
- drone_id UUID nullable
- ts TIMESTAMPTZ
- position_lat DOUBLE PRECISION
- position_lon DOUBLE PRECISION
- alt_m DOUBLE PRECISION
- item_code VARCHAR(50)
- severity INT
- note TEXT
- media_url TEXT nullable
- confidence FLOAT nullable
- created_at TIMESTAMPTZ

## 5️ inspection_exports

- id UUID PK
- tenant_id UUID NOT NULL
- task_id UUID FK
- format VARCHAR(10)
- file_path TEXT
- created_at TIMESTAMPTZ

必须创建 Alembic migration。

---

# Permissions

新增权限：

- inspection:read
- inspection:write

必须接入 require_perm。

---

# API Contract

## Templates

GET /api/inspection/templates  
POST /api/inspection/templates  
GET /api/inspection/templates/{id}  
POST /api/inspection/templates/{id}/items  
GET /api/inspection/templates/{id}/items  

## Tasks

POST /api/inspection/tasks  
GET /api/inspection/tasks  
GET /api/inspection/tasks/{id}  

## Observations

POST /api/inspection/tasks/{task_id}/observations  
GET /api/inspection/tasks/{task_id}/observations  

## Export

POST /api/inspection/tasks/{task_id}/export?format=html  
GET /api/inspection/exports/{export_id}

必须更新 OpenAPI。

---

# UI Requirements

路径：

- /ui/inspection
- /ui/inspection/tasks/{task_id}

技术要求：

- 使用 Jinja2 模板
- 使用 Leaflet CDN
- 不引入 Node
- 静态 JS 放在 app/web/static/

功能：

- 显示任务列表
- 点击任务显示地图
- 地图展示 observation 点位
- 点击点位显示详情
- 导出按钮

---

# Demo Script

新增：

infra/scripts/demo_inspection_phase1.py

必须执行：

1. 创建模板（违建/占道/垃圾）
2. 创建巡查任务（区域 polygon）
3. 注入 3 条 observation
4. 调用 export
5. 校验返回成功

必须纳入 make e2e。

---

# Acceptance Criteria

阶段完成必须满足：

- make lint 通过
- make typecheck 通过
- make test 通过
- make e2e 通过
- UI 可访问
- 地图显示点位
- 导出成功

---

# Completion Output

完成后输出：

- What was delivered
- How to verify
- Risks / Notes