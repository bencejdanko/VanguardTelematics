import sys
import os
import time
import serial
import redis
from queue import Queue
from threading import Thread

# Redis cloud connection details
REDIS_URL = ""

# Default configuration
DEFAULT_BAUD = 115200
DEFAULT_PORT_WIN = "COM5"
DEFAULT_PORT_LINUX = "/dev/ttyS5"

# Thread-safe queue for buffering parsed samples
data_queue = Queue()

def parse_line(line):
    """
    Parses a CSV line from the serial port.
    Expected format: timestamp,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,mag_x,mag_y,mag_z,press,roll,pitch,yaw
    """
    line = line.strip()
    if not line or line.startswith("timestamp"):
        return None
    
    parts = line.split(',')
    if len(parts) < 14:
        return None
        
    try:
        return {
            "timestamp": parts[0],
            "acc_x": float(parts[1]),
            "acc_y": float(parts[2]),
            "acc_z": float(parts[3]),
            "gyr_x": float(parts[4]),
            "gyr_y": float(parts[5]),
            "gyr_z": float(parts[6]),
            "mag_x": float(parts[7]),
            "mag_y": float(parts[8]),
            "mag_z": float(parts[9]),
            "press": float(parts[10]),
            "roll": float(parts[11]),
            "pitch": float(parts[12]),
            "yaw": float(parts[13])
        }
    except ValueError:
        return None

def redis_writer(redis_url):
    """
    Background worker thread that batches data from the queue and sends it to Redis.
    """
    print(f"Connecting to Redis at {redis_url.split('@')[1]}...")
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        r.ping()
        print("Connected to Redis successfully!")
    except Exception as e:
        print(f"Error connecting to Redis: {e}")
        sys.exit(1)

    batch = []
    last_flush = time.time()
    
    while True:
        try:
            # Block for up to 10ms to get a sample
            sample = data_queue.get(timeout=0.01)
            batch.append(sample)
            data_queue.task_done()
        except:
            pass # Timeout reached, no new item in queue
            
        # Flush condition: batch size >= 10 (100ms of data) or elapsed time > 100ms
        if batch and (len(batch) >= 10 or (time.time() - last_flush) >= 0.1):
            try:
                pipe = r.pipeline()
                for s in batch:
                    # Pushing all fields into a single stream endpoint
                    pipe.xadd("/data/mems", {
                        "ts": s["timestamp"],
                        "acc_x": s["acc_x"],
                        "acc_y": s["acc_y"],
                        "acc_z": s["acc_z"],
                        "gyr_x": s["gyr_x"],
                        "gyr_y": s["gyr_y"],
                        "gyr_z": s["gyr_z"],
                        "mag_x": s["mag_x"],
                        "mag_y": s["mag_y"],
                        "mag_z": s["mag_z"],
                        "press": s["press"],
                        "roll": s["roll"],
                        "pitch": s["pitch"],
                        "yaw": s["yaw"]
                    })
                
                pipe.execute()
                print(f"Pushed {len(batch)} samples to /data/mems stream. (Queue size: {data_queue.qsize()})")
            except Exception as e:
                print(f"Error writing to Redis: {e}")
            finally:
                batch.clear()
                last_flush = time.time()

def main():
    # Determine default port based on OS
    default_port = DEFAULT_PORT_WIN if os.name == 'nt' else DEFAULT_PORT_LINUX
    
    # Allow command line override
    port = sys.argv[1] if len(sys.argv) > 1 else default_port
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUD
    
    # Check if target is a simulation file
    is_simulation = os.path.isfile(port)
    
    print("==================================================")
    print(" STM32 MEMS to Redis Streamer")
    print("==================================================")
    if is_simulation:
        print(f"Mode:        Simulation (Streaming from file)")
        print(f"File Path:   {port}")
    else:
        print(f"Mode:        Serial Port (Real Hardware)")
        print(f"Serial Port: {port}")
        print(f"Baud Rate:   {baud}")
    print("--------------------------------------------------")
    
    # Start Redis writer thread
    writer_thread = Thread(target=redis_writer, args=(REDIS_URL,), daemon=True)
    writer_thread.start()
    
    if is_simulation:
        print(f"Reading simulation file '{port}'...")
        try:
            with open(port, 'r') as f:
                lines = f.readlines()
            print(f"Loaded {len(lines)} lines from simulation file.")
        except Exception as e:
            print(f"Error reading simulation file: {e}")
            sys.exit(1)
            
        print("Streaming started. Press Ctrl+C to stop.")
        try:
            while True:
                for line in lines:
                    sample = parse_line(line)
                    if sample:
                        data_queue.put(sample)
                    time.sleep(0.01) # Simulate 100 Hz sampling rate
        except KeyboardInterrupt:
            print("\nStopping streamer...")
        finally:
            print("Goodbye!")
            
    else:
        # Connect to serial port
        print(f"Opening serial port {port}...")
        try:
            ser = serial.Serial(port, baud, timeout=1)
            ser.flushInput()
            print("Serial port opened successfully!")
        except Exception as e:
            print(f"Error opening serial port: {e}")
            if os.name != 'nt' and port.startswith('/dev/ttyS'):
                print("\nTIP: If running in WSL2, you might need to run:")
                print(f"  sudo chmod 666 {port}")
            sys.exit(1)
            
        print("Streaming started. Press Ctrl+C to stop.")
        
        try:
            while True:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore')
                    sample = parse_line(line)
                    if sample:
                        data_queue.put(sample)
                except Exception as ser_err:
                    print(f"Serial read error: {ser_err}")
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopping streamer...")
        finally:
            if 'ser' in locals() and ser.isOpen():
                ser.close()
            print("Serial port closed. Goodbye!")

if __name__ == "__main__":
    main()
