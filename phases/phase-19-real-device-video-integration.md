# Phase 19 - 真实设备与视频接入

## 0. Basis
- Depends on: `phases/phase-18-outcomes-repository-object-storage.md`

## 1. Objective
打通真机、视频、遥测联动链路，形成“可真实接入、可演示、可回放”的运行基线。

## 2. Scope
- 真机接入（MAVLink / DJI 适配器）
- 视频接入（RTSP/WebRTC 网关）
- 遥测流与一张图联动展示
- Fake/Real 双模式切换
- 接入安全策略（签名、令牌、速率控制）

## 3. Out of Scope
- 全量设备协议覆盖
- 媒体中台深度转码能力

## 4. Deliverables
- 设备接入适配器抽象与最小实现
- 视频流接入配置与状态可观测接口
- 实时联动演示脚本（真机或模拟设备）
- 接入稳定性与边界测试

## 5. Acceptance
- 真实设备接入可稳定上报遥测
- 视频流可在态势页稳定展示
- Fake/Real 切换不破坏业务流程
- 接入链路无跨租户越权

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 真机+视频联动演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞真实落地）：
  - `19-WP1` 设备接入适配器最小链路
  - `19-WP2` 视频接入与态势联动最小链路
- P1（随后完成，形成稳定演示能力）：
  - `19-WP3` Fake/Real 双模式切换 + 接入鉴权与限流治理
- P2（可延后到本阶段后半）：
  - 在 `19-WP3` 基础上补齐多机并发接入与抖动优化
- 执行顺序：`P0 -> P1 -> P2 -> 19-WP4`

## 8. Execution Progress

- [x] 19-WP1 设备接入最小链路
- [x] 19-WP2 视频接入与态势联动
- [x] 19-WP3 模式切换与接入治理
- [x] 19-WP4 验收关账
