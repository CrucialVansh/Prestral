# Deploy Prestral (optional / cloud)

**Local development** lives on **`main`** — see the root [README.md](README.md).

This file is for hosting a public demo. **Host:** [Render](https://render.com) free Web Service — one Docker container = React + FastAPI. **$0 hosting** (sleeps after ~15 min idle). You still pay Mistral for API usage.

## Deploy

```bash
git push -u origin deploy
```

1. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** (repo + `deploy` branch)  
   or **Web Service** → Docker → root `Dockerfile`
2. Set **`MISTRAL_API_KEY`**
3. Open the `*.onrender.com` URL (UI + `/api` same-origin)

Health: `GET /health`

## Local Docker smoke test

```bash
docker build -t prestral .
docker run --rm -p 8000:8000 -e MISTRAL_API_KEY=sk-... prestral
# http://localhost:8000
```

## Notes

| Topic | Detail |
|-------|--------|
| Sleep | Free tier cold-starts after idle |
| Memory | In-memory decks — sleep/redeploy clears data |
| Slide PNGs | LibreOffice optional. Without it, Pillow compositor still builds slide PNGs from shapes (good enough for free deploy). |
| Drive | Set `GOOGLE_*` + redirect `https://YOUR.onrender.com/api/storage/google/callback` |
