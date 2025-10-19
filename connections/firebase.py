import requests
import discord
import asyncio
import settings

async def check_status():
    req = requests.get(settings.FIREBASE_API_SECRET + "/test_data/status.json")
    if req.status_code == 200:
        status = str(req.json())
        return status
    else:
        return "NONE"
    
async def wait_for_result(path, key=None, expected_type=None, timeout=10):
    for _ in range(timeout * 2):
        response = requests.get(path)
        if response.status_code == 200:
            data = response.json()
            if expected_type and not isinstance(data, expected_type):
                await asyncio.sleep(0.5)
                continue
            return data[key] if key else data
        await asyncio.sleep(0.5)
    return None 