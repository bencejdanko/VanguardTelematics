import asyncio
import random
import time
import logging
import os
import redis.asyncio as aioredis

logger = logging.getLogger("datalogfusion.simulator")

REDIS_HOST = os.getenv("REDIS_HOST", "coat-generous-snow-13477.db.redis.io")
REDIS_PORT = int(os.getenv("REDIS_PORT", "13011"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "AU0X7vgAPgJ6lLt6f4yeZQgwlVIyc0XN")
STREAM_KEY = os.getenv("REDIS_STREAM_KEY", "sensor:stream")
LATEST_KEY = os.getenv("REDIS_LATEST_KEY", "sensor:latest")

async def simulator_worker():
    logger.info("Starting background simulator worker for V-002 and V-003...")
    r = aioredis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True, socket_connect_timeout=30, socket_timeout=30, retry_on_timeout=True,
        
    )
    
    vehicles = ["V-002", "V-003", "V-004"]
    
    # Baseline values for a normal vehicle
    baseline = {
        "acc_x": 0.0,
        "acc_y": 0.0,
        "acc_z": 980.0,  # ~1g in mg
        "gyr_x": 0.0,
        "gyr_y": 0.0,
        "gyr_z": 0.0,
        "mag_x": 0.0,
        "mag_y": 0.0,
        "mag_z": 0.0,
        "press": 1013.25,
        "pitch": 0.0,
        "roll": 0.0,
        "yaw": 0.0
    }
    
    # Register them as active
    for v_id in vehicles:
        await r.sadd("active_vehicles", v_id)

    while True:
        try:
            for v_id in vehicles:
                # Add continuous random fluctuation
                payload = {
                    "vehicle_id": v_id,
                    "acc_x": baseline["acc_x"] + random.uniform(-10, 10),
                    "acc_y": baseline["acc_y"] + random.uniform(-10, 10),
                    "acc_z": baseline["acc_z"] + random.uniform(-10, 10),
                    "gyr_x": baseline["gyr_x"] + random.uniform(-50, 50),
                    "gyr_y": baseline["gyr_y"] + random.uniform(-50, 50),
                    "gyr_z": baseline["gyr_z"] + random.uniform(-50, 50),
                    "mag_x": baseline["mag_x"] + random.uniform(-5, 5),
                    "mag_y": baseline["mag_y"] + random.uniform(-5, 5),
                    "mag_z": baseline["mag_z"] + random.uniform(-5, 5),
                    "press": baseline["press"] + random.uniform(-0.1, 0.1),
                    "pitch": baseline["pitch"] + random.uniform(-0.5, 0.5),
                    "roll": baseline["roll"] + random.uniform(-0.5, 0.5),
                    "yaw": baseline["yaw"] + random.uniform(-0.5, 0.5),
                }
                
                # Push to Redis stream and hash
                await r.xadd(STREAM_KEY, payload, maxlen=50000, approximate=True)
                # Note: hset with LATEST_KEY will overwrite, but the dashboard reads from /stream mostly
                await r.hset(LATEST_KEY, mapping=payload)
                
            # Sleep to match ~10Hz per vehicle, wait 0.1s
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"Simulator worker error: {exc}")
            await asyncio.sleep(2)
