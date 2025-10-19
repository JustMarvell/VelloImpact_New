import requests
import settings

async def PostWebhook(json : dict):
    req = requests.post(settings.DISCORD_WEBHOOK_URL_SECRET, json=json)
    if 200 <= req.status_code < 300:
        return True
    else:
        return False