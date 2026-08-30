# DEMOSCENE

A sleek, self-hosted web app and archive designed to catalogue, inspect, and track **PlayStation 1 and PlayStation 2 PAL demo discs**, powered by data from [Crimson Ceremony](https://crimson-ceremony.net/demopals).

---

## Docker Deployment

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
