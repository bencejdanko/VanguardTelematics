# DataLogFusion Backend

HTTP API server that reads live sensor data from Redis Cloud and serves it to the dashboard.

## Data Flow

```
Redis Cloud (sensor:stream / sensor:latest)
        │
        ▼
    api.py  (FastAPI + uvicorn)
        │
   ┌────┴─────┐
   ▼          ▼
GET /latest  GET /stream
(snapshot)   (SSE — live feed)
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Redis connection check |
| `GET /latest` | Latest sensor reading (JSON) |
| `GET /history?count=N` | Last N readings, newest first (default 100) |
| `GET /stream` | SSE live feed — streams every new reading |

## Setup

```bash
pip install -r requirements.txt
python main.py
```

Server starts on `http://0.0.0.0:8000`.

## Connect from a dashboard

**Snapshot:**
```js
const res = await fetch('http://localhost:8000/latest');
const data = await res.json();
```

**Live SSE stream:**
```js
const source = new EventSource('http://localhost:8000/stream');
source.onmessage = (e) => {
  const reading = JSON.parse(e.data);
  // { id, timestamp, acc_x_mg, gyr_x_mdps, roll_deg, ... }
};
```

## No live data? Load the sample CSV

```bash
python load_sample.py
```

Pushes all 1013 rows from `sample-data/sample.csv` into Redis for testing.

## Redis Keys

| Key | Type | Description |
|---|---|---|
| `/data/mems` | Stream | Full time-series (`XADD`) |
| `sensor:latest` | Hash | Latest reading only (`HSET`) |

## Fields

| Field | Type | Unit |
|---|---|---|
| `timestamp` | string | HH:MM:SS.hh |
| `acc_x_mg` / `y` / `z` | int | mg |
| `gyr_x_mdps` / `y` / `z` | int | mdps |
| `mag_x_mgauss` / `y` / `z` | int | mgauss |
| `press_hpa` | float | hPa |
| `roll_deg` / `pitch_deg` / `yaw_deg` | float | degrees |
