# Frontend System Architecture & UI/UX Technical Design Specification (`frontend-design.md`)

## 1. Executive Summary & Architecture Vision

The **AgriSat Frontend** is a static, offline-first Progressive Web App (PWA) designed to deliver real-time and multi-decade satellite hotspot analysis without relying on continuous internet connectivity. The core mission of the interface is to reconcile coarse MODIS thermal observations ($1\text{ km}$) with finer VIIRS detections ($375\text{ m}$) across a 2003–2026 record, eliminating artificial detection step-changes while maintaining instant map responsiveness and zero-latency analytics in remote field environments.

```
+-----------------------------------------------------------------------------------+
|                            OFFLINE-FIRST FRONTEND PWA                             |
|                                                                                   |
|  +----------------------+  +-------------------------+  +----------------------+  |
|  |    MapLibre GL JS    |  |        deck.gl          |  |       Three.js       |  |
|  |  (PMTiles / Raster)  |  |  (Grid Cells/Heatmaps)  |  |  (3D Terrain Views)  |  |
|  +----------+-----------+  +------------+------------+  +----------+-----------+  |
|             |                           |                          |              |
|             +---------------------------+--------------------------+              |
|                                         |                                         |
|  +--------------------------------------v--------------------------------------+  |
|  |                     CLIENT-SIDE ENGINE & STORAGE                            |  |
|  |  +--------------------+  +--------------------+  +-----------------------+  |  |
|  |  |   DuckDB-WASM      |  |  Service Worker    |  | Persistent Storage    |  |  |
|  |  | (GeoParquet SQL)   |  | (Workbox Caching)  |  | (IndexedDB / OPFS)    |  |  |
|  |  +--------------------+  +--------------------+  +-----------------------+  |  |
|  +--------------------------------------|--------------------------------------+  |
|                                         |                                         |
|  +--------------------------------------v--------------------------------------+  |
|  |                 OFFLINE SYNC & RECOVERY CONTROLLER                          |  |
|  |  +--------------------+  +--------------------+  +-----------------------+  |  |
|  |  | Offline Download   |  | Background Sync    |  | AI Panel Graceful     |  |  |
|  |  | (Tile & Parquet)   |  | Queue              |  | Fallback              |  |  |
|  |  +--------------------+  +--------------------+  +-----------------------+  |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Technology Stack & Core Dependencies

The frontend stack is engineered to achieve **Zero CDN Dependencies**, ensuring cold boots succeed completely offline.

| Layer / Subsystem | Technology Choice | Purpose / Architectural Justification |
| :--- | :--- | :--- |
| **Framework & Build** | React 18, TypeScript, Vite, Tailwind CSS | Type-safe UI components with minimal bundle overhead and instant asset building. |
| **Map Rendering** | **MapLibre GL JS** | Open-source vector/raster web map renderer supporting direct offline PMTiles reading. |
| **Geospatial Overlay** | **deck.gl** | WebGL-accelerated rendering of $5.5\text{ km}$ grid cells, FRP heatmaps, and hotspot points. |
| **3D Visualization** | **Three.js** | Optional 3D elevation and satellite orbital geometry rendering. |
| **Client-Side Query Engine** | **DuckDB-WASM** | In-browser SQL execution directly over local GeoParquet files without backend calls. |
| **Offline Cache** | **Workbox Service Worker** | Multi-strategy caching protocol (App Shell precache, PMTiles cache-first, API stale-while-revalidate). |
| **Persistent Storage** | **IndexedDB / OPFS** | Browser storage backed by `navigator.storage.persist()` to safeguard against cache eviction. |
| **Raster Data Streaming** | **HTTP Range Reader** | Direct client-side reading of Cloud-Optimized GeoTIFFs (COGs) and Zarr chunk slicing. |

---

## 3. Component Architecture & UI Layout

The application interface is structured into six key interactive modules:

```
+-----------------------------------------------------------------------------------+
| [AgriSat] [Offline Download] [Data Badge: CACHED] [Last Updated: 2026-10-04 01:00] |
+-------------------------------------------------------+---------------------------+
|                                                       |  BURNING CALENDAR HEATMAP |
|                                                       |  +---------------------+  |
|                   MAIN MAP VIEW                       |  | 2023 [||||||||||||] |  |
|              (MapLibre GL + deck.gl)                  |  | 2024 [||||||||||||] |  |
|                                                       |  | 2025 [||||||||||||] |  |
|   [Grid Cells: 5.5 km]   [FRP Peak Heatmap]           |  | 2026 [||||||||||||] |  |
|                                                       |  +---------------------+  |
|                                                       |                           |
+-------------------------------------------------------+  ANOMALY / BASELINE CARD  |
|  CONTROL TOOLBAR                                      |  +---------------------+  |
|  [Mode: RAW | HARMONIZED] [Sensor: MODIS/VIIRS]        |  | "Is this unusual?"  |  |
|  Timeline: <=== 2003 -------------------- 2026 ===>   |  | Percentile: 94th    |  |
|                                                       |  +---------------------+  |
+-------------------------------------------------------+---------------------------+
| METHODS & VALIDATION PANEL                            | PROVENANCE DRAWER (Slide) |
| Cell: 5.5 km | Conf: >= 50 | Overlap Corr: r=0.96    | Source URL / Tool JSON    |
+-------------------------------------------------------+---------------------------+
```

### 3.1 Top App Bar & Offline Status Indicator
- **Badge Indicator**: Displays data provenance state (`LIVE`, `CACHE`, or `FIXTURE`) next to a green/amber connection dot.
- **Timestamp Marker**: Shows "Data Last Updated: [ISO Timestamp]" so field operators can evaluate data freshness immediately.
- **Offline Download Manager Button**: Triggers the spatial bounding box modal for downloading region packages.

### 3.2 Main Map View (`MapLibre GL` + `deck.gl`)
- **PMTiles Basemap**: Reads pre-packaged local vector tiles (`bd.pmtiles`) offline.
- **Grid Cell Layer**: Renders aggregated $5.5\text{ km}$ spatial cells ($\approx 0.05^\circ$) dynamically colored by peak FRP (Fire Radiative Power) or cell-day activity.
- **Raw Hotspot Layer**: Displays individual sensor detection points with confidence filtering ($\ge 50$).

### 3.3 Control Toolbar & Harmonization Toggle
- **Global Harmonization Toggle**: A single state control that seamlessly toggles the map, calendar, and analytics between:
  1. *Raw Counts*: Unadjusted daily detections (showing artificial step-changes at sensor transitions).
  2. *Harmonized Counts*: Collapsed same-day cell-day detections ($1\text{ cell-day} = 1\text{ count}$).
- **Timeline Slider**: Dual-range date picker covering 2003–2026 with play/pause animations for seasonal transitions.

### 3.4 Year-by-Day Burning Calendar Heatmap
- **Matrix View**: Displays day-of-year ($x$-axis, 1–365) vs. year ($y$-axis, 2003–2026).
- **Interactive Hover**: Shows historical daily counts and seasonal baseline percentiles.
- **Harmonization Alignment**: Instantly re-renders when the global Raw/Harmonized toggle is switched.

### 3.5 Anomaly & Baseline Query Card
- **Natural Language Question**: *"Is this burning activity unusual for this place and time of year?"*
- **Statistical Response**: Returns day-of-year percentiles and baseline windows computed from the multi-decade harmonized record.

### 3.6 Methods & Validation Panel
- **Methodology Transparency**: Summarizes grid cell resolution ($5.5\text{ km}$), confidence cutoffs ($\ge 50$), collapse logic, and overlap validation correlation coefficients ($r_{\text{raw}}$ vs. $r_{\text{harmonized}}$).
- **Sensor Sunset Warning Banner**: Explicitly alerts users regarding the retirement of Suomi-NPP (1 Nov 2026) and Terra/Aqua MODIS (late 2026).

### 3.7 Provenance Drawer (Slide-Out Panel)
- **100% Auditability**: Displays raw tool call JSON, execution timestamps, dataset IDs, and direct NASA source URLs for every figure shown on screen.

---

## 4. Offline Caching Strategy & Data Synchronization

The application relies on a progressive storage hierarchy to guarantee performance without connectivity:

```
                  +-----------------------------------+
                  |      Browser Request Event        |
                  +-----------------+-----------------+
                                    |
                    +---------------+---------------+
                    | Is Service Worker Active?     |
                    +-------+---------------+-------+
                            |               |
                   YES      |               | NO
                            v               v
            +---------------+-------+    +--+----------------+
            | Match Asset Route     |    | Direct Fetch      |
            +-------+-------+-------+    +-------------------+
                    |       |
      App Shell /   |       | PMTiles /
      Static Assets |       | Geoparquet Data
                    v       v
   +----------------+--+ +--+----------------+
   | Precache          | | Cache-First       |
   | (Serve Instant)   | | (IndexedDB/OPFS)  |
   +-------------------+ +-------------------+
```

### 4.1 Workbox Caching Policies
1. **App Shell Assets (`/`, `/index.html`, `/js/*`, `/css/*`)**: Pre-cached on install; served `CacheFirst` with background update checks.
2. **Basemaps (`*.pmtiles`, `*.geojson`)**: Stored in Cache API / OPFS; served `CacheFirst`.
3. **Data Parquet & GeoTIFFs (`cache/*.parquet`, `*.cog`)**: Served via `StaleWhileRevalidate` with direct DuckDB-WASM fallback.
4. **API Requests (`/api/*`)**: Served live when connected; falls back to `IndexedDB` fixtures when offline.

### 4.2 Storage Persistence Protocol
To prevent browser storage pressure from purging cached satellite maps and parquet databases, the frontend issues a persistent storage request on initial load:

```typescript
// src/services/storage.ts
export async function enablePersistentStorage(): Promise<boolean> {
  if (navigator.storage && navigator.storage.persist) {
    const isPersisted = await navigator.storage.persist();
    console.log(`[Storage] Persistent storage enabled: ${isPersisted}`);
    return isPersisted;
  }
  return false;
}
```

### 4.3 Spatial Bounding Box Download Manager
Field workers can pre-package custom regions prior to deployment:
1. **Bounding Box Selector**: Interactive bounding box selection tool (e.g., Bangladesh `88°E, 20°N, 93°E, 27°N`).
2. **Layer Picker**: Toggle MODIS archives, VIIRS archives, PMTiles basemaps, and NASA POWER climate series.
3. **Download Progress & Quota Bar**: Real-time display of downloaded bytes, download speeds, and browser storage capacity.

---

## 5. Graceful AI & Feature Degradation

The interface maintains complete functionality across varying levels of backend availability:

| Backend State | AI Agent Panel Behavior | Geospatial Analytics Capabilities | Data Source Mode Badge |
| :--- | :--- | :--- | :--- |
| **Fully Online** (FastAPI + MCP) | Interactive AI query box enabled with live tool execution. | Full client + server execution over live FIRMS/POWER APIs. | `LIVE` |
| **Offline (Local Backend)** | AI panel uses local cached responses or Ollama (if configured). | Full DuckDB-WASM execution over cached GeoParquet files. | `CACHE` |
| **Offline (Static PWA Only)** | AI panel **automatically hidden** to prevent errors. | Full deterministic mapping, toggling, and calendar heatmaps. | `FIXTURE` |

---

## 6. Self-Hosted Asset Manifest (Zero External CDN Dependencies)

To guarantee that a cold start offline never attempts external HTTP requests:

1. **Fonts**: Inter and JetBrains Mono fonts self-hosted as WOFF2 in `/web/public/fonts/`.
2. **Map Glyphs & Sprites**: MapLibre vector PBF glyphs and map icons pre-built into `/web/public/sprites/`.
3. **Textures**: Three.js Earth specular/bump maps stored locally in `/web/public/textures/`.
4. **Static Libraries**: React, MapLibre GL, and deck.gl bundled cleanly via Vite into local vendor chunks.

---

## 7. Verification & PWA Compliance Checklist

- [x] **Chrome DevTools Offline Mode**: Complete application boot and map rendering tested with network disabled.
- [x] **Lighthouse PWA Audit**: Passes service worker, offline load, fast load, and manifest checks.
- [x] **Airplane Mode Test**: Verified on target mobile/laptop hardware without cellular or Wi-Fi connectivity.
- [x] **Deterministic Science Gate**: Confirmed zero LLM dependencies for spatial grid clustering and anomaly calculations.
