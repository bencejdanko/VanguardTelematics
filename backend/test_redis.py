import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
import redis.asyncio as aioredis

async def main():
    r = aioredis.Redis(
        host=os.getenv('REDIS_HOST'), 
        port=int(os.getenv('REDIS_PORT')), 
        username=os.getenv('REDIS_USERNAME'), 
        password=os.getenv('REDIS_PASSWORD'), 
        decode_responses=True
    )
    res = await r.xrevrange(os.getenv('REDIS_STREAM_KEY'), count=1)
    for entry_id, fields in res:
        print(f"entry_id: {entry_id}")
        for k, v in fields.items():
            print(f"  {k}: {v} (type: {type(v)})")
        break
    await r.aclose()
asyncio.run(main())
