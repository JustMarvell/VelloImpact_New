import random
import string
from youtubesearchpython import VideosSearch

def random_video():
    # Generate a random query: 4-6 random letters
    query_length = random.randint(4, 6)
    query = ''.join(random.choice(string.ascii_letters) for _ in range(query_length))
    
    # Search for videos
    search = VideosSearch(query, limit=2)  # Get 5 to pick random one
    results = search.result()['result']
    
    if not results:
        print("No videos found for this random query. Trying again...")
        random_video()  # Recurse, but be careful with stack
        return
    
    # Pick a random one from the results
    video = random.choice(results)
    url = video['link']
    
    print(f"Here's a random YouTube video: {url}")
    
async def random_video_async():
    # Generate a random query: 4-6 random letters
    query_length = random.randint(4, 6)
    query = ''.join(random.choice(string.ascii_letters) for _ in range(query_length))
    
    # Search for videos
    search = VideosSearch(query, limit=2)  # Get 5 to pick random one
    results = search.result()['result']
    
    if not results:
        print("No videos found for this random query. Trying again...")
        random_video()  # Recurse, but be careful with stack
        return
    
    # Pick a random one from the results
    video = random.choice(results)
    url = video['link']
    
    await print(f"Here's a random YouTube video: {url}")
    
def test():
    videosSearch = VideosSearch('NoCopyrightSounds', limit = 2)

    print(videosSearch.result())
    