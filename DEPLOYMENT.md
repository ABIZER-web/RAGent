# Deploying RAGent — Free Hosting Guide (Render + Streamlit Community Cloud)

This deploys the backend (FastAPI) on **Render** and the frontend (Streamlit) on
**Streamlit Community Cloud** — both free.

⚠️ **Important limitation:** Render's free tier has an ephemeral filesystem —
uploaded documents, chats, and accounts will be wiped whenever the service
restarts or redeploys (roughly every time it spins down from inactivity, or
you push new code). This is fine for a demo/portfolio project. If you need
data to actually persist, you'd need a paid Render disk or an external
database — not covered here.

---

## Step 1 — Push the code to GitHub

```bash
cd RAGent10
git init
git add .
git commit -m "Initial commit"
```

Create a new **empty** repository on github.com (don't initialize it with a
README), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

Double-check your `.env` file did **not** get committed (it shouldn't — it's
in `.gitignore`). Run `git status` and confirm `.env` isn't listed as tracked.

---

## Step 2 — Deploy the backend on Render

1. Go to **render.com** and sign in with GitHub
2. Click **New +** → **Web Service**
3. Connect your `RAGent` repository
4. Render should auto-detect the settings from `render.yaml`. If not, set manually:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
5. Under **Environment Variables**, add:
   | Key | Value |
   |---|---|
   | `GEMINI_API_KEY` | your real Gemini key |
   | `APP_USERNAME` | your chosen admin username |
   | `APP_PASSWORD` | your chosen admin password |
   | `ALLOWED_ORIGINS` | `*` for now (tighten later — see Step 4) |
6. Click **Create Web Service**

First deploy takes a few minutes (installing torch/sentence-transformers is
the slow part). Once live, note your backend URL, e.g.:
```
https://ragent-backend.onrender.com
```

**Test it directly:** visit `https://ragent-backend.onrender.com/` in your
browser — you should see `{"status":"RAGent API is running"}`.

⚠️ **Free tier note:** the service spins down after ~15 minutes of no traffic
and takes ~30-50 seconds to wake back up on the next request. The first
request after idle time will feel slow — that's normal, not a bug.

⚠️ **Memory note:** Render's free tier gives 512MB RAM. Loading the embedding
model + cross-encoder reranker is usually fine, but if you see the service
crash/restart under load, that's likely an out-of-memory issue — the fix is
upgrading to a paid Render plan with more RAM, not a code bug.

---

## Step 3 — Deploy the frontend on Streamlit Community Cloud

1. Go to **share.streamlit.io** and sign in with GitHub
2. Click **New app**
3. Select your repository, branch `main`
4. **Main file path:** `frontend/streamlit_app.py`
5. Before deploying, click **Advanced settings** and add a secret:
   ```toml
   API_URL = "https://ragent-backend.onrender.com"
   ```
   (use your actual Render URL from Step 2)
6. Click **Deploy**

Streamlit Cloud will use `frontend/requirements.txt` automatically (it looks
for a requirements file in the same folder as the main app file first) — this
keeps the frontend install lightweight since it doesn't need torch/embeddings
libraries, those only run on the backend.

Your app will be live at something like:
```
https://your-app-name.streamlit.app
```

---

## Step 4 — Lock down CORS (optional but recommended)

Once you know your Streamlit Cloud URL, go back to Render → your backend
service → Environment → update `ALLOWED_ORIGINS` to your actual frontend URL
instead of `*`:
```
ALLOWED_ORIGINS=https://your-app-name.streamlit.app
```
Save — Render will redeploy automatically.

---

## Step 5 — Test the live site

1. Open your Streamlit Cloud URL
2. Register a new account (the admin account from your env vars also works)
3. Upload a document, ask a question
4. If the first request times out — that's the Render free-tier cold start
   (30-50s). Wait and try again; subsequent requests will be fast.

---

## Updating your deployed app later

Both platforms auto-redeploy on every `git push` to `main`:
```bash
git add .
git commit -m "some change"
git push
```
Render and Streamlit Cloud will pick it up automatically within a minute or two.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Frontend shows "Backend not reachable" | Wrong `API_URL` secret, or Render service is still cold-starting — wait 60s and refresh |
| Backend crashes/restarts randomly | Likely OOM on the free 512MB tier |
| Uploaded documents disappear | Expected — free tier has no persistent disk |
| "Model not found" errors from Gemini | Same fix as local: check `app/generator.py`'s `MODEL` constant is set to `"gemini-flash-latest"`, and your `GEMINI_API_KEY` env var on Render is correct |
| Streamlit Cloud build fails | Check the build log — usually a typo in `frontend/requirements.txt` or the secrets TOML format |
