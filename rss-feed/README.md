# Daily RSS Intelligence Agent

A YAML-driven Python project that runs daily, scores RSS entries against deterministic topic rules, clusters top stories, writes local artifacts, syncs to Notion, and optionally sends a WhatsApp digest.

## Project structure

- `main.py` orchestrates the full daily run
- `config_loader.py` loads and validates YAML config
- `rss.py` fetches and normalizes feed items
- `scoring.py` performs deterministic keyword-based topic scoring (v1)
- `clustering.py` builds TF-IDF + KMeans clusters
- `storage.py` handles artifacts and seen-item state
- `notion_sync.py` maps selected items into Notion database rows
- `whatsapp.py` sends concise digest (Twilio in v1, Meta scaffold)
- `feedback.py` scaffold for weekly tuning pipeline

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill environment variables in your shell or via .env loading tool
```

### Run locally

```bash
python main.py --config config.yml --topics topics.yml
```

Outputs are written to `run.output_dir` (default `outputs/`) and state is kept in `run.state_dir` (default `state/`).

## Configuration

- Edit feed and routing behavior in `config.yml`
- Edit relevance topics/rules in `topics.yml`
- Secrets stay in environment variables only

### Notion mapping

The integration token and database ID are read from env vars configured in YAML:
- `notion.token_env`
- `notion.database_id_env`

Database property names are also read from YAML (`notion.properties.*`) and not hardcoded.

Special date behavior:
- `Published At` is sent as Notion date when RSS date parsing succeeds.
- Missing/unparseable feed dates are skipped (field omitted).
- `Digest Date` is always set to current run date in configured timezone (default Europe/Berlin).

## Scheduling examples

### Cron (daily at 08:00 Europe/Berlin)

```cron
0 8 * * * cd /path/to/rss-feed && /path/to/rss-feed/.venv/bin/python main.py --config config.yml --topics topics.yml >> state/cron.log 2>&1
```

### systemd timer

`/etc/systemd/system/rss-intel.service`

```ini
[Unit]
Description=RSS Intelligence Daily Run

[Service]
Type=oneshot
WorkingDirectory=/path/to/rss-feed
EnvironmentFile=/path/to/rss-feed/.env
ExecStart=/path/to/rss-feed/.venv/bin/python /path/to/rss-feed/main.py --config /path/to/rss-feed/config.yml --topics /path/to/rss-feed/topics.yml
```

`/etc/systemd/system/rss-intel.timer`

```ini
[Unit]
Description=Run RSS Intelligence Daily

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rss-intel.timer
```

## v2 extension points

- Replace or augment deterministic scoring with semantic reranking in `scoring.py`
- Add model-assisted cluster labeling in `clustering.py`
- Implement Meta WhatsApp provider in `whatsapp.py`
- Use `feedback.py` logs for weekly weight calibration
