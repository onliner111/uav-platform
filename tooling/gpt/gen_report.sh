mkdir -p logs

codex --full-auto "
Generate a full system snapshot document as logs/gpt_SYSTEM_SNAPSHOT.md.
The document must include:
1. Project structure tree (max depth 4)
2. List of main modules and responsibilities
3. Database models (tables + fields)
4. API endpoints summary
5. Background jobs or event flows
6. Docker services definition
7. Current migrations status
8. Known TODO / FIXME markers in code
9. Test coverage summary (if available)
10. Git branch + last 10 commits summary

Generate logs/gpt_ARCHITECTURE_RISK_REPORT.md.
Analyze:
- Tight coupling areas
- Violations of governance/AGENTS.md rules
- Potential scalability risks
- Data model design risks
- Permission model weaknesses
- Missing test coverage areas
- Dangerous technical debt

Do not modify any code.
Only generate the documentation file in logs/.
"
