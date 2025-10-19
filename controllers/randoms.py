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
        print("No videos found for this random query. Trying again...")
        await get_random_video()  # Recurse, but be careful with stack
        return
    
    # Pick a random one from the results
    video = random.choice(results)
    url = video['link']
    
    return url