# ITLF RSS v2

Replace `itlf_rss.py` in the GitHub repository. Keep your existing `.github/workflows/rss.yml` and its 5-minute schedule. Python 3.10+ required (`zoneinfo` uses the runner's timezone database).

Run locally: `python itlf_rss.py`.

Outputs: `rss.xml` and `state.json` (keep both committed between successful runs).

Cautions: DATEX II location formats vary; this parser accepts explicit department codes or coordinate pairs within an approximate Lorraine rectangle. This can include neighboring territory and does not constitute precise departmental filtering. `aligned` / `opposite` are left as technical direction codes rather than falsely assigning a destination. Recurring validity schedules and road-network reference tables are not resolved. Check the output against real source events before public alerting. Missing records are removed after two successful snapshots; download failures preserve existing output. No foreign-country source is included.
