import requests
import discord
import asyncio
import settings
import firebase_admin
from firebase_admin import credentials, db

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

def initialize_app():
    cred = credentials.Certificate(f'{settings.BASE_DIR}/key.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL' : f'{settings.FIREBASE_API_SECRET}'
    })