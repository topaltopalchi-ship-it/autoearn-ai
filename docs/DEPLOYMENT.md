# Deploy AutoEarn AI as a persistent web service

This repository contains a FastAPI web application. GitHub Actions is used for tests; it is not the production host.

## Important before deployment

- The Render blueprint in this repository uses a paid Starter web service and a persistent disk. The free web-service tier does not provide the persistent disk needed by this SQLite setup and can sleep when idle.
- The service is configured with a generated `AUTOEARN_OWNER_TOKEN` (at least 32 characters) and stores SQLite at `/var/data/autoearn.db`.
- Keep the token private. In the hosting dashboard, reveal/copy the generated environment variable and enter it in the dashboard's Owner token field. The browser stores it only for the current tab session.
- Use HTTPS only. Do not put the owner token in source code, GitHub commits, screenshots, public issue reports, or chat messages.
- This is a single-owner deployment gate, not a full multi-user authentication system. Before opening access to other people, add proper user accounts, session cookies, CSRF protections, rate limiting, backups, and a managed secrets workflow.
- The application does not autonomously execute tasks on third-party platforms. RSS discovery only imports public feed listings as pending candidates; the user reviews and approves them.

## Deploy with Render Blueprint

1. Push the `feat-discovery-adapter-runtime` branch after its tests pass.
2. In Render, choose **New → Blueprint** and connect the GitHub repository.
3. Select branch `feat-discovery-adapter-runtime` and allow Render to read `render.yaml`.
4. Review the paid service and persistent-disk costs shown by Render before confirming.
5. After deployment, open the service URL. Check that `/api/health` returns `{"status":"ok"}`.
6. In Render service settings, open Environment and copy the generated `AUTOEARN_OWNER_TOKEN` securely. Do not regenerate it unless you are ready to update the token in the browser.
7. Open the service root URL in Chrome on Android, enter the owner token, and connect.
8. To install the web app, use Chrome's menu → **Add to Home screen** or **Install app** if offered.

## Local container test

Build and run with a persistent local data directory:

```bash
docker build -t autoearn-ai .
mkdir -p autoearn-data
docker run --rm -p 10000:10000 \
  -e AUTOEARN_OWNER_TOKEN='replace-with-a-random-secret-at-least-32-characters' \
  -e AUTOEARN_DB=/var/data/autoearn.db \
  -v "$PWD/autoearn-data:/var/data" \
  autoearn-ai
```

Then open `http://localhost:10000` and `http://localhost:10000/api/health`.

## Database backup

Back up the SQLite database from the persistent disk regularly. Before restoring or migrating, stop writes to the service and preserve a copy of the existing database. A persistent disk is not a backup.
