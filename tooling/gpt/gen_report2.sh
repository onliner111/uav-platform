mkdir -p logs

codex --full-auto "
Generate logs/gpt_ARCHITECTURE_RISK_REPORT.md.

Analyze:
- Tight coupling areas
- Violations of governance/AGENTS.md rules
- Potential scalability risks
- Data model design risks
- Permission model weaknesses
- Missing test coverage areas
- Dangerous technical debt

Do not change code.
Only generate the report in logs/.
"
