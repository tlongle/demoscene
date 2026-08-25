# SCENE

A web app and scraper designed to catalogue, inspect, and track **PS1 and PS2 PAL demo discs**, powered by data from [Crimson Ceremony](https://crimson-ceremony.net/demopals).

---

## Features

- **Docker & Server Ready**: Pre-configured `Dockerfile` and `docker-compose.yml` with persistent `/data` volume for SQLite and downloaded images. Seamlessly runs behind **Nginx** reverse proxy and **Cloudflare Tunnels**.
- **Offline Scans & Image Cache**: Downloads and stores all disc face scans, front slipcases, back inlays, and variant covers locally inside the Docker volume.
- **Real Game Box Art Integration**: Resolves and displays high-res PAL game box covers for playable demo games and trailers (supports official **IGDB / Twitch API** + open cover archives with retro fallback placeholders for non-game media/videos).
- **Instant Search & Deep Filtering**: Search by demo title (`OPS2M Demo 46`), SCED code (`SCED-52161`), or game title (`Silent Hill`, `Tekken`, `Crash Bandicoot`).
- **Collector Inventory Ledger**:
  - 1-tap toggling: **In Collection**, **Wishlist**, **Not Owned**.
  - Physical condition tracking (*Mint*, *Good*, *Acceptable*, *Poor*, *Disc Only*).
  - Checklist (*Original Sleeve*, *Case*, *Tested & Working*).
  - Custom collector logs (boot sale notes, spine numbers, variant notes).
- **Backup & Restore**: Instant JSON export and restore of your collection ledger.

---

## Docker Deployment (Recommended)

### 1. Configure Environment (Optional)
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

*(Optional)* If you have a free Twitch Developer account for IGDB official 1080p box art, add your credentials in `.env`:
```env
TWITCH_CLIENT_ID=your_twitch_client_id
TWITCH_CLIENT_SECRET=your_twitch_client_secret
```
*(If left blank, the app will automatically use open retro cover archives!)*

### 2. Start with Docker Compose
```bash
docker compose up -d --build
```

The container starts with:
- Web App accessible on port `8000`.
- Persistent SQLite database and image storage mounted in `./data`.

---

## Local Development (Without Docker)

Run directly with Python:

```bash
./run.sh
```
Or:
```bash
python3 start.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## Offline Asset Caching & Scans Download

To download all disc scans, slipcases, and box art locally into `./data/assets`:
1. In the web app header, click **"OFFLINE ASSETS"**.
2. Tap **"▶ START SCANS DOWNLOAD"** to download all Crimson Ceremony disc scans.
3. Tap **"▶ BATCH FETCH BOX ART"** to pre-download game covers.

Or run directly from the command line:
```bash
python3 download_assets.py
```
