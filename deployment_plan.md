# Deployment Plan: Smruti AgentX (Multi-Agent Chatbot)

To make this project accessible "anywhere," we will deploy it to **Railway**, which is ideal for Python-based full-stack applications with managed databases and Redis.

## Deployment Architecture

1.  **Backend Service (FastAPI)**:
    *   Hosts the API.
    *   Serves the Primary HTML UI (Figma Mock).
    *   Connects to PostgreSQL (Persistence) and Redis (State/Queue).
2.  **Frontend Service (Streamlit)**:
    *   Hosts the secondary Streamlit dashboard.
    *   Connects to the Backend API.
3.  **Infrastructure**:
    *   **PostgreSQL**: For user accounts and chat history.
    *   **Redis**: For real-time state and caching.

---

## Step 1: Prepare the Repository for Railway

We need to ensure Railway knows how to build both parts of the app. Since they are in subdirectories, we can use Railway's **Multi-Service** capability.

### 1.1 Update `railway.toml`
Currently, the `railway.toml` only handles the backend. We will update it to be more robust or provide a `Dockerfile`.

## Step 2: Environment Variables
You will need to set these in Railway's "Variables" tab for both services:

| Variable | Description |
| :--- | :--- |
| `DATABASE_URL` | Provided by Railway Postgres |
| `REDIS_URL` | Provided by Railway Redis |
| `JWT_SECRET` | A random long string for auth |
| `GROQ_API_KEY` | Your Groq key (required for core LLM) |
| `PINECONE_API_KEY` | Required for RAG / Document upload |
| `PINECONE_INDEX_NAME` | Your Pinecone index name |
| `PINECONE_ENVIRONMENT` | Your Pinecone region |
| `SUPABASE_URL` | (Optional) For OAuth |
| `SUPABASE_ANON_KEY` | (Optional) For OAuth |

## Step 3: Deployment Steps

### Method A: Railway CLI (Recommended)
1.  Install Railway CLI: `npm i -g @railway/cli`
2.  Login: `railway login`
3.  Initialize: `railway init`
4.  Add Redis/Postgres via the Railway Dashboard.
5.  Deploy: `railway up`

### Method B: Railway Dashboard (GitHub Link)
1.  Push your code to a GitHub repository.
2.  Go to [Railway.app](https://railway.app/).
3.  Create a "New Project" -> "Deploy from GitHub repo".
4.  Add the **Backend** service:
    *   Root Directory: `backend`
    *   Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5.  Add the **Frontend** service (Optional):
    *   Root Directory: `frontend`
    *   Start Command: `streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`
### Method C: Docker Compose with Nginx (Production Ready)
1. Ensure Docker and Docker Compose are installed.
2. Run `docker-compose up --build`.
3. Nginx will now handle all routing on port `80`:
   - **Streamlit Frontend**: `http://your-ip/`
   - **Backend UI**: `http://your-ip/ui-final`
   - **API Docs**: `http://your-ip/api/docs` (Proxied)

---

## Action Items for Me (The AI)

1.  [x] **Create Deployment Plan Document**
2.  [x] **Optimize Backend Config**: Added `field_validator` for `DATABASE_URL` in `config.py`.
3.  [x] **Create Dockerfiles**: Created `backend/Dockerfile`, `frontend/Dockerfile`, and `nginx/Dockerfile`.
4.  [x] **Verify Streamlit Connection**: Updated `frontend/streamlit_app.py` to use `BACKEND_URL`.
5.  [x] **Health Check Fix**: Verified `/health` endpoint is Railway-ready.
6.  [x] **Orchestration**: Created `docker-compose.yml` with Nginx reverse proxy.
