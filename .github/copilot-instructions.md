# CSV Viewer – AI contributor quick guide

Concise, repo-specific rules to be productive in this project. Prefer exact paths and existing patterns below when adding code.

## Architecture and flows
- Full-stack app: React 18 + MUI (frontend), FastAPI (backend), Celery+Redis, OpenSearch. Data dir inside containers: `/app/data`.
- API base prefix is `/api` (not `/api/v1`), see `backend/main.py` and routers in `backend/api/`.
- File pipeline: `backend/utils/file_watcher.py` watches `/app/data` and on netspeed changes deletes all `netspeed_*` indices then triggers `tasks.index_all_csv_files`. Cooldown 30s, 2s write settle.
- Index naming: `netspeed_{sanitized_filename}` (e.g., `netspeed_netspeed_csv`, `netspeed_netspeed_csv_1`). Historical search uses `netspeed_*`.
- OpenSearch mappings live in `backend/utils/opensearch.py`. If mappings change, you must delete indices and rebuild via `GET /api/search/index/rebuild`.

## Run, build, debug
- Use `./app.sh start dev` for hot reload (frontend mounts `frontend/src,public`; backend mounts `backend/`). Wait ~30s after compose up before further commands.
- Dev ports via `.env.dev`: `FRONTEND_DEV_PORT`→3000 container, `BACKEND_DEV_PORT`→`BACKEND_PORT` (FastAPI). OpenSearch dev runs with security disabled; `OPENSEARCH_PASSWORD` is optional.
- Key logs/health: `./app.sh status`, `docker compose -f docker-compose.dev.yml logs -f backend|frontend|opensearch`, `curl :9200/_cluster/health`.

## Data and CSV specifics
- Files: `netspeed.csv` (current), `netspeed.csv.N` (history), `netspeed.csv_bak` (backup). Indexing order is current first, then all others; see `tasks/index_all_csv_files`.
- CSV formats: old(11 cols) and new(14 cols) auto-detected in `backend/utils/csv_utils.py`. Keep headers and desired column order from `DESIRED_ORDER`.

## APIs to know (FastAPI)
- Files: `/api/files/`, `/api/files/netspeed_info`, `/api/files/preview?limit=&filename=`, `/api/files/reindex`, `/api/files/reload_celery`.
- Search: `/api/search/?query=&field=&include_historical=`, `/api/search/index/all`, `/api/search/index/status/{task_id}`, `/api/search/index/rebuild`.
- Stats: `/api/stats/current`, `/api/stats/cities/debug`.
- Search work runs via Celery (`tasks.search_opensearch`) and is awaited with a short timeout; return shape includes `headers`, `data`, `took_ms`.

## Frontend conventions
- Axios uses relative paths (e.g., `/api/search/`), see `frontend/src/utils/apiConfig.js`.
- Hooks in `frontend/src/hooks/` expose `{ data, loading, error }` patterns (see `useSearchCSV.js`, `useFilePreview.js`, `useFiles.js`). Debounce search 1s.
- Components to mirror: `CSVSearch.js`, `FileTable.js`, `FilePreview.js`, `IndexingProgress.js`.

## Testing and commits
- Backend tests live in `tests/backend`; run with `python -m pytest tests/backend`. Tests are designed to run without live OpenSearch.
- Local Git hook `.git/hooks/pre-commit` auto-fixes whitespace/newlines, then runs backend tests and (optionally) frontend tests. Set `SKIP_FRONTEND_TESTS=1` to skip Jest in commits.
- The VS Code task “Commit with tests” calls `scripts/commit-with-tests.sh` which is deprecated and exits 1. Don’t use it; commit normally (hook runs tests).

## Pitfalls and tips
- Don’t introduce `/api/v1` paths; `API_V1_STR` is unused. Keep routes under `/api`.
- When changing mappings or index naming, call `/api/search/index/rebuild` to drop `netspeed_*` and re-index.
- Always use absolute `/app/data` inside backend; in dev, host path is mounted from `CSV_FILES_DIR`.
- Pagination/limits are primarily client-side; keep backend responses stable: `{success, message, headers, data, ...}`.

Key files: `backend/api/*.py`, `backend/tasks/tasks.py`, `backend/utils/{opensearch.py,file_watcher.py,csv_utils.py,index_state.py}`, `backend/models/file.py`, `frontend/src/hooks/*`, `frontend/src/components/*`, `docker-compose*.yml`, `app.sh`.
