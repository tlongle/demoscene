# DEMOSCENE

A sleek, self-hosted web app and archive designed to catalogue, inspect, and track **PlayStation 1 and PlayStation 2 PAL demo discs**, powered by data from [Crimson Ceremony](https://crimson-ceremony.net/demopals).

---

## 📁 Project Structure

```text
demo_scene/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application, routes, and middleware
│   ├── core/
│   │   ├── config.py        # Centralized settings & default port 5363
│   │   └── database.py      # SQLite database engine & collection queries
│   └── services/
│       ├── scraper.py       # Crimson Ceremony catalog scraper & sync
│       ├── boxart.py        # IGDB Twitch API integration & cover cache
│       ├── intel.py         # Game metadata enrichment & palette badges
│       ├── downloader.py    # High-resolution offline scan downloader
│       └── parser.py        # HTML & entry text block parser
├── data/
│   ├── demopals.db          # Persistent SQLite database
│   └── assets/              # Offline disc scans, slipcases, and box art
├── static/                  # PWA frontend (index.html, style.css, app.js)
├── Dockerfile               # Production container image definition
├── docker-compose.yml       # Port 5363 container orchestration
├── requirements.txt         # Python dependencies
├── run.sh                   # Local launch helper script
├── start.py                 # Application entry point
├── .env.example             # Environment template
└── .gitignore               # Git ignore rules for clean repo
```

---

## 🚀 Docker Deployment (Port 5363)

### 1. Configure Environment (Optional)
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

*(Optional)* If you have Twitch Developer credentials for official 1080p IGDB box art, add them to `.env` (or configure them directly in the in-app **⚙️ Settings** modal):
```env
PORT=5363
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

## 🌐 Nginx Proxy Manager Setup

In Nginx Proxy Manager (NPM):
* **Scheme**: `http`
* **Forward Hostname / IP**: `172.17.0.1` *(Docker Host Gateway)* or your server's LAN IP
* **Forward Port**: `5363`
* **Websockets Support**: ✅ Toggle ON
* **Block Common Exploits**: ✅ Toggle ON

---

## 💻 Local Development (Without Docker)

Run directly with Python:

```bash
./run.sh
```
Or:
```bash
python3 start.py
```
Open **[http://localhost:5363](http://localhost:5363)** in your browser.
