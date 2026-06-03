## VPS Deployment Plan

Target ports:

- Frontend: `3002`
- Backend: `8082`

### What changed in the project

- The backend now reads `HOST`, `PORT`, `RELOAD`, and `CORS_ORIGINS` from the environment.
- The frontend now reads `NEXT_PUBLIC_API_BASE_URL` so it can point to the VPS backend instead of a hardcoded localhost URL.
- The frontend scripts now bind to `0.0.0.0:3002`.

### Server environment

Set these variables on the VPS:

```bash
GROQ_API_KEY=your_key_here
HOST=0.0.0.0
PORT=8082
RELOAD=false
CORS_ORIGINS=http://your-server-domain:3002,http://127.0.0.1:3002
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8082
```

### Suggested run order

1. Start the backend on `8082`.
2. Build the frontend with `NEXT_PUBLIC_API_BASE_URL` set.
3. Start the frontend on `3002`.
4. Put Nginx in front if you want TLS or public routing.

### Docker Deployment

The repo now includes Dockerfiles for both apps and a root `docker-compose.yml` that publishes the services on localhost ports only:

- Backend: `127.0.0.1:8082`
- Frontend: `127.0.0.1:3002`

Use this flow on the VPS:

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Set `GROQ_API_KEY` in `.env` before starting the stack. The frontend is built with `NEXT_PUBLIC_API_BASE_URL=/api`, so Nginx should proxy `/api` to the backend container and `/` to the frontend container.

### Notes

- Do not run the backend with reload enabled in production.
- If you use a domain for the frontend, add it to backend CORS.
- Keep `GROQ_API_KEY` only on the server.
