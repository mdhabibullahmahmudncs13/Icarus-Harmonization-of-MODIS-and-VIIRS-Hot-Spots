Project Icarus

Harmonizing MODIS and VIIRS Active-Fire Hot Spots

Project Icarus is an offline-capable web application and reproducible data pipeline that combines active-fire detections from NASA's MODIS and VIIRS satellite instruments into a more consistent record of burning activity.

Challenge: NASA Space Apps Challenge 2026 — Harmonization of MODIS and VIIRS Hot Spots
Project status: Research and prototype implementation

The problem

MODIS observes active fires at approximately 1 km resolution, while VIIRS detects fires at approximately 375 m. VIIRS can identify many smaller or cooler fires, so raw detection counts often rise when VIIRS enters the record around 2012. That apparent jump can reflect a change in observing instruments rather than a real change in fire activity.

Icarus aims to reduce this sensor-driven discontinuity while preserving data provenance and communicating uncertainty.

How it works

Acquire data: fetch and register NASA FIRMS active-fire products before deployment. Raw files and manifests are cached locally.

Normalize and grid: apply quality filters, map detections to a 0.05° grid, and collapse repeated detections into cell-day presence.

Harmonize sensors: estimate cross-sensor calibration from overlapping observation periods and map VIIRS activity to a MODIS-equivalent scale.

Measure context: calculate observing coverage, climatological baselines, anomalies, and the typical critical fire period.

Serve results: expose read-only analytical results through a FastAPI API backed by local Parquet data and DuckDB.

Explore offline: use the web interface to inspect maps, time series, activity calendars, anomaly and critical-period information, and provenance.

The scientific calculations are deterministic Python code. Any optional AI narration is a separate layer; it does not perform the harmonization or calculate scientific results. Synthetic demo data is explicitly labelled and must not be interpreted as real fire observations.

Key features

Harmonization of MODIS and VIIRS active-fire observations.

Presence-based cell-day aggregation to reduce duplicate-count inflation.

Cross-sensor calibration using overlap periods.

Coverage and source labels to distinguish observed, calibrated, and unavailable periods.

Climatology, anomaly scoring, and critical-period estimates.

Preset or custom areas of interest (AOIs).

Read-only JSON API with a shared response contract.

Local cache and offline demo workflow.

Reproducible parameters, validation experiments, and automated tests.

Architecture

NASA FIRMS / reference datasets
            |
            v
  Acquisition and local cache
       (network required)
            |
            v
 Deterministic Python pipeline
     + DuckDB / Parquet
            |
            v
    Read-only FastAPI API
            |
            v
 React + Vite web application
            |
            +---- Optional AI narration
                  (explains API output only)

The data-acquisition stage requires connectivity. Once data and derived artifacts have been prepared, the API and frontend can operate locally; the committed fixture supports an offline demo without downloading NASA data.

Technology stack

Backend and data

Python 3.11+

FastAPI and Uvicorn

DuckDB, Pandas, and PyArrow/Parquet

Pydantic and JSON Schema validation

Pytest and Ruff

Frontend

React 18

TypeScript

Vite

D3 array/scale utilities and Three.js

Vitest and Playwright

Data sources

NASA FIRMS MODIS and VIIRS active-fire products

NASA MODIS burned-area data for an optional independent validation workflow

Repository structure

.
├── config/
│   └── params.yaml          # Central registry of scientific parameters
├── demo_fixtures/           # Committed offline demo detections
├── docs/                    # Architecture, methods, API, validation and deployment docs
├── src/
│   ├── acquire/             # NASA data acquisition and cache helpers
│   ├── api/                 # FastAPI endpoints and dataset access
│   ├── compute/             # Gridding, calibration, coverage, anomaly and season logic
│   ├── validate/            # Validation experiment harness and reports
│   └── demo.py              # Deterministic synthetic fixture generator
├── tests/                   # Backend tests
├── tools/                   # Experiment and fixture utilities
├── validation/              # Validation outputs
└── web/                     # React/Vite frontend and browser tests

Getting started

Requirements

Python 3.11 or newer

Node.js and npm for the frontend

uv is recommended for creating the Python virtual environment

Network access and a NASA FIRMS map key are needed only to download source data

1. Get the code

git clone <your-repository-url>
cd Icarus-Harmonization-of-MODIS-and-VIIRS-Hot-Spots

Replace <your-repository-url> with the repository's clone URL.

2. Set up the Python environment

The Makefile installs the project's backend and data-processing dependencies:

make venv

The default environment uses .venv. If you prefer to install dependencies manually, the Makefile's DEPS variable lists the packages it installs.

3. Run the backend in offline demo mode

The repository includes a deterministic demo fixture, so a FIRMS key is not required for this step:

make demo

This starts the API with OFFLINE=1 using Uvicorn. By default, Uvicorn listens on http://127.0.0.1:8000.

Useful checks:

curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/meta

Interactive API documentation is available at http://127.0.0.1:8000/docs while the backend is running.

Note: The offline API uses the committed demo fixture when the full local data cache is not available. Its synthetic values are for demonstrating and testing the workflow only.

4. Run the frontend

In another terminal:

cd web
npm install
npm run dev

Open the local URL printed by Vite (normally http://localhost:5173).

The frontend supports a bundled mock-data mode for a self-contained demo. To use the API-backed mode, configure the frontend environment as described below.

5. Configure the frontend data source

The example environment file documents supported options:

cp .env.example .env

For API-backed frontend development, set:

VITE_DATA=api
VITE_API_BASE=http://127.0.0.1:8011/api/v1

The API's default port and the configured frontend base URL must match. If you run Uvicorn on port 8000, either start it on port 8011 or set VITE_API_BASE to http://127.0.0.1:8000/api/v1.

Vite reads environment variables when it starts; restart the development server after changing them. Do not commit API keys or tokens.

Downloading real NASA data

Real-data acquisition is a separate, network-dependent step.

Request a NASA FIRMS MAP_KEY from the official FIRMS website.

Copy .env.example to .env and set FIRMS_MAP_KEY.

Review the selected products, bounding box, and date range in .env.example and src/acquire/firms.py.

Run the cache command, optionally overriding its defaults:

make cache
# Example with explicit products and dates:
make cache ARGS="--products VIIRS_SNPP_SP --start 2012-01-01"

The default pilot region is approximately Bangladesh and nearby areas. Check the acquisition module and its command-line help before downloading a large date range. Raw and derived datasets are stored locally and are not bundled with this repository.

For offline-only execution, set OFFLINE=1. In that mode the acquisition helpers read local cache/demo fixtures and do not access the network.

API overview

The read-only API exposes health and metadata routes plus analysis endpoints. The versioned API prefix is /api/v1.

Endpoint

Purpose

GET /health

Health check

/api/v1/meta

Dataset and parameter metadata

/api/v1/series

Time-series data for an AOI

/api/v1/cells

Cell-level values for a date range

/api/v1/baseline

Climatological baseline

/api/v1/anomalies

Anomaly results

/api/v1/critical-period

Seasonal onset, peak, end, and window

/api/v1/validation

Validation summaries

/api/v1/methods

Method and provenance information

/api/v1/aoi

AOI-related information

Exact request parameters and payload shapes are defined by the API implementation and docs/contract.schema.json. Invalid AOIs return structured validation errors. Responses include parameter metadata so results can be traced to the configuration used.

Configuration and reproducibility

Scientific parameters live in config/params.yaml. The configuration includes grid resolution, quality thresholds, temporal binning, calibration settings, coverage rules, anomaly thresholds, and critical-period criteria.

Derived outputs record a hash of the parameter configuration. Changing parameters can invalidate downstream results, so regenerate affected outputs and rerun validation after making scientific changes.

See:

docs/PARAMETERS.md — parameter definitions

docs/DATA_DICTIONARY.md — fields and data meanings

docs/TRD.md — technical requirements and methods

docs/ARCHITECTURE.md — system design

Tests and validation

Run the backend checks from the repository root:

make test
make lint

Run frontend checks from web/:

npm test
npm run typecheck
npm run build
npm run test:e2e

Run the deterministic validation experiments:

make validate

Or run the experiment module directly:

python -m tools.experiments

The validation report is documented in docs/VALIDATION.md; generated outputs are stored under validation/. Validation distinguishes synthetic mechanism checks from observed-data results and documents limitations rather than treating synthetic data as evidence.

Scientific interpretation and limitations

MODIS and VIIRS differ in spatial resolution, sensitivity, and detection behaviour. Harmonization reduces a known instrument-related discontinuity; it cannot make the sensors identical.

Calibration depends on overlap data, quality filters, and configured parameters. Interpret results alongside coverage, uncertainty, source labels, and provenance.

NOAA-21 data may be near-real-time and subject to upstream revision.

The offline demo fixture is synthetic and is not evidence of real-world fire activity.

Burned-area comparison is an independent validation path and may require additional data access credentials.

Icarus is an analytical aid, not a replacement for official emergency alerts or local incident assessments.

For the current experiment results and their caveats, consult docs/VALIDATION.md.

Data attribution

Icarus uses NASA FIRMS active-fire data and references NASA/LP DAAC products for validation. Credit NASA FIRMS/LANCE/EOSDIS and NASA LAADS DAAC when using results derived from their data, and consult docs/REFERENCES.md for product details and literature references. Downloaded raw datasets are cached locally and are not redistributed by this repository.

Contributing

Contributions are welcome. Before submitting a change:

Read CONTRIBUTING.md and the relevant design/method documentation.

Keep scientific computation deterministic and separate from I/O and presentation code.

Update tests when changing algorithms, contracts, or parameters.

Document parameter changes and rerun relevant validation experiments.

Run make test, make lint, and applicable frontend checks.

Security

Do not commit .env, NASA keys, Earthdata tokens, or private data. See SECURITY.md for reporting vulnerabilities.

Documentation

Start here:

docs/PRD.md — product vision and scope

docs/ARCHITECTURE.md — system architecture

docs/FLOWS.md — user flows

docs/DESIGN.md — frontend design system

docs/DEPLOYMENT.md — deployment and offline operation

docs/TESTING.md — testing strategy

docs/VALIDATION.md — experiment results and limitations

docs/REFERENCES.md — datasets and citations

Project Icarus — turning multi-sensor fire detections into a more consistent, transparent view of burning activity.
