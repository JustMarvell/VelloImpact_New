import requests
import settings

async def PostWebhook(json : dict):
    try:
        requests.post(settings.DISCORD_WEBHOOK_URL_SECRET, json=json)
        return True
    except Exception as e:
        return e