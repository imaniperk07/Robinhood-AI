# Changelog

## v0.1 — GitHub + Streamlit Cloud deployment

- Moved from local-only Streamlit runs to a GitHub repo deployed on Streamlit
  Community Cloud, so the app is reachable from any browser (including phone)
  without needing this Mac running.
- Restructured `database.py` behind a `Storage` interface with `SQLiteStorage`
  as the v0.1 backend — swapping in a persistent shared database later means
  writing a new class, not touching every caller.
- Reworked the Portfolio tab's SnapTrade integration to use the SDK directly
  instead of a local-only Node CLI, so it works on a remote host. Along the
  way, fixed a client-auth bug (missing `SnapTradeAuth` wiring meant every
  authenticated call silently failed) and discovered the app's personal
  SnapTrade key needs no separate per-user credentials.
- Added a lightweight GitHub Actions CI workflow: installs dependencies,
  compiles every file, and import-checks every module (except `app.py`) on
  every push/PR.

### Known limitation
SQLite and the local JSON runtime files are ephemeral on Streamlit Cloud's
free tier — wiped on redeploy/restart. Content Signals history, AI Cost
Tracker history, Memory Agent's saved profile, and the trading journal won't
persist long-term on the cloud version until a v0.2 storage backend is added.
