import rpi_gpio as GPIO
import time
import urllib.request
import subprocess
import os

import threading

# Configuration
SIG_PIN = 21
LED_PIN = 20
# Replace with your laptop's local IP address on your network
LAPTOP_URL = "http://172.20.10.3:8080/feed" 
STREAM_TIMEOUT = 10 # Keep streaming 10 seconds after last motion detection
DOWNSAMPLE_FACTOR = 2 # Factor to downsample raw YCBYCR frame (1 to disable)
POST_TIMEOUT = 5.0 # Timeout in seconds for HTTP upload POST requests

# C Capture Utility paths
BINARY_PATH = "./camera_capture"
DUMP_DIR = "/tmp"
RAW_FILE = "/tmp/frame0.raw"

# Shared state
last_trigger_time = 0
last_attempt_time = 0  # Cooldown tracker
streaming = False
stream_lock = threading.Lock()

def downsample_ycbycr(frame_bytes, width, height, factor=2):
    """
    Downsamples a YCBYCR (YUYV) frame by the given factor.
    YCBYCR is a packed YUV 4:2:2 format: 4 bytes per 2 pixels (Y1, U, Y2, V).
    A row has width * 2 bytes.
    We take every 'factor' rows.
    In each row, we take every 'factor' blocks of 4 bytes.
    """
    if factor <= 1:
        return frame_bytes, width, height

    row_stride = width * 2
    new_width = width // factor
    # Ensure new_width is even (YCBYCR needs even width since 2 pixels per block)
    if new_width % 2 != 0:
        new_width = (new_width // 2) * 2
        
    new_height = height // factor
    
    block_step = 4 * factor
    bytes_per_row_to_keep = (new_width // 2) * 4  # Each 2 pixels is a 4-byte block
    
    out_rows = []
    for r in range(0, height, factor):
        if len(out_rows) >= new_height:
            break
        row_start = r * row_stride
        row_data = frame_bytes[row_start : row_start + row_stride]
        
        # Extract the blocks
        row_chunks = [row_data[i : i + 4] for i in range(0, len(row_data), block_step)]
        row_bytes = b"".join(row_chunks)[:bytes_per_row_to_keep]
        out_rows.append(row_bytes)
        
    downsampled_bytes = b"".join(out_rows)
    return downsampled_bytes, new_width, new_height

def camera_stream_worker():
    global streaming
    print("[Camera] Background thread started. Streaming using QNX camera_capture C utility...")
    try:
        while True:
            with stream_lock:
                is_active = (time.time() - last_trigger_time < STREAM_TIMEOUT)
                if not is_active:
                    print("[Camera] Timeout reached. Stopping C capture stream...")
                    streaming = False
                    break
            
            try:
                # Clean up any leftover file from a previous frame
                if os.path.exists(RAW_FILE):
                    os.remove(RAW_FILE)

                # Execute compiled C capture utility
                # It dumps the single frame to /tmp/frame0.raw and writes meta to stdout
                result = subprocess.run(
                    [BINARY_PATH, "-f", DUMP_DIR],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3.0
                )
                
                # Parse stdout for: "[Camera] Meta: <width>x<height> fmt=<fmt> stride=<stride> size=<size>"
                meta_line = None
                for line in result.stdout.split("\n"):
                    if "[Camera] Meta:" in line:
                        meta_line = line
                        break
                
                if meta_line and os.path.exists(RAW_FILE):
                    parts = meta_line.split()
                    dims = parts[2].split("x")
                    width = int(dims[0])
                    height = int(dims[1])
                    fmt = int(parts[3].split("=")[1])
                    stride = int(parts[4].split("=")[1])
                    
                    with open(RAW_FILE, "rb") as f:
                        frame_bytes = f.read()
                    
                    # Sanity check frame size
                    expected_size = width * height * 2
                    if len(frame_bytes) < expected_size:
                        print(f"[Camera] Warning: Read truncated local file of size {len(frame_bytes)} (expected {expected_size})")
                    
                    # Apply downsampling if requested and supported
                    if fmt == 14 and DOWNSAMPLE_FACTOR > 1:
                        frame_bytes, new_w, new_h = downsample_ycbycr(frame_bytes, width, height, DOWNSAMPLE_FACTOR)
                        # print(f"[Camera] Downsampled from {width}x{height} to {new_w}x{new_h} ({len(frame_bytes)} bytes)")
                        width = new_w
                        height = new_h
                        stride = new_w * 2

                    # POST raw pixels directly to laptop with metadata headers
                    req = urllib.request.Request(
                        LAPTOP_URL, 
                        data=frame_bytes, 
                        headers={
                            'Content-Type': 'application/octet-stream',
                            'X-Width': str(width),
                            'X-Height': str(height),
                            'X-Format': str(fmt),
                            'X-Stride': str(stride)
                        }
                    )
                    with urllib.request.urlopen(req, timeout=POST_TIMEOUT) as response:
                        response.read()
                else:
                    # Thread cooldown on capture failure to prevent fast loop spam
                    time.sleep(1.0)
            except Exception as e:
                print("[Camera] Capture or transfer failed:", e)
                time.sleep(1.0)
            
            # Send at ~20 FPS (50ms loop interval)
            time.sleep(0.05)
    finally:
        # Clean up raw file
        if os.path.exists(RAW_FILE):
            try:
                os.remove(RAW_FILE)
            except Exception:
                pass
        print("[Camera] Background thread finished.")

def main():
    global last_trigger_time, last_attempt_time, streaming
    GPIO.setup(SIG_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(LED_PIN, GPIO.OUT)
    
    print("Pi Sentry monitoring IR sensor...")
    try:
        while True:
            # Active-low detection: 0 = obstacle detected
            if GPIO.input(SIG_PIN) == 0:
                GPIO.output(LED_PIN, GPIO.HIGH)
                
                with stream_lock:
                    last_trigger_time = time.time()
                    current_time = time.time()
                    
                    # Only try to spawn the camera thread if not already running AND after a 10s cooldown
                    if not streaming and (current_time - last_attempt_time > 10.0):
                        print("[Pi] Trigger detected! Starting background camera thread...")
                        streaming = True
                        last_attempt_time = current_time
                        t = threading.Thread(target=camera_stream_worker, daemon=True)
                        t.start()
            else:
                GPIO.output(LED_PIN, GPIO.LOW)
                
            time.sleep(0.05) # Poll sensor every 50ms
    except KeyboardInterrupt:
        print("\nStopping Pi client.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
