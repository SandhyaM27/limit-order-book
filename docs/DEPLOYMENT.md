# Deployment

What is deployed: the **Streamlit dashboard** (a simulation demo). The engine is
a library with no network API. It is not an exchange and holds no real data.

## 0. Before anything: local checks
```bash
make check        # ruff + mypy + pytest
make run          # http://localhost:8501
```

## 1. Streamlit Community Cloud (easiest, free)
1. Push the repo to GitHub (see `docs/GIT_GUIDE.md`).
2. https://share.streamlit.io -> New app -> pick repo, branch `main`,
   main file `dashboard/app.py`, Python 3.12 (Advanced settings).
3. Deploy. Dependencies come from `requirements.txt`; `dashboard/app.py`
   adds `src/` to `sys.path`, so no install step is needed.
4. Put the resulting URL in the README.

## 2. Docker (any VPS, Fly.io, Cloud Run, etc.)
```bash
docker build -t lob-dashboard .
docker run --rm -p 8501:8501 lob-dashboard        # or: docker compose up --build
```
The image runs as a non-root user and has a healthcheck on `/_stcore/health`.

## 3. Render.com
New -> Blueprint -> select the repo. `render.yaml` builds the Dockerfile.

## 4. Container registry
Tag a release: `git tag v0.1.0 && git push --tags`. The `Publish image` workflow
pushes `ghcr.io/<you>/limit-order-book:v0.1.0`.

## Operational notes
- **Resources:** each browser session keeps its own simulation in memory
  (`st.session_state`). The dashboard caps a run at 200k events; give the
  container about 1 GB RAM and expect a few concurrent users, not many.
- **Public exposure:** there is no authentication and no persistence. If the
  app is public, keep the caps in `dashboard/app.py`.
- **HTTPS:** terminate TLS at your platform's proxy (Streamlit Cloud, Render,
  Cloud Run do this). Don't expose port 8501 directly on the internet.
- **Config:** `.streamlit/config.toml` (headless, XSRF on, telemetry off).
- **Rollback:** redeploy the previous git tag / image tag.
- **Monitoring:** platform health check on `/_stcore/health`; logs go to stdout.
