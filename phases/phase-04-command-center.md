# Phase 04 — 指挥大屏系统

## Goal

实现可展示的大屏系统。

---

## Scope

- 全屏页面
- 实时统计
- WebSocket 聚合
- 热力图

禁止：

- 不引入前端框架
- 不重构 telemetry

---

# UI

/ui/command-center

必须展示：

- 在线设备数
- 今日巡查次数
- 问题总数
- 实时告警
- 地图实时刷新

---

# API

GET /api/dashboard/stats  
WebSocket /ws/dashboard  

---

# Demo

demo_command_center_phase4.py

---

# Acceptance

- 页面实时刷新
- 统计数据正确