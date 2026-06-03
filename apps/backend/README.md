## Backend Server

The FastAPI app runs on port `8082` by default.

### Development / Server Run

```bash
python main.py
```

### Environment Variables

Set these on the server before starting the app:

```bash
GROQ_API_KEY=your_key_here
HOST=0.0.0.0
PORT=8082
RELOAD=false
CORS_ORIGINS=http://localhost:3002,http://127.0.0.1:3002
```

If the frontend is served from a domain, add that origin to `CORS_ORIGINS` as well.

### Docker

Build and run the backend container with the root Compose setup:

```bash
docker compose build backend
docker compose up -d backend
```
