# Interview Simulator — Frontend

React + TypeScript + Vite + Tailwind SPA for the AI Interview Simulator backend.
Node is only a build-time tool — `npm run build` outputs plain static HTML/JS/CSS.

## Setup

```bash
cd frontend
npm install
cp .env.example .env   # adjust if the API isn't on localhost:8000
npm run dev
```

Requires the backend running (see repo root `docker-compose.yml` + `uvicorn main:app --reload`)
and `CORS_ALLOWED_ORIGINS` in the backend `.env` to include this dev server's origin
(defaults to `http://localhost:5173`, which matches Vite's default port).

## Env vars

| Var | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend REST base URL (default `http://localhost:8000`) |
| `VITE_WS_BASE_URL` | Backend WebSocket base URL (default `ws://localhost:8000`) |

## OAuth (Google / GitHub) setup

The backend's `/auth/{provider}/callback` route itself is untouched — it still returns the
JWT as JSON. To make that work from a single-page app, point the OAuth redirect at *this
frontend* instead of the backend, and let the frontend forward the code/state via `fetch`:

1. In your Google/GitHub OAuth app console, set the authorized redirect URI to:
   `http://localhost:5173/oauth/callback/google` (and `/oauth/callback/github`).
2. In the backend `.env`, set both:
   ```
   OAUTH_REDIRECT_BASE_URL=http://localhost:5173
   OAUTH_CALLBACK_PATH_TEMPLATE=/oauth/callback/{provider}
   ```
   The path template matters — without it the backend still builds the old
   `/auth/{provider}/callback` path, which doesn't match any route this SPA actually has
   (`src/App.tsx` only defines `/oauth/callback/:provider`), and Google will reject the
   redirect_uri outright since it won't match what's registered in step 1.
3. `src/pages/OAuthCallback.tsx` reads `?code&state` from the URL, calls the backend's
   existing callback endpoint, and stores the returned JWT.

## Live video/audio

Camera/mic controls exist in `src/components/interview/LiveMediaControls.tsx` but are
disabled and tucked behind a closed-by-default menu — there's no backend support for
live media yet. Wiring them up later should only require replacing the `disabled` buttons
with real handlers; no other frontend restructuring needed.

## Structure

- `src/lib/` — API client, shared types (mirrors backend Pydantic schemas), auth token storage
- `src/context/AuthContext.tsx` — current user + login/signup/logout
- `src/hooks/useInterviewSocket.ts` — wraps the `WS /ws/interview/{id}` protocol
- `src/pages/` — one file per route
- `src/components/` — shared UI (glass panels, buttons, chat, nav/footer)
