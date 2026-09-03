"""
2026-09-03-build-dashboard.py
Inject data/2026-09-03-projections.json into the dashboard template and write two files:
  2026-09-03-greece-projections-dashboard.html          full standalone document (open in any browser)
  2026-09-03-greece-projections-dashboard.artifact.html body-only version for publishing as a claude.ai artifact
Re-run after 2026-09-03-models.py.
"""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__))
data = open(os.path.join(HERE, "data", "2026-09-03-projections.json"), encoding="utf-8").read()
tpl = open(os.path.join(HERE, "templates", "dashboard-template.html"), encoding="utf-8").read()
body = tpl.replace("/*__DATA__*/null", data)
open(os.path.join(HERE, "2026-09-03-greece-projections-dashboard.artifact.html"), "w", encoding="utf-8").write(body)
full = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style></head><body>'
        + body + '</body></html>')
open(os.path.join(HERE, "2026-09-03-greece-projections-dashboard.html"), "w", encoding="utf-8").write(full)
print("dashboard written", len(full)//1024, "KB")
