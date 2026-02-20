# Phase 03 — 应急快速建任务（3分钟机制）

## Goal

实现应急模式：

事件创建 → 选区域 → 自动建任务 → 多机跟踪

---

## Scope

- incident 表
- emergency_mode 任务创建
- 优先级字段
- UI 应急模式入口

禁止：

- 不引入视频流
- 不做多部门协同

---

# Data Model

## incidents

- id UUID
- tenant_id UUID
- title VARCHAR(200)
- level VARCHAR(20)
- location GEOMETRY(POINT, 4326)
- status VARCHAR(20)
- created_at TIMESTAMPTZ

---

# API

POST /api/incidents  
GET /api/incidents  
POST /api/incidents/{id}/create-task  

---

# UI

/ui/emergency

- 地图圈选
- 一键建任务
- 任务优先级显示

---

# Demo

demo_emergency_phase3.py

---

# Acceptance

- 3分钟内创建任务
- mission_id 关联成功