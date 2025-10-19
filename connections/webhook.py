import requests
import settings

async def PostWebhook(json : dict):
    result = requests.post(settings.DISCORD_WEBHOOK_URL_SECRET, json=json)
    if 200 <= result.status_code < 300:
        return True
    else:
        return False