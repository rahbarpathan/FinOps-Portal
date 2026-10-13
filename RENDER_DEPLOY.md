# 🚀 Deploying CentrAlign FinOps Portal to Render

This guide outlines how to deploy the **FinOps Portal & Autonomous AI Task Worker** to **Render** using Docker.

---

## 📦 What Was Prepared for Render

1. **[`Dockerfile`](file:///c:/Users/rahba/Downloads/FinOps%20Portal/Dockerfile)**:
   - Python 3.12 slim base with Playwright and Chromium dependencies installed (`playwright install --with-deps chromium`).
   - Linux container-optimized Chrome flags (`--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`).
2. **[`render.yaml`](file:///c:/Users/rahba/Downloads/FinOps%20Portal/render.yaml)**:
   - Render Blueprint file for one-click setup.
   - Automatically defines the Docker web service, health check at `/api/ground-truth`, and environment variables.
3. **[`.dockerignore`](file:///c:/Users/rahba/Downloads/FinOps%20Portal/.dockerignore)**:
   - Excludes `.venv`, caches, and local configuration for fast builds.
4. **Dynamic Port & Host Binding**:
   - [`run.py`](file:///c:/Users/rahba/Downloads/FinOps%20Portal/run.py), [`agent/verifier.py`](file:///c:/Users/rahba/Downloads/FinOps%20Portal/agent/verifier.py), and [`agent/llm.py`](file:///c:/Users/rahba/Downloads/FinOps%20Portal/agent/llm.py) now dynamically read Render's `$PORT` and `$PORTAL_URL`.

---

## 🛠️ Step-by-Step Deployment Instructions

### Step 1: Commit and Push Changes to GitHub

Run these commands in your terminal to push the deployment configuration to your repository:

```bash
git add Dockerfile .dockerignore render.yaml run.py agent/llm.py agent/tools.py agent/verifier.py env/templates/create_bill.html .env.example
git commit -m "Add Docker and Render deployment setup with Groq LLM integration"
git push origin main
```

---

### Step 2: Deploy on Render Dashboard

#### Option A: One-Click via Blueprint (Recommended)
1. Go to **[dashboard.render.com](https://dashboard.render.com/)**.
2. Click **New +** (top right) and select **Blueprint**.
3. Connect your GitHub repository: **`rahbarpathan/FinOps-Portal`**.
4. Render will read [`render.yaml`](file:///c:/Users/rahba/Downloads/FinOps%20Portal/render.yaml).
5. In the Environment Variables screen:
   - Enter `GROQ_API_KEY`: `<your-groq-api-key>`
6. Click **Apply**. Render will build the Docker container and deploy the app!

#### Option B: Deploy as a Standard Web Service
1. In Render Dashboard, click **New +** -> **Web Service**.
2. Select your repository: **`rahbarpathan/FinOps-Portal`**.
3. Configure the service:
   - **Name**: `finops-portal`
   - **Runtime**: **Docker**
   - **Instance Type**: **Free** or **Starter**
4. Under **Environment Variables**, add:
   - `GROQ_API_KEY` = `<your-groq-api-key>`
   - `GROQ_MODEL` = `openai/gpt-oss-120b`
   - `BROWSER_HEADLESS` = `true`
5. Click **Create Web Service**.

---

## 🌐 After Deployment

Once deployed, Render will provide a live URL (e.g. `https://finops-portal.onrender.com`):
- **Vendor Inbox**: `https://<your-app>.onrender.com/inbox`
- **Finance System**: `https://<your-app>.onrender.com/bills`
- **Agent Live Cockpit**: `https://<your-app>.onrender.com/agent`
- **Ground-Truth API**: `https://<your-app>.onrender.com/api/ground-truth`
