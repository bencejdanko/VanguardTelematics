import asyncio
import logging
import os
import json
import time
import math
import redis.asyncio as aioredis
try:
    from deepgram import DeepgramClient, SpeakOptions
except ImportError:
    # deepgram-sdk ≥ 7 restructured the speak API.
    # TTS dispatch will be skipped until the package is aligned.
    DeepgramClient = None  # type: ignore[assignment,misc]
    class SpeakOptions:  # type: ignore[no-redef]
        def __init__(self, **kwargs): pass

logger = logging.getLogger("datalogfusion.analytics")

REDIS_HOST = os.getenv("REDIS_HOST", "coat-generous-snow-13477.db.redis.io")
REDIS_PORT = int(os.getenv("REDIS_PORT", "13011"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "AU0X7vgAPgJ6lLt6f4yeZQgwlVIyc0XN")
STREAM_KEY = os.getenv("REDIS_STREAM_KEY", "sensor:stream")

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

async def trigger_radio_dispatch(vehicle_id: str, incident_type: str):
    logger.warning(f"EMERGENCY on {vehicle_id}: {incident_type}. Triggering dispatch.")
    if not DEEPGRAM_API_KEY:
        logger.error("DEEPGRAM_API_KEY not set! Skipping TTS generation.")
        return

    try:
        if DeepgramClient is None:
            logger.error("DeepgramClient unavailable (SDK version mismatch). Skipping TTS.")
            return
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        text = f"Attention dispatch. Unit {vehicle_id} {incident_type} detected. High confidence. Crew status unknown. Immediate assistance requested."
        options = SpeakOptions(
            model="aura-asteria-en",
        )
        
        filename = f"dispatch_{vehicle_id}.mp3"
        # Deepgram Python SDK sync method wrapped in to_thread
        await asyncio.to_thread(
            deepgram.speak.rest.v("1").save,
            filename,
            {"text": text},
            options
        )
        logger.info(f"Generated Deepgram TTS audio file: {filename}")
    except Exception as e:
        logger.error(f"Deepgram TTS failed: {e}")

async def analytics_worker():
    logger.info("Starting background analytics worker for Predictive Maintenance & Emergencies...")
    r = aioredis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        username=REDIS_USERNAME, 
        password=REDIS_PASSWORD, 
        decode_responses=True,
        socket_connect_timeout=10
    )
    last_id = "$"
    
    # State for predictive maintenance
    maintenance_windows = {}
    # State for emergency detection
    vehicle_states = {}

    while True:
        try:
            results = await r.xread({STREAM_KEY: last_id}, block=5000, count=50)
            if not results:
                continue

            for _stream, entries in results:
                for entry_id, fields in entries:
                    last_id = entry_id
                    vehicle_id = fields.get("vehicle_id", "V-001") # Default for load_sample.py
                    
                    # 1. Smart Emergency Detection
                    acc_x = float(fields.get("acc_x", fields.get("acc_x_mg", 0)))
                    acc_y = float(fields.get("acc_y", fields.get("acc_y_mg", 0)))
                    acc_z = float(fields.get("acc_z", fields.get("acc_z_mg", 0)))

                    if vehicle_id not in vehicle_states:
                        vehicle_states[vehicle_id] = {
                            "tilt_frames": 0,
                            "last_incident_time": 0,
                            "prev_g_force": 1.0,
                            "base_acc_x": acc_x,
                            "base_acc_y": acc_y,
                            "base_acc_z": acc_z,
                        }
                    state = vehicle_states[vehicle_id]
                    
                    acc_mag = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
                    g_force = acc_mag / 1000.0
                    jerk = abs(g_force - state["prev_g_force"])
                    state["prev_g_force"] = g_force
                    
                    # Rollover logic using 3D acceleration vector (robust against Euler lock/offsets)
                    base_x = state["base_acc_x"]
                    base_y = state["base_acc_y"]
                    base_z = state["base_acc_z"]
                    base_mag = math.sqrt(base_x**2 + base_y**2 + base_z**2)
                    
                    if acc_mag > 0 and base_mag > 0:
                        dot_product = (acc_x * base_x) + (acc_y * base_y) + (acc_z * base_z)
                        cos_theta = dot_product / (acc_mag * base_mag)
                        # cos(60 degrees) = 0.5. If cos_theta < 0.5, tilt is > 60 degrees.
                        if cos_theta < 0.5:
                            state["tilt_frames"] += 1
                        else:
                            state["tilt_frames"] = 0
                    else:
                        state["tilt_frames"] = 0
                        
                    incident_type = None
                    current_time = time.time()
                    
                    # Cooldown of 5 seconds between reported incidents
                    if current_time - state["last_incident_time"] > 5.0:
                        if g_force > 6.0 and jerk > 4.0:
                            incident_type = "High-Impact Crash"
                            state["last_incident_time"] = current_time
                        elif state["tilt_frames"] >= 50:
                            incident_type = "Rollover"
                            state["last_incident_time"] = current_time
                            state["tilt_frames"] = 0 # reset after trigger

                    if incident_type:
                        # Broadcast emergency to SSE listeners via Redis PubSub
                        await r.publish("emergency_channel", json.dumps({
                            "vehicle_id": vehicle_id, 
                            "reason": incident_type
                        }))
                        # Trigger Deepgram Radio Broadcast
                        await trigger_radio_dispatch(vehicle_id, incident_type)

                    # 2. Predictive Maintenance: Track moving average of Pressure
                    press = float(fields.get("press_hpa", 1013.25))
                    
                    if vehicle_id not in maintenance_windows:
                        maintenance_windows[vehicle_id] = []
                    
                    window = maintenance_windows[vehicle_id]
                    window.append(press)
                    if len(window) > 100:
                        window.pop(0)
                        
                        avg_press = sum(window) / len(window)
                        if avg_press < 1000.0:  # Arbitrary anomaly threshold
                            logger.info(f"Predictive Maintenance Alert: {vehicle_id} pressure dropping (Avg: {avg_press:.2f})")
                            await r.publish("maintenance_channel", json.dumps({
                                "vehicle_id": vehicle_id, 
                                "reason": "Pressure anomaly detected"
                            }))
                            window.clear() # Reset after alert

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"Analytics worker error: {exc}")
            await asyncio.sleep(2)
            
    await r.aclose()
