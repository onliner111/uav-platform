# Phase 05 — 合规与留痕强化

## Goal

满足政府验收要求。

---

## Scope

- approval_records 表
- 审批流
- 禁飞区校验
- 审计导出

---

# Data Model

## approval_records

- id UUID
- tenant_id UUID
- entity_type VARCHAR(50)
- entity_id UUID
- status VARCHAR(20)
- approved_by UUID
- created_at TIMESTAMPTZ

---

# API

POST /api/approvals  
GET /api/approvals  

---

# Demo

demo_compliance_phase5.py

---

# Acceptance

- 审批可追溯
- 审计日志可导出