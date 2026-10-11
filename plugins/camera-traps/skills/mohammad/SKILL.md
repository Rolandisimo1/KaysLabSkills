---
name: mohammad
description: >-
  Build large-scale wildlife / camera-trap / street-imagery computer-vision
  pipelines the way Mohammad Alyetama does. Use when harvesting or scraping
  image data at scale (Mapillary, camera traps, feeders), building a
  Label-Studio annotation loop, training or serving YOLO/MegaDetector models,
  estimating distance/depth from camera-trap frames, or wiring up resumable,
  checkpointed data-engineering jobs with Parquet, DuckDB, S3, and SLURM.
  Triggers: "download/scrape images", "Label Studio", "YOLO dataset",
  "pre-annotations", "prediction API", "camera trap depth/distance",
  "MegaDetector", "hard negatives".
---

# Wildlife CV Pipeline (style: Alyetama)

Extracted from `street_dogs_mp`, `dog_detection`, `baby_animals`, and
`dnd-calib`. The through-line: treat a research CV project as production data
engineering — scrape at scale, keep a human in the loop through Label Studio,
serve models efficiently, and make every long-running job resumable.

## Core architecture: independent, numbered, resumable CLI stages

Structure a project as a small set of standalone scripts, each one stage of a
pipeline, each runnable on its own with `argparse` and `--help`. Do not build
one monolith. The canonical mental model is three stages:

1. **Extract** — scrape/collect + detect + write structured output.
2. **Audit** — independently verify the extract captured everything it should;
   list what's missing.
3. **Backfill** — fetch only the missing set, append to the same schema.

Conventions to keep:

- Scripts live at repo root; everything else (`tools/`, config, data dirs) is
  subordinate. Default paths are relative to the working dir, and scripts are
  always run from repo root.
- Long jobs are resumable by construction: compressed checkpoints, per-unit
  progress sidecars (`.*_progress*.json` with a row offset), and idempotent
  file steps (check destination counts before copying, so a re-run on a
  half-finished dataset is safe).
- Scale with multiprocessing across units (regions/cameras/species) and
  threading within a unit (API calls, downloads). Make the process/worker
  counts CLI flags.
- Be SLURM-aware — assume big runs go to a cluster; don't hardcode a machine.

## The Label Studio annotation loop (the heart of it)

Every classification/detection project runs the same human-in-the-loop cycle.
Build all five pieces:

1. **Export** — `export_annotations.sh`: curl the Label Studio API, export
   JSON_MIN. Token + base URL from `.env`.
2. **Prepare dataset** — `prepare_*_dataset.py`: parse the JSON_MIN export,
   convert to YOLO format (detection: boxes → txt; classification: crop the box
   region and sort crops into class folders), split train/val (default 0.8).
   Optional on-the-fly compression/resize. Flexible `--classes` and a
   `--classify-by` key.
3. **Train** — Ultralytics YOLO (detection or classification). For
   classification, follow a detect-then-crop-then-classify pattern: use
   MegaDetector (or a detector) to find the animal box, crop, then run the
   classifier on the crop.
4. **Serve** — `prediction_api.py`, a FastAPI server that returns
   Label-Studio-compatible pre-annotations. Two non-negotiable efficiency
   features: lazy model load (load weights on first request, not at boot) and
   automatic GPU VRAM release after an idle timeout (~5 min). Carry a
   `--model-version` string.
5. **Send predictions back** — `send_prediction_tasks.py`: pull tasks from
   Label Studio, filter out cancelled/already-annotated (and optionally
   `--after-date`), call the prediction API, upload predictions as
   pre-annotations so humans correct rather than label from scratch. Use the
   model-version string to manage/replace stale predictions.

Hard-negative / hallucination mining is a first-class step: collect images
annotated as a specific non-target class (`generate_other_animals.py -c "other
animal"`) and feed them back as background/negative training data to suppress
false positives.

## Serving & storage defaults

- FastAPI for inference endpoints; lazy load + idle VRAM GC always.
- SQLite to log predictions and errors from batch inference.
- S3-compatible object storage configured via `.env` (`ENDPOINT_URL`,
  `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`, `BUCKET_NAME`, `BUCKET_REGION`). Pass
  local image dirs so the server skips re-downloading images it already has.
- Batch inference (`predict_and_filter.py`): GPU acceleration, `--batch` size
  flag, instant random sampling over millions of images, write results to the
  SQLite db.

## Data at scale (from street_dogs_mp)

- Parquet is the canonical store — chunked/partitioned, written incrementally,
  append-only backfill shards that match the main schema. Split "everything"
  (`all_data_*`) from "the subset you care about" (`ground_animals_*`).
- Build a DuckDB catalog that reads only Parquet footers (row counts, never a
  full scan) so you can answer "what do we have, where, how much" instantly —
  even for unmounted drives. Make it incremental (re-read a file only if
  size/mtime changed) and offline-drive-aware.
- For paginated/tiled web APIs, prefer the source that gives a completeness
  guarantee: e.g., Mapillary vector tiles return every point, while the bbox
  search API silently caps (~2000) and 500s on dense cells. Choose the API that
  lets you audit coverage, not just fetch.
- Rotate API tokens (`MLY_KEY`, `MLY_KEY_1`…), round-robin across them, and
  show a live daily budget bar when an API has a per-token/day quota. Multi-day
  runs just re-run the same command; done units are skipped.
- Ship a small Flask browse app (`browse.py`) over the output: region sidebar,
  geocoded location search, image lightbox, Leaflet heatmap of coordinates,
  per-file download links.

## Camera-trap depth / distance calibration (from dnd-calib)

When estimating animal position/distance from camera-trap frames:

- Organize images into a deterministic tree:
  `{dataset}/{camera_model}/{transects}/{deployment}/` with
  `calibration_frames/`, `calibration_frames_masks/`, `detection_frames/`.
- Normalize deployment IDs into filesystem-safe names (replace `/`, `,`, `.`,
  `:` and spaces with hyphens).
- Let EXIF make/model override the metadata's camera field.
- Run a YOLO sign detector on calibration frames to produce binary
  bounding-box masks; collect frames with no detection into `failed_signs` and
  assert mask-count == frame-count before proceeding.
- Each camera model needs a crop of its timestamp data-strip before depth
  estimation; store per-model `crop_top`/`crop_bottom` in a
  `camera_crop_mapping.json`. Keep per-model FOV/sensor specs in a
  `cameras_specs.json`.
- Feed masks + FOV into a depth-estimation model (DPT) with RANSAC calibration
  regression; emit per-deployment `.npy` calibration arrays and a top-level
  `depth_mmm.csv` (mean/median/min/max depth per deployment).

## Config & secrets

`.env` for every secret (Label Studio token, API keys, S3 creds), always with a
committed `.env.example`. Never hardcode tokens.

## Checklist when starting a new project in this style

- Split the work into Extract / Audit / Backfill (or numbered stages), each a
  standalone CLI script.
- Make every long job resumable + idempotent from day one.
- Stand up the full Label Studio loop, not just training.
- Serve with FastAPI + lazy load + idle VRAM release.
- Parquet + DuckDB catalog for anything over ~10k records.
- `.env` + `.env.example`; SQLite for run logs.
- Plan for SLURM and multi-day, multi-token runs.
