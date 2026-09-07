# PBPX

PlayStation Demo & Promo Archive — a high-performance web archive and collection tracker designed to catalogue, inspect, and showcase PlayStation demo and promotional discs, box art, and high-resolution scans.

---

## Deployment Modes

PBPX runs from a single codebase supporting two distinct modes:

1. **`selfhosted` (Default)**: Optimized for personal homelab / private Docker deployment. Single-instance collection tracking with guest catalog access and local database persistence. Registration is disabled after the first admin is created.
2. **`public`**: Multi-tenant public web deployment (e.g. `pbpx.cc`). Features public user registration, multi-user isolated collections, public collector showcase profiles (`/#u/{username}`), optional collection privacy toggles, and admin-gated catalog mutations.

---

## Docker Deployment

### 1. Configure Environment (Optional)
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Set mode and credentials as needed:
```env
PORT=5363
PBPX_MODE=selfhosted          # 'selfhosted' or 'public'
ALLOW_REGISTRATION=false       # set true if you want open registration in selfhosted mode
TWITCH_CLIENT_ID=your_twitch_client_id
TWITCH_CLIENT_SECRET=your_twitch_client_secret
```

### 2. Start with Docker Compose
```bash
docker compose up -d --build
```

* **Web UI Port**: `5363`
* **Persistent Data**: Stored in `./data` (SQLite database + downloaded artwork)

---

## 💻 Local Development (Without Docker)

Run directly with `uv`:

```bash
uv run python start.py
```
Or with shell script:
```bash
./run.sh
```

Open **[http://localhost:5363](http://localhost:5363)** in your browser.
