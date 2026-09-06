# Web deployment

## Local run

From the repository root:

```powershell
python -m uvicorn web.backend.app:app --reload --port 8000
```

Open `web/frontend/index.html` with a static server. For example:

```powershell
python -m http.server 5173 --directory web/frontend
```

The frontend defaults to `http://localhost:8000`. Set `window.API_BASE` in `app.js` to the deployed API URL before publishing the frontend.

## Public deployment

1. Push this repository to GitHub, excluding `config.json`, `cookies_store.json`, and `articles.json` from commits.
2. Deploy `web/render.yaml` on Render or deploy `web/backend/app.py` to another Python host.
3. Set the backend environment variable `CORS_ORIGINS` to the GitHub Pages URL.
4. Put the deployed backend URL in `web/frontend/app.js` as `window.API_BASE`.
5. Publish `web/frontend` with GitHub Pages.

The backend must have a persistent data volume or database for articles and cookies. Do not put Cookie values in frontend code or GitHub Pages.
