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

from config import (
    REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD,
    REDIS_STREAM_KEY as STREAM_KEY, DEEPGRAM_API_KEY
)

logger = logging.getLogger("datalogfusion.analytics")

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

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

async def analytics_worker():
    logger.info("Starting background analytics worker for Predictive Maintenance & Emergencies...")
    r = aioredis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        username=REDIS_USERNAME, 
        password=REDIS_PASSWORD, 
        decode_responses=True, socket_connect_timeout=30, socket_timeout=30, retry_on_timeout=True,
        
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
                    
                    if vehicle_id not in vehicle_states:
                        vehicle_states[vehicle_id] = {
                            "tilt_frames": 0,
                            "last_incident_time": 0,
                            "prev_g_force": 1.0,
                            "last_acc_x": 0.0,
                            "last_acc_y": 0.0,
                            "last_acc_z": 980.0,
                            "last_gyr_x": 0.0,
                            "last_gyr_y": 0.0,
                            "last_gyr_z": 0.0,
                            "last_press": 1013.25,
                        }
                    state = vehicle_states[vehicle_id]
                    
                    # 1. Smart Emergency Detection
                    acc_x = safe_float(fields.get("acc_x", fields.get("acc_x_mg", state["last_acc_x"])), state["last_acc_x"])
                    acc_y = safe_float(fields.get("acc_y", fields.get("acc_y_mg", state["last_acc_y"])), state["last_acc_y"])
                    acc_z = safe_float(fields.get("acc_z", fields.get("acc_z_mg", state["last_acc_z"])), state["last_acc_z"])

                    # Glitch filter: drop data point if sign flips dramatically
                    def is_false_signal(curr, prev):
                        return (curr * prev < 0) and abs(curr - prev) > 1000.0

                    if is_false_signal(acc_x, state["last_acc_x"]) or \
                       is_false_signal(acc_y, state["last_acc_y"]) or \
                       is_false_signal(acc_z, state["last_acc_z"]):
                        acc_x = state["last_acc_x"]
                        acc_y = state["last_acc_y"]
                        acc_z = state["last_acc_z"]

                    state["last_acc_x"] = acc_x
                    state["last_acc_y"] = acc_y
                    state["last_acc_z"] = acc_z

                    acc_mag = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
                    g_force = acc_mag / 1000.0
                    jerk = abs(g_force - state["prev_g_force"])
                    state["prev_g_force"] = g_force
                    
                    # Rollover logic using Gyroscope Vector ONLY
                    gyr_x = safe_float(fields.get("gyr_x", fields.get("gyr_x_mdps", state["last_gyr_x"])), state["last_gyr_x"])
                    state["last_gyr_x"] = gyr_x
                    gyr_y = safe_float(fields.get("gyr_y", fields.get("gyr_y_mdps", state["last_gyr_y"])), state["last_gyr_y"])
                    state["last_gyr_y"] = gyr_y
                    gyr_z = safe_float(fields.get("gyr_z", fields.get("gyr_z_mdps", state["last_gyr_z"])), state["last_gyr_z"])
                    state["last_gyr_z"] = gyr_z
                    gyr_mag = math.sqrt(gyr_x**2 + gyr_y**2 + gyr_z**2)
                    
                    # If rotation rate is high (e.g., > 30000 mdps = 30 dps) for a sustained period
                    if gyr_mag > 30000.0:
                        state["tilt_frames"] += 1
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
                    press = safe_float(fields.get("press_hpa", state["last_press"]), state["last_press"])
                    state["last_press"] = press
                    
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
