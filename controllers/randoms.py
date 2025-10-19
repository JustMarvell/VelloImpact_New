import random
import string
from youtubesearchpython import VideosSearch

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