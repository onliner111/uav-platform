# UAV Platform

运行方式1：完全绕过 沙箱限制、所有人工确认、权限控制
codex --dangerously-bypass-approvals-and-sandbox

运行方式2：尽量自动执行，只修改工作目录下的文件
codex -a never -s workspace-write


重启先读取 `phases/resume.md`，并按其中 Next TODO 继续执行。

Key directories:
- `app/`
- `infra/`
- `tests/`
- `openapi/`
- `phases/`
- `logs/`
- `docs/`
- `governance/`
- `tooling/`
