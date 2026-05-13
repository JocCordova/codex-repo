# home-storage-agent

`home-storage-agent` is a local-first Python 3.11+ CLI for safely auditing, classifying, planning, copying, and verifying a migration from laptop and external `2tb` drive storage into a new `5tb` archive drive.

The tool is intentionally conservative:

- it never deletes files
- it never moves files by default
- scanning and planning are the default workflow
- copy operations are dry-run unless `--execute` is passed
- sensitive files are flagged and excluded from LLM classification by default
- the LLM co-pilot path sends metadata only by default: filename, extension, size, parent folder, modified date, and inferred type

## install

From this folder:

```bash
python -m pip install -e .
```

Or run without installing:

```bash
python -m home_storage_agent --help
```

## project layout

```text
home-storage-agent/
  config/
    sources.yaml
    destinations.yaml
    classification_rules.yaml
    llm_budget.yaml
    sensitive_patterns.yaml
  scripts/
    01_scan_inventory.py
    02_detect_duplicates.py
    03_classify_basic.py
    04_classify_with_llm.py
    05_generate_migration_plan.py
    06_execute_copy.py
    07_verify_copy.py
    08_generate_report.py
  data/
    inventory.duckdb
    inventory.csv
    duplicates.csv
    migration_plan.csv
  reports/
    migration_report.md
    folder_summaries.md
    manual_review.md
    backup_verification.md
  logs/
    migration.log
```

Generated folder names, file names, config keys, and output paths are lowercase and snake_case.

## configure sources

Edit `config/sources.yaml` before running a real scan:

```yaml
laptop_paths:
  - ~/documents
  - ~/downloads
external_2tb_paths:
  - /volumes/external_2tb
excluded_paths:
  - ~/.trash
  - ~/library/caches
max_scan_depth: null
```

## target archive structure

The destination configuration stages files into this lowercase structure:

```text
archive_5tb/
  00_inbox_to_sort/
  01_media/
    movies/
    series/
    documentaries/
    youtube/
    music/
    audiobooks/
    personal_videos/
    unsorted_video/
    needs_metadata/
  02_photos_videos/
    camera/
    phone_exports/
    edited/
    raw/
    personal_archive/
  03_documents/
    personal/
    legal/
    finance/
    contracts/
    scans/
    tax/
    manual_review/
  04_code_projects/
    github_exports/
    old_projects/
    client_work/
    notebooks/
    manual_review/
  05_startup/
    3d_pie/
    pie_os/
    brand/
    research/
    legal/
    finances/
  06_backups/
    laptop/
    phone/
    config_exports/
    system_exports/
    mac_mini/
  07_personal_data_lake/
    spotify/
    netflix/
    youtube/
    instagram/
    watch_history/
    listening_history/
    recommendations/
    playlists/
  99_cold_storage/
    old_archives/
    unknown/
    manual_review/
```

## usage

### scan

Scan configured source paths into a local DuckDB inventory and CSV export.

```bash
python -m home_storage_agent scan --config config/sources.yaml
```

By default, scanning does not calculate full file hashes. To hash every file, opt in explicitly:

```bash
python -m home_storage_agent scan --full-hash
```

Outputs:

- `data/inventory.duckdb`
- `data/inventory.csv`

Inventory columns include `path`, `filename`, `extension`, `size_mb`, `created_at`, `modified_at`, `file_type`, `source_root`, `parent_folder`, and `hash_status`.

### duplicates

Detect duplicate candidates without deleting anything.

```bash
python -m home_storage_agent duplicates --weak
```

The weak pass marks likely duplicates using same filename plus same size. A stronger pass checks sha256 checksums for candidates:

```bash
python -m home_storage_agent duplicates --sha256
```

Output:

- `data/duplicates.csv`

### classify

Classify files with deterministic local rules first.

```bash
python -m home_storage_agent classify
```

Categories include:

- `media_video`
- `media_audio`
- `photo`
- `document`
- `code`
- `archive`
- `installer`
- `config`
- `sensitive`
- `unknown`

Sensitive and high-risk items include legal, tax, finance, contracts, keys, password exports, `.env`, certificates, private documents, and sensitive pattern matches.

Output:

- `data/classified_inventory.csv`

### classify-llm

Run metadata-only LLM-assisted classification for ambiguous files.

```bash
python -m home_storage_agent classify-llm --ambiguous-only
```

The current implementation includes an offline metadata-only fallback so the CLI remains local-first even when no LLM provider is configured. The integration point is intentionally isolated and budget-controlled by `config/llm_budget.yaml`.

Safety defaults:

```yaml
metadata_only_default: true
allow_content_inspection: false
```

The tool does not read or send sensitive file contents. Sensitive rows and high-risk rows are skipped by LLM classification.

Output:

- `data/llm_classifications.csv`

### plan

Generate a migration plan and manual review report.

```bash
python -m home_storage_agent plan
```

Supported actions:

- `copy`
- `copy_review_required`
- `skip`
- `manual_review`

Uncertain files default to manual review.

Outputs:

- `data/migration_plan.csv`
- `reports/manual_review.md`

### copy

Copy files from the migration plan. Dry-run is the default:

```bash
python -m home_storage_agent copy --dry-run
```

Actually copying requires `--execute`:

```bash
python -m home_storage_agent copy --execute --archive-root /volumes/archive_5tb
```

Copy safety:

- never deletes source files
- never moves source files
- preserves timestamps via `shutil.copy2`
- never overwrites silently
- filename conflicts receive safe numbered suffixes such as `_001`
- all actions are logged to `logs/migration.log`

### verify

Verify copied files by count and size, optionally with sampled sha256 checksums.

```bash
python -m home_storage_agent verify --sample-checksums 500
```

Output:

- `reports/backup_verification.md`

### report

Generate a readable migration report.

```bash
python -m home_storage_agent report
```

Output:

- `reports/migration_report.md`

The report includes totals, largest folders, largest files, file type distribution, duplicate candidates, high-risk files, manual review items, copied/skipped files, and verification summary fields when available.

## script wrappers

The numbered scripts call the same CLI commands:

```bash
python scripts/01_scan_inventory.py --config config/sources.yaml
python scripts/02_detect_duplicates.py --weak
python scripts/03_classify_basic.py
python scripts/04_classify_with_llm.py --ambiguous-only
python scripts/05_generate_migration_plan.py
python scripts/06_execute_copy.py --dry-run
python scripts/07_verify_copy.py --sample-checksums 500
python scripts/08_generate_report.py
```

## media organization notes

The v1 media path prepares files for future Jellyfin, Plex, or Emby usage. It does not try to perfectly rename movies or series. Unknown videos are staged into `archive_5tb/01_media/unsorted_video/` or `archive_5tb/01_media/needs_metadata/` and can be cleaned up later.

## personal data lake notes

The folder structure reserves space for exports from Spotify, Netflix, YouTube, Instagram, watch history, listening history, recommendations, and playlists. Provider-specific parsers are intentionally not implemented in v1.

## privacy model

The LLM acts as a migration co-pilot, not an autonomous file manager. Use it for ambiguous filenames, folder summaries, suggested destinations, media grouping hints, project summaries, and personal data lake organization suggestions. Do not use it for deleting files, moving files without review, reading sensitive content, or making final decisions on legal, financial, password, key, or client files.
