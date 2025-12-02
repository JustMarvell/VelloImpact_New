import random
import string
from youtubesearchpython import VideosSearch

async def search_video():
    
    # Generate a random query: 4-6 random letters
    query_length = random.randint(4, 6)
    query = ''.join(random.choice(string.ascii_letters) for _ in range(query_length))
    
    # Search for videos
    search = VideosSearch(query, limit=2)  # Get 5 to pick random one
    results = search.result()['result']
    
    if not results:
        return "Failed : Failed To search video"
    
    # Pick a random one from the results
    video = random.choice(results)
    url = video['link']
    
    return url
