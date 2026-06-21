# Redis Cloud Sensor Streamer

A high-performance Python script to stream STM32 MEMS sensor data (via CSV over serial/VCOM) directly to Redis Cloud streams.

## Prerequisites

Install Python dependencies:
```bash
pip install pyserial redis
```

## How to Run

The script (`redis_stream.py`) runs identically on both Windows and Linux/WSL2:

### Option A: Run Natively in Windows (Recommended)
Running natively in a Windows terminal (cmd or PowerShell) is recommended since it has native plug-and-play access to your USB COM ports without any mounting/virtualization layers.

```bash
python redis_stream.py COM5 115200
```

### Option B: Run in WSL2 (Debian)
If you prefer running inside WSL2:
1. Ensure your user has permissions to access the serial port:
   ```bash
   sudo chmod 666 /dev/ttyS5
   ```
2. Run the script pointing to `/dev/ttyS5` (which corresponds to `COM5`):
   ```bash
   python3 redis_stream.py /dev/ttyS5 115200
   ```

### Option C: Run in File Simulation Mode (Offline Testing)
If the serial port is locked or the hardware is not currently connected, you can stream mock data from a CSV file (like `sample.csv`) at a simulated 100 Hz:

```bash
# Relative path to sample.csv
python redis_stream.py ../sample-data/sample.csv
```

*Note: In simulation mode, the script loops continuously over the file to provide an infinite stream for testing.*

---

## Stream Endpoint Mapping
To maximize performance and keep network utilization low, all 13 sensor metrics are published together under a **single stream endpoint** at `/data/mems`:

* **Stream Endpoint**: `/data/mems`
* **Message Fields**:
  - `ts`: Timestamp (`HH:MM:SS.hh`)
  - `acc_x`, `acc_y`, `acc_z`: Accelerometer axes ($mg$)
  - `gyr_x`, `gyr_y`, `gyr_z`: Gyroscope axes ($mdps$)
  - `mag_x`, `mag_y`, `mag_z`: Magnetometer axes ($mgauss$)
  - `press`: Pressure ($hPa$)
  - `roll`, `pitch`, `yaw`: Euler orientation angles (degrees)