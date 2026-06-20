import asyncio
import logging
import os
import json
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

from config import REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD, STREAM_KEY, DEEPGRAM_API_KEY

async def trigger_radio_dispatch(vehicle_id: str, reason: str):
    logger.warning(f"EMERGENCY on {vehicle_id}: {reason}. Triggering dispatch.")
    if not DEEPGRAM_API_KEY:
        logger.error("DEEPGRAM_API_KEY not set! Skipping TTS generation.")
        return

    try:
        if DeepgramClient is None:
            logger.error("DeepgramClient unavailable (SDK version mismatch). Skipping TTS.")
            return
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        text = f"Attention dispatch. Emergency detected on {vehicle_id}. Reason: {reason}. Please send immediate assistance."
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

    while True:
        try:
            results = await r.xread({STREAM_KEY: last_id}, block=5000, count=50)
            if not results:
                continue

            for _stream, entries in results:
                for entry_id, fields in entries:
                    last_id = entry_id
                    vehicle_id = fields.get("vehicle_id", "V-001") # Default for load_sample.py
                    
                    # 1. Emergency Detection: Rollover (Gyro Z > 8000) or Impact (Accel Z drops < 500)
                    gyr_z = float(fields.get("gyr_z_mdps", 0))
                    acc_z = float(fields.get("acc_z_mg", 1000))
                    
                    if abs(gyr_z) > 8000 or abs(acc_z) < 500:
                        # Broadcast emergency to SSE listeners via Redis PubSub
                        await r.publish("emergency_channel", json.dumps({
                            "vehicle_id": vehicle_id, 
                            "reason": "Rollover or Impact detected"
                        }))
                        # Trigger Deepgram Radio Broadcast
                        await trigger_radio_dispatch(vehicle_id, "Rollover or Impact detected")

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
