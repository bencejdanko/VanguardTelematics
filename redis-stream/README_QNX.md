# QNX Streaming to Redis Database

Streams live MEMS sensor data from the STM32 board (connected via USB-serial at
`/dev/serusb1`) to the shared Redis Cloud stream **`/data/mems`** using a
single, dependency-free C program: **`main.c`**.

No external libraries are required — only standard POSIX sockets and termios,
which QNX Neutrino supports natively.

---

## File Overview

| File | Description |
|------|-------------|
| `main.c` | Self-contained C streamer (QNX / any POSIX target) |
| `redis_stream.py` | Python streamer (Windows / Linux / WSL2) |
| `README.md` | General setup notes |
| `README_QNX.md` | This file — QNX-specific build instructions |

---

## Redis Stream Details

| Property | Value |
|----------|-------|
| **Endpoint** | `hospitable-van-guitar-57111.db.redis.io:17434` |
| **Stream key** | `/data/mems` |
| **User** | `default` |
| **Fields per entry** | `ts, acc_x, acc_y, acc_z, gyr_x, gyr_y, gyr_z, mag_x, mag_y, mag_z, press, roll, pitch, yaw` |
| **Protocol** | Raw RESP over TCP (no TLS) |

---

## Building on QNX (native compile on the target)

If your QNX image includes a C compiler (`qcc` or `cc`):

```sh
# first on host machine copy over

scp -o MACs=hmac-sha2-256 main.c qnxuser@172.20.10.7:/data/home/qnxuser

# On the QNX Raspberry Pi target
cc -o mems_stream main.c -lsocket
```

> **Note:** On some QNX builds the socket functions live in `libc` and `-lsocket`
> is not needed. If you get linker errors, try without it:
> ```sh
> cc -o mems_stream mems_stream.c
> ```

---

## Cross-Compiling from a QNX SDP Host (Linux / Windows)

If you have the **QNX Software Development Platform (SDP)** installed on your
development machine, cross-compile with the `qcc` wrapper:

### 1. Initialise the QNX environment

```sh
# Adjust the path to match your SDP version (7.1 / 8.0 etc.)
source ~/qnx800/qnxsdp-env.sh
```

### 2. Identify your target architecture

| Raspberry Pi model | Architecture flag |
|--------------------|-------------------|
| RPi 3 / 4 (64-bit QNX) | `gcc_ntoaarch64le` |
| RPi 2 / Zero (32-bit QNX) | `gcc_ntoarmv7le` |

### 3. Compile

```sh
# 64-bit ARM (most common for RPi 3/4)
qcc -V gcc_ntoaarch64le -o mems_stream mems_stream.c -lsocket

# 32-bit ARM
qcc -V gcc_ntoarmv7le  -o mems_stream mems_stream.c -lsocket
```

### 4. Copy the binary to the target

```sh
scp mems_stream user@<rpi-ip>:/home/user/
```

---

## Running

```sh
# Default: /dev/serusb1 @ 115200 baud
./mems_stream

# Override serial device
./mems_stream /dev/serusb2
```

The program prints a startup banner and then logs a line every 10 samples
(~100 ms at 100 Hz):

```
==================================================
 STM32 MEMS → Redis Streamer  (QNX / C)
==================================================
Serial device : /dev/serusb1  @ 115200 baud
Redis endpoint: hospitable-van-guitar-57111.db.redis.io:17434
Redis stream  : /data/mems
Batch size    : 10 samples
--------------------------------------------------
Opening serial port...
Serial port opened.
Connecting to Redis...
TCP connection established.
Authenticated to Redis.
Streaming started. Press Ctrl+C to stop.

[10]  Pushed 10 samples to /data/mems
[20]  Pushed 10 samples to /data/mems
...
```

Press **Ctrl+C** to stop cleanly.

---

## Runtime Environment Variable Overrides

You can override the compiled-in Redis credentials at runtime without
recompiling:

```sh
export REDIS_HOST="hospitable-van-guitar-57111.db.redis.io"
export REDIS_PORT="17434"
export REDIS_PASS=
./mems_stream
```