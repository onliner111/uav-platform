# Phase 02 — 问题闭环流转（执法核心）

## Goal

实现问题闭环流程：

巡查成果 → 生成问题单 → 指派 → 整改 → 复核 → 关闭

---

## Scope

- defect 表
- defect_actions 表
- 状态机流转
- 复核任务生成
- 闭环统计 API
- UI 问题管理页面

禁止：

- 不引入工单外部系统
- 不引入审批流（Phase 05）
- 不实现应急模式

---

# Data Model

## defect

- id UUID PK
- tenant_id UUID
- observation_id UUID FK
- title VARCHAR(200)
- description TEXT
- severity INT
- status VARCHAR(20)
  - OPEN
  - ASSIGNED
  - IN_PROGRESS
  - FIXED
  - VERIFIED
  - CLOSED
- assigned_to UUID nullable
- created_at TIMESTAMPTZ

## defect_actions

- id UUID PK
- tenant_id UUID
- defect_id UUID FK
- action_type VARCHAR(50)
- note TEXT
- created_at TIMESTAMPTZ

---

# API

POST /api/defects/from-observation/{observation_id}  
GET /api/defects  
GET /api/defects/{id}  
POST /api/defects/{id}/assign  
POST /api/defects/{id}/status  
GET /api/defects/stats  

---

# UI

新增：

/ui/defects

功能：

- 列表筛选
- 状态切换
- 指派
- 查看历史操作

---

# Demo

demo_defect_phase2.py

流程：

1. 从 observation 生成 defect
2. assign
3. status 流转至 CLOSED
4. 验证统计数据

---

# Acceptance

- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q` 通过
- 问题可流转
- stats API 正确
