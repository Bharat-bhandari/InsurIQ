# PolicyDesk VPS deploy fixes (2026-06-07)

Two deploy/transport bugs. App logic was fine; these are transport/proxy/config.

---

## BUG 1 — MCP transport mismatch (405 Method Not Allowed)

**Root cause.** `src/mcp_server/server.py` served the MCP protocol over **SSE**
(`GET /sse` + `POST /messages/`). The backend MCP client and the TrueFoundry MCP
Gateway speak **streamable-HTTP** (`POST /mcp`). Every gateway `initialize` /
`tools/call` POST hit the SSE endpoint → **405**, surfaced in the graph as
`[mcp] remote call get_waiting_periods failed: unhandled errors in a TaskGroup`,
so the tool degraded on every call.

**Code fix (done).** The server now serves **streamable-HTTP at `POST /mcp`**
(`mcp.streamable_http_app()`, `streamable_http_path="/mcp"`, `/health` via
`@mcp.custom_route`). Verified locally: `initialize` returns 200 (not 405) and a
full `get_waiting_periods` round-trip through `mcp_client.fetch_via_mcp` returns
real keyed-Evidence.

**VPS / dashboard steps (manual):**

1. Redeploy the `mcp` container (`docker compose up -d --build mcp`). Log line
   should now read `serving streamable-HTTP on http://0.0.0.0:8081/mcp`.
2. **nginx for the MCP subdomain** — proxy to `/mcp` and **disable buffering**
   (streamable-HTTP uses `text/event-stream` chunked responses):

   ```nginx
   location /mcp {
       proxy_pass http://127.0.0.1:8081/mcp;
       proxy_http_version 1.1;
       proxy_set_header Host $host;
       proxy_set_header Connection "";
       proxy_buffering off;          # required: do not buffer the stream
       proxy_read_timeout 3600s;
       chunked_transfer_encoding off;
   }
   ```

3. **TFY MCP Gateway registration (dashboard):** set this MCP server's URL to the
   public streamable endpoint `https://<mcp-subdomain>/mcp` and transport to
   **StreamableHttp** (NOT SSE). Re-run "initialize" in the How-To-Use panel; it
   must return 200.
4. **Backend `.env`** (deployed): keep `USE_MCP_FOR=get_waiting_periods`, set
   `TFY_MCP_URL` to the TFY gateway MCP endpoint for this server (streamable-HTTP,
   path ends `/mcp` — anything NOT containing `/sse` makes the client use
   streamable-HTTP), and `TFY_MCP_TOKEN` to the scoped gateway token.

---

## BUG 2 — browser "TypeError: Failed to fetch" → silent cached mock

**Root cause.** **Duplicate `Access-Control-Allow-Origin` headers.** Both nginx
(`add_header`) AND FastAPI's `CORSMiddleware` (configured with `allow_origins=["*"]`)
emitted CORS headers. A real browser sends `Origin`, so the response carried:

```
access-control-allow-origin: *                                  (FastAPI)
access-control-allow-origin: https://insuriq.himalayandev.tech  (nginx)
access-control-allow-credentials: true                          (nginx)
```

Browsers reject any response with **two** `Access-Control-Allow-Origin` values →
`TypeError: Failed to fetch` *before* the body is read. curl without an `Origin`
header only saw nginx's single header, so it "worked" — masking the bug. The
frontend's catch-handler then showed the SAME cached mock for every question.
(`ACAO: *` together with `allow-credentials: true` is also an illegal combo.)

**Code fix (done).**
- `src/api/app.py` is now the **single CORS authority**: reflects the specific
  origins from `CORS_ORIGINS` (never `*`), `allow_credentials=True`. Verified
  locally: exactly one `ACAO`, preflight 200, disallowed origins get none.
- Root `.env` `CORS_ORIGINS` corrected from the API's own domain to the **frontend
  origin** `https://insuriq.himalayandev.tech,http://localhost:3002` (compose
  passes this through and it overrides the backend env_file value).
- Frontend cached fallback is now **loudly labelled** (orange "Showing a CACHED
  answer — backend unreachable" banner + reason) so it can never masquerade as a
  live answer.

**VPS step (manual, required):** **remove the CORS `add_header` block from the
nginx server for `api.insuriq.himalayandev.tech`** so FastAPI is the only source.
Delete lines like:

```nginx
add_header Access-Control-Allow-Origin  ...;
add_header Access-Control-Allow-Credentials true;
add_header Access-Control-Allow-Methods ...;
add_header Access-Control-Allow-Headers ...;
# and any `if ($request_method = OPTIONS) { return 204; }` CORS shim
```

Then `nginx -t && systemctl reload nginx` and redeploy the backend container.

After this there must be exactly **one** `Access-Control-Allow-Origin:
https://insuriq.himalayandev.tech` in the `/ask` response when called with that
Origin.
