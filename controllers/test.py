import requests
import settings
import discord
import time
import asyncio

async def get_character(charName: str):
    # requests.put(settings.FIREBASE_COMMAND_PATH, json='read_temperature')
    
    character_name = charName
    
    for _ in range(20):
        response = requests.get(f'{settings.FIREBASE_API_SECRET}/Char_{character_name}.json')
        if response.status_code == 200:
            data = response.json()
            
            return data
        await asyncio.sleep(0.5)
        
    # requests.put(settings.FIREBASE_COMMAND_PATH, json="idle")
    return None

async def put_character():
    json = {
        "data" : "test",
        "hehe" : 3
    }
    requests.put(f'{settings.FIREBASE_API_SECRET}/test_data', json=json)
    