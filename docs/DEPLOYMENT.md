# Milestone 0: Render setup

The user has deployed both services, and dependency, browser/CORS and public-cache
checks pass. This guide records how the services are configured. The existing URLs
remain in local configuration; no hostname is invented. See [acceptance](ACCEPTANCE.md).

## 1. Push the source

Verify `git status` and `git check-ignore .env.local` before committing and pushing.
The `.gitignore` excludes credentials, the supplied assessment PDFs, installed tools,
dependency folders, downloaded PDFs, and feasibility artifacts. Never force-add them.

## 2. Create the Python API

Choose Render **New → Web Service**, connect the FINN repository, and set:

| Setting | Value |
| --- | --- |
| Name | `finn-api` (the assigned hostname may differ) |
| Runtime | Python |
| Branch | Your pushed working branch |
| Root directory | Leave blank: repository root |
| Build command | `pip install -r requirements.lock && pip install --no-deps -e .` |
| Start command | `uvicorn finn.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health/live` |
| Instance | **Free** |

Backend environment variables:

| Variable | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.12.10` |
| `FINN_ENV` | `production` |
| `GEMINI_API_KEY` | Existing key from `.env.local` |
| `GEMINI_LITE_MODEL` | `gemini-3.5-flash-lite` |
| `GEMINI_REASONING_MODEL` | `gemini-3.8-flash` |
| `FINN_ENABLE_SEMANTIC_SEARCH` | `false` |
| `SUPABASE_URL` | Project URL, locally named `NEXT_PUBLIC_SUPABASE_URL` |
| `SUPABASE_SECRET_KEY` | Server-only secret; never prefix it `VITE_` or `NEXT_PUBLIC_` |
| `SUPABASE_PUBLISHABLE_KEY` | Publishable key |
| `SUPABASE_STORAGE_BUCKET` | `finn-documents` |
| `FINN_ALLOWED_ORIGINS` | Set to the real frontend origin in step 4 |

Deploy and copy the actual API URL shown by Render. Open `/health/live`; expect
`service: finn-api` and `status: ok`. Readiness deliberately says `foundation_only`.
Before step 4, browser requests from the production frontend will not be allowed.

## 3. Create the frontend

Choose Render **New → Static Site**, connect the same repository, and set:

| Setting | Value |
| --- | --- |
| Name | `finn-web` |
| Branch | Same source branch |
| Root directory | `frontend` |
| Build command | `npm ci --no-fund --no-audit && npm run build` |
| Publish directory | `dist` |

Set only these frontend build variables:

| Variable | Value |
| --- | --- |
| `NODE_VERSION` | `24.22.2` |
| `VITE_API_BASE_URL` | Actual API URL from step 2, without a trailing slash |
| `VITE_SUPABASE_URL` | Public Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Publishable key, **not** the secret |

Do not add Gemini or Supabase secrets to the frontend service. Changing a `VITE_` value
requires a new frontend build. Add a **Rewrite** from `/*` to `/index.html` and the
headers `X-Content-Type-Options: nosniff` and
`Referrer-Policy: strict-origin-when-cross-origin`.

Deploy and copy the assigned frontend URL. The static page should load independently
of whether the Python service is awake.

## 4. Connect and verify

Set the API's `FINN_ALLOWED_ORIGINS` to the actual frontend **origin**: HTTPS scheme
and hostname only, no trailing slash/path/wildcard. Save/redeploy the API. On the
frontend verify both **Check API connection** and **Check public cache**.

The Supabase migration and its access boundaries have already been tested. Keep the
PDF bucket private and do not add anonymous write policies to fix a frontend problem.
The connection view reads `finn_public_status`; the working app also reads portfolio
metadata and explicitly published research through read-only policies.

`render.yaml` supplies equivalent Blueprint configuration. Its `sync: false` values
must be filled by you; actual API URLs and frontend origins still need to be set
after service creation. Do not add a paid database, disk, cron service, or worker.

## 5. Close the deployment gate

Put the actual assigned URLs in `.env.local`:

```dotenv
FINN_DEPLOYED_API_URL=<actual API URL>
FINN_DEPLOYED_WEB_URL=<actual frontend URL>
```

Then run:

```powershell
.\.venv\Scripts\python.exe -m finn.feasibility --symbol INFY
```

After at least 15 minutes without API traffic, reopen the frontend and check the API.
Record wake-up time; the static page/public cache should remain usable. Do not add
artificial keep-alive traffic to disguise cold starts.

Those Milestone 0 checks have passed. Push/Pull implementation is now present; verify
the current release with the product browser checks and [acceptance notes](ACCEPTANCE.md).
