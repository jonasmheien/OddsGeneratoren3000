The scheduled GitHub Actions job writes `active.json` here and archives earlier
editions in `history/YYYY-MM-DD.json`. Do not manually populate or overwrite
state while a workflow runs. This folder contains public football predictions,
not secrets. Once an edition is published, the result-status job updates only
outcome fields; it does not silently substitute new tips or odds.
