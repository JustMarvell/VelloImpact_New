import random
import string
import settings
import requests
from youtubesearchpython import VideosSearch
import zenquotespy

async def get_random_video():
    # Generate a random query: 4-6 random letters
    query_length = random.randint(4, 6)
    query = ''.join(random.choice(string.ascii_letters) for _ in range(query_length))
    
    # Search for videos
    search = VideosSearch(query, limit=2)  # Get 5 to pick random one
    results = search.result()['result']
    
    if not results:
        await get_random_video()  # Recurse, but be careful with stack
        return
    
    # Pick a random one from the results
    video = random.choice(results)
    url = video['link']
    
    return url

async def get_random_music():
    # List of music-related search terms to ensure music videos
    music_terms = [
        "music", "song", "official music video", "live performance", 
        "acoustic", "pop song", "rock music", "jazz", 
        "hip hop", "classical music", "electronic music"
    ]
    
    # Combine a random music term with a random string for variety
    query = f"{random.choice(music_terms)} {''.join(random.choice(string.ascii_letters) for _ in range(random.randint(3, 5)))}"
    
    # Search for music videos
    search = VideosSearch(query, limit=5)
    results = search.result()['result']
    
    if not results:
        get_random_music()  # Recurse, but be careful with stack
        return
    
    # Pick a random music video from the results
    video = random.choice(results)
    url = video['link']
    
    return url

async def get_random_quotes():
    try:
        quote = zenquotespy.random()
    except Exception:
        raise Exception

    return quote

async def get_random_roast():
    roasts = [
        "I'd agree with you but then we’d both be wrong.",
        "I’m not insulting you; I’m describing you.",
        "You bring everyone so much joy... when you leave.",
        "I thought of you today. It reminded me to take out the trash.",
        "You have something on your chin... no, the third one down.",
        "If I wanted to hear from an idiot, I’d just watch reality TV.",
        "You’re as useless as the 'ueue' in 'queue'.",
        "Somewhere out there is a tree tirelessly producing oxygen for you. You owe it an apology.",
        "You have the perfect face for radio.",
        "Your secrets are safe with me. I never even listen when you tell me them.",
        "You are proof that evolution can go in reverse.",
        "I'd explain it to you but I left my English-to-Dingbat dictionary at home.",
        "You bring everyone so much joy... when you leave.",
        "You're not stupid; you just have bad luck when it comes to thinking.",
        "If I had a face like yours, I’d sue my parents.",
        "You are the human version of a participation trophy.",
        "You have something on your chin... no, the third one down.",
        "Your gene pool could use a little chlorine.",
        "You are like a cloud. When you disappear, it’s a beautiful day."
    ]
    
    url = 'https://api.cookie-api.com/api/fun/roast'
    headers = {'Authorization': settings.COOKIE_API_SECRET}

    response = requests.get(url, headers=headers)
    if (response.status_code == 200):
        roast = response.json()['roast']
        return roast
    else:
        return random.choice(roasts)
    
async def get_magic_8_ball(question : str) -> dict:
    
    url = 'https://api.cookie-api.com/api/tools/magic-8-ball'
    params = {'question': question}
    headers = {'Authorization': settings.COOKIE_API_SECRET}
    
    try :
        response = requests.get(url, params=params, headers=headers)
    except Exception:
        raise Exception
    
    if (response.status_code == 200):
        return response.json()
    else:
        raise Exception
    
async def get_ai_chat(prompt : str):
    
    url = f'https://api.cookie-api.com/api/ai/message?prompt={prompt}'
    headers = {
        'Authorization': settings.COOKIE_API_SECRET
    }
    
    try :
        response = requests.get(url, headers=headers)
    except Exception:
        raise Exception
    
    if (response.status_code == 200):
        return response.json()
    else:
        raise Exception