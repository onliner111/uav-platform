# 城市低空综合治理与应急指挥平台
# 运维部署手册（V2.0）

- 文档版本：V2.0
- 适用对象：运维工程师、实施工程师
- 适用范围：`phase-01` 至 `phase-15` 已实现能力
- 更新日期：2026-02-25

---

## 1. 部署说明

当前版本采用单体 FastAPI + 插件适配器架构，容器化部署，依赖：

1. PostgreSQL（PostGIS 镜像）
2. Redis
3. 应用服务 `app`
4. 工具服务 `app-tools`（OpenAPI 导出、演示脚本、冒烟脚本）
5. OpenAPI 生成服务 `openapi-generator`

---

## 2. 环境要求

### 2.1 主机要求（建议）

- CPU：4 核及以上
- 内存：8 GB 及以上
- 磁盘：50 GB 可用空间
- 操作系统：Linux / Windows（支持 Docker Desktop）

### 2.2 软件要求

- Docker 24+
- Docker Compose v2+
- Git

---

## 3. 目录与关键文件

- 环境变量模板：`.env.example`
- 编排文件：`infra/docker-compose.yml`
- 迁移配置：`alembic.ini`、`infra/migrations/*`
- 运维脚本：`infra/scripts/*`
- 构建与验证入口：`Makefile`

---

## 4. 环境变量配置

复制并修改环境变量：

```bash
cp .env.example .env
```

关键变量：

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DB_PORT`
- `REDIS_PORT`
- `APP_PORT`
- `JWT_SECRET`
- `JWT_ALGORITHM`

生产建议：

1. `POSTGRES_PASSWORD` 使用高强度密码
2. `JWT_SECRET` 使用 32 位以上随机字符串
3. 对外端口按安全策略限制来源 IP

---

## 5. 首次部署流程

以下示例在仓库根目录执行。

### 5.1 启动服务

```bash
docker compose -f infra/docker-compose.yml up -d --build app app-tools db redis
```

### 5.2 执行数据库迁移

```bash
docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head
```

### 5.3 健康检查

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

---

## 6. 日常运维命令

### 6.1 服务管理

启动：

```bash
docker compose -f infra/docker-compose.yml up -d
```

停止：

```bash
docker compose -f infra/docker-compose.yml down
```

查看状态：

```bash
docker compose -f infra/docker-compose.yml ps
```

查看日志：

```bash
docker compose -f infra/docker-compose.yml logs -f app db redis
```

### 6.2 质量门禁命令

```bash
docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts
docker compose -f infra/docker-compose.yml run --rm --build app mypy app
docker compose -f infra/docker-compose.yml run --rm --build app pytest -q
docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head
docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export
```

### 6.3 E2E 与验收验证

```bash
docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py
docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py
docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase15_kpi_open_platform.py
```

---

## 7. 发布升级流程

### 7.1 升级前

1. 备份数据库
2. 记录当前镜像版本和 Git 提交号
3. 在测试环境预演迁移脚本与冒烟脚本

### 7.2 执行升级

1. 拉取新代码
2. 重建镜像并启动服务
3. 执行迁移
4. 执行质量门禁与冒烟验证

示例：

```bash
docker compose -f infra/docker-compose.yml up -d --build app app-tools db redis
docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head
docker compose -f infra/docker-compose.yml run --rm --build app pytest -q
docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py
```

---

## 8. 数据备份与恢复

### 8.1 PostgreSQL 备份

```bash
docker compose -f infra/docker-compose.yml exec -T db \
  pg_dump -U ${POSTGRES_USER:-uav} ${POSTGRES_DB:-uav_platform} > backup_$(date +%F_%H%M%S).sql
```

### 8.2 PostgreSQL 恢复

```bash
cat backup_xxx.sql | docker compose -f infra/docker-compose.yml exec -T db \
  psql -U ${POSTGRES_USER:-uav} ${POSTGRES_DB:-uav_platform}
```

### 8.3 导出文件归档

系统导出文件目录：

- `logs/exports/`

建议纳入定期归档策略。

---

## 9. 监控与告警建议

至少覆盖以下指标：

1. `app` 进程可用性与重启次数
2. PostgreSQL 连接数、慢查询、磁盘
3. Redis 内存占用
4. API 5xx 比例
5. WebSocket 连接数

建议集成平台：

- Prometheus + Grafana（基础监控）
- Sentry（应用异常追踪）

---

## 10. 故障排查手册

### 10.1 `readyz` 失败

步骤：

1. `docker compose -f infra/docker-compose.yml ps` 查看 db/redis 是否 healthy
2. 检查 `DATABASE_URL`、`REDIS_URL`
3. 查看 `app` 日志定位错误堆栈

### 10.2 迁移失败

步骤：

1. 查看 Alembic 报错
2. 核对数据库版本表 `alembic_version`
3. 在测试环境重放迁移脚本

### 10.3 500 错误

步骤：

1. `docker compose -f infra/docker-compose.yml logs app --tail=200`
2. 对照最近变更（代码/配置/迁移）
3. 必要时回滚到上个稳定版本

### 10.4 UI 页面空白

步骤：

1. 检查 token 是否有效
2. 检查对应权限是否具备
3. 浏览器控制台检查静态资源加载错误

---

## 11. 安全加固建议

1. 禁止默认密码进入生产
2. 强制 HTTPS 与网关鉴权
3. 收敛数据库和 Redis 对外暴露范围
4. 定期轮换 `JWT_SECRET`
5. 审计与导出文件应纳入加密归档策略

---

## 12. 生产验收清单

上线前确认：

1. 数据库迁移成功
2. `healthz/readyz` 正常
3. 质量门禁通过（lint/typecheck/test）
4. `verify_smoke.py` 通过
5. 管理员账号可登录，核心 UI 可访问
6. 关键模块可访问：`assets`、`compliance`、`outcomes`、`map`、`task-center`、`ai`、`kpi`、`open-platform`
7. 审计与报表导出可用

---

## 13. 接口清单附录

详细接口请参见 `docs/API_Appendix_V2.0.md`。

建议将该附录作为联调验收与上线回归的核对清单。

