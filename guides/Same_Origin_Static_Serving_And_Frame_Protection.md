# Same-Origin Static Serving + Frame Protection - Beginner Guide

This guide explains the T0018.2 wiring in plain language. It is for a new
developer who understands that InternHunter has a FastAPI backend, but does not
yet understand how a browser page can be served from the same app.

T0018.2 is not the chat UI design ticket. It is the small piece of backend
wiring that lets the app serve a page at `/` while keeping all API routes
working.

---

## 1. The one-sentence version

FastAPI now serves files from `src/api/static/` at the same origin as the API,
and it adds `X-Frame-Options: DENY` so the demo page cannot be embedded inside
someone else's site.

That means:

- Browser page: `http://127.0.0.1:8000/`
- API routes: `http://127.0.0.1:8000/api/v1/...`
- Docs page: `http://127.0.0.1:8000/docs`

All three come from the same FastAPI app.

---

## 2. What "same-origin" means

A browser origin is the combination of:

1. Protocol, such as `http`
2. Host, such as `127.0.0.1`
3. Port, such as `8000`

So this is one origin:

```text
http://127.0.0.1:8000
```

If the page is loaded from:

```text
http://127.0.0.1:8000/
```

and JavaScript calls:

```text
http://127.0.0.1:8000/api/v1/agent/chat/stream
```

then the browser sees both as the same origin.

That is the whole point of T0018.2. The frontend and backend live behind one
origin, so the demo does not need a separate frontend host or CORS setup.

---

## 3. Why not use a separate frontend server?

A separate frontend might look like this:

```text
Frontend: http://localhost:5173
Backend:  http://127.0.0.1:8000
```

Those are different origins because the ports differ. The browser would then
enforce CORS rules. The backend would have to explicitly allow the frontend
origin.

This project deliberately avoids that for the MVP:

- Fewer moving parts
- One deploy unit
- No CORS debugging for the demo page
- `api.cors.allowed_origins` can stay empty because the UI is same-origin

The UI can still look polished. "Same-origin static" only describes where the
files are served from, not how good the page can look.

---

## 4. What FastAPI is serving

The static files live here:

```text
src/api/static/
```

For T0018.2, the important file was:

```text
src/api/static/index.html
```

Later T0018.3 filled that directory with the real UI assets:

```text
src/api/static/index.html
src/api/static/styles.css
src/api/static/app.js
```

The wiring is the same either way. FastAPI just serves files from that folder.

Think of `src/api/static/` as the tiny built-in website folder for the backend.

---

## 5. The key line in `src/api/app.py`

The important mount is:

```python
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
```

Broken down:

- `app.mount(...)` attaches another mini app under a path.
- `"/"` means "serve this at the root of the website."
- `StaticFiles(...)` is Starlette/FastAPI's static-file server.
- `directory=str(STATIC_DIR)` points at `src/api/static/`.
- `html=True` tells `StaticFiles` to serve `index.html` for directory-style
  requests like `/`.
- `name="static"` gives the mount a route name.

So when a browser requests:

```text
GET /
```

FastAPI can answer with:

```text
src/api/static/index.html
```

---

## 6. Why route order matters

The app includes the API routers before mounting static files:

```python
app.include_router(
    query.create_router(limiter=limiter, rate_limit=resolved_rate_limit),
    prefix="/api/v1",
)
app.include_router(health.router, prefix="/api/v1")
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
```

This order matters because the static mount is at `/`, which is very broad.

The intended behavior is:

| Request | Who should handle it? |
|---|---|
| `/` | Static files |
| `/styles.css` | Static files |
| `/app.js` | Static files |
| `/api/v1/ready` | API router |
| `/api/v1/agent/chat/stream` | API router |
| `/docs` | FastAPI docs route |

If static files were mounted too early or too broadly in the wrong way, they
could shadow API routes. "Shadow" means a static route catches the request
before the API route gets a chance to answer.

T0018.2's test suite protects against that.

---

## 7. What the route-precedence tests prove

The tests live in:

```text
tests/api/test_static_serving.py
```

They check these beginner-friendly truths:

1. `/` serves a page.
2. `/docs` still loads and is not swallowed by the static mount.
3. `/api/v1/ready` still resolves as an API route.
4. `/` includes the frame-protection header.

The core checks are:

```python
response = self.client.get("/")
self.assertEqual(response.status_code, 200)
self.assertIn("InternHunter", response.text)
```

```python
response = self.client.get("/docs")
self.assertEqual(response.status_code, 200)
```

```python
response = self.client.get("/api/v1/ready")
self.assertEqual(response.status_code, 200)
```

These tests are not testing the visual design. They are testing that the wiring
does not break the backend.

---

## 8. What frame protection means

Frame protection prevents another website from putting InternHunter inside an
HTML frame, such as:

```html
<iframe src="https://your-demo-url.example"></iframe>
```

Why this matters:

- A malicious site could visually wrap your app in a fake page.
- Users might think they are interacting with one site while another site is
  controlling the surrounding experience.
- This class of attack is called clickjacking.

T0018.2 uses a simple response header:

```text
X-Frame-Options: DENY
```

`DENY` means browsers should not allow the page to be framed at all.

---

## 9. Where the header is added

The header is added in `src/api/app.py` by `FrameGuardMiddleware`:

```python
class FrameGuardMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Frame-Options"] = "DENY"
            await send(message)

        await self.app(scope, receive, send_with_header)
```

Beginner translation:

1. A request comes in.
2. FastAPI prepares a response.
3. Right before the response starts, the middleware adds one header.
4. The response continues normally.

The middleware is pure ASGI, which means it wraps the app at a low level without
turning streaming responses into buffered responses.

That detail matters because InternHunter also has an SSE streaming endpoint. We
want the header middleware to be boring and invisible to streaming.

---

## 10. Why T0018.2 uses only `X-Frame-Options`

You may see security guides recommend a fuller Content Security Policy, like:

```text
Content-Security-Policy: frame-ancestors 'none'
```

That is a good future option, but T0018.2 intentionally stays minimal.

Reason:

- The MVP static UI is plain HTML, CSS, and JavaScript.
- A strict CSP can accidentally block inline styles, scripts, fonts, or future
  UI changes if it is not designed carefully.
- T0018.2 only needed the frame-protection piece that T0016.4 deferred.

So the MVP choice is:

```text
X-Frame-Options: DENY
```

No fuller CSP yet.

---

## 11. How the browser and API now talk

Because the page and API share the same origin, frontend JavaScript can call the
API with relative paths:

```javascript
fetch("/api/v1/ready")
```

and:

```javascript
fetch("/api/v1/agent/chat/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query }),
})
```

The browser resolves those relative URLs against the current page origin.

If the page is:

```text
http://127.0.0.1:8000/
```

then `"/api/v1/ready"` becomes:

```text
http://127.0.0.1:8000/api/v1/ready
```

No hardcoded host. No separate frontend environment variable. No CORS.

---

## 12. Common beginner confusion

### "Does mounting `/` replace the whole API?"

No. The API routers are still registered. The tests prove `/api/v1/ready` and
`/docs` still work.

### "Does `StaticFiles` run the JavaScript?"

No. FastAPI only sends the JavaScript file to the browser. The browser runs it.

### "Is this server-side rendering?"

No. FastAPI is not generating HTML dynamically here. It is serving static files
from disk.

### "Is CORS disabled?"

CORS middleware still exists, but the demo UI does not need cross-origin access.
For the same-origin page, CORS is not involved.

### "Does frame protection protect the API too?"

The middleware adds the header broadly to HTTP responses. The important target
is the HTML page at `/`, because pages are what browsers frame.

### "Why is the static mount in the API app instead of a `frontend/` folder?"

Because this MVP has no build step and no separate frontend deploy. The static
directory is intentionally small and close to the FastAPI app that serves it.

---

## 13. How to verify T0018.2

Run the focused tests:

```bash
uv run pytest tests/api/test_static_serving.py -q
```

Run the streaming regression test:

```bash
uv run pytest tests/api/test_stream.py -q
```

Run the API route suite:

```bash
uv run pytest tests/api -q
```

Manual checks with the app running:

```bash
uv run uvicorn src.api.app:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

Then check the frame header:

```bash
curl -sI http://127.0.0.1:8000/ | grep -i x-frame-options
```

Expected:

```text
x-frame-options: DENY
```

Also confirm these still work:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/v1/ready
```

---

## 14. The mental model to keep

Before T0018.2:

```text
FastAPI app
  /api/v1/...  -> JSON and SSE endpoints
  /docs        -> Swagger UI
  /            -> nothing useful
```

After T0018.2:

```text
FastAPI app
  /api/v1/...  -> JSON and SSE endpoints
  /docs        -> Swagger UI
  /            -> static InternHunter page
  /*.css       -> static CSS
  /*.js        -> static JavaScript
```

And every HTTP response gets:

```text
X-Frame-Options: DENY
```

That is the wiring. T0018.3 builds the actual page behavior on top of it.

