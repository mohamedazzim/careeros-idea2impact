**Start Guide**

1. Make sure Docker Desktop is running.
   The whole stack is designed to start through Docker Compose, so you do not need local Node or Python installs for the normal path.

2. Open a terminal at CareerOS.
   This is the repo root that contains docker-compose.yml.

3. Start the full stack.
   Run:

```powershell
docker compose up -d --build
```

   This starts:
   - PostgreSQL
   - Redis
   - Qdrant
   - Backend
   - Worker
   - Frontend

4. Wait for the containers to become healthy.
   Check status with:

```powershell
docker ps
```

   You want to see:
   - backend healthy
   - frontend healthy
   - db healthy
   - redis healthy
   - qdrant healthy
   - worker healthy or at least no crash loop

5. Open the app in your browser.
   Use:
   - Frontend: http://localhost:3000
   - Backend docs: http://localhost:8000/api/docs

6. Sign in from the frontend.
   The login page should now talk to the backend through the frontend proxy setup in frontend/next.config.mjs, so browser CORS issues should be avoided.

7. If you need to restart only one service:
   Run one of these:

```powershell
docker compose restart frontend
docker compose restart backend
docker compose restart worker
```

8. If something fails, check logs.
   Run:

```powershell
docker compose logs --tail 100 frontend
docker compose logs --tail 100 backend
docker compose logs --tail 100 worker
docker compose logs --tail 100 db redis qdrant
```

**What the key files do**

- docker-compose.yml starts the whole system and wires the services together.
- frontend/Dockerfile builds the Next.js frontend.
- backend/src/main.py sets backend middleware, including CORS.
- frontend/next.config.mjs proxies browser API calls through the frontend origin.
- frontend/src/app/layout.tsx loads the global styles so the UI is not plain HTML.

If you want, I can also write you a shorter “daily run” version with just the 3 commands you need most of the time.