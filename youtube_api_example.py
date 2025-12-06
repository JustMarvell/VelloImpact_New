"""
Example: Using google-api-python-client to fetch related videos from YouTube.

This example demonstrates how to:
1. Set up the YouTube Data API client
2. Fetch related videos for a given video ID
3. Extract useful metadata (title, channel, duration, views)
4. Filter and process results
"""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
import settings

# ============================================================================
# SETUP
# ============================================================================
# 1. Install the library:
#    pip install google-api-python-client
#
# 2. Get your API key:
#    - Go to https://console.cloud.google.com/
#    - Create a project
#    - Enable "YouTube Data API v3"
#    - Create an API key (Credentials > API key)
#    - Copy the key and store it safely

YOUTUBE_API_KEY = settings.YOUTUBE_API_SECRET  # Replace with your actual key

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_youtube_client():
    """Initialize and return a YouTube API client."""
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{11})",
        r"([A-Za-z0-9_-]{11})$"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_video_details(youtube, video_id: str):
    """
    Fetch detailed metadata for a single video.
    Returns: dict with title, channel, duration, views, description
    """
    try:
        request = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=video_id
        )
        response = request.execute()
        
        if not response.get("items"):
            return None
        
        item = response["items"][0]
        snippet = item["snippet"]
        content_details = item["contentDetails"]
        statistics = item["statistics"]
        
        # Parse ISO 8601 duration to seconds
        duration_str = content_details.get("duration", "PT0S")
        duration_seconds = parse_duration(duration_str)
        
        return {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "channel_name": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "description": snippet.get("description", ""),
            "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            "duration_seconds": duration_seconds,
            "view_count": int(statistics.get("viewCount", 0)),
            "published_at": snippet.get("publishedAt", ""),
        }
    except HttpError as e:
        print(f"HTTP error fetching video details: {e}")
        return None


def parse_duration(duration_str: str) -> int:
    """
    Parse ISO 8601 duration (e.g., 'PT3M45S') to total seconds.
    """
    import re
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, duration_str)
    
    if not match:
        return 0
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    
    return hours * 3600 + minutes * 60 + seconds


def get_related_videos(youtube, video_id: str, max_results: int = 10) -> list:
    """
    Fetch related videos for a given video ID using YouTube's official recommendation algorithm.
    
    Args:
        youtube: YouTube API client
        video_id: The video ID to find related videos for
        max_results: Number of results to fetch (max 50)
    
    Returns:
        List of dicts with video info (video_id, title, channel, duration, etc.)
    """
    try:
        request = youtube.search().list(
            part="snippet",
            relatedToVideoId=video_id,
            type="video",
            maxResults=max_results,
            fields="items(id(videoId),snippet(title,channelTitle,channelId,description,thumbnails,publishedAt))"
        )
        response = request.execute()
        
        results = []
        for item in response.get("items", []):
            video_id_result = item["id"].get("videoId")
            snippet = item["snippet"]
            
            results.append({
                "video_id": video_id_result,
                "title": snippet.get("title", ""),
                "channel_name": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "description": snippet.get("description", ""),
                "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "published_at": snippet.get("publishedAt", ""),
                # Note: duration_seconds is NOT returned by search().list() for performance reasons
                # You'd need to call get_video_details() separately if you need it
            })
        
        return results
    except HttpError as e:
        print(f"HTTP error fetching related videos: {e}")
        return []


def filter_videos(videos: list, min_duration: int = 90, min_views: int = 1000) -> list:
    """
    Filter videos by criteria (duration, views, etc.).
    Note: duration_seconds may be 0 if not fetched; adjust as needed.
    """
    filtered = []
    for video in videos:
        duration = video.get("duration_seconds", 0)
        views = video.get("view_count", 0)
        
        # Skip videos that are too short (might be clips)
        if duration > 0 and duration < min_duration:
            continue
        
        # Skip videos with very few views (might be obscure)
        if views < min_views:
            continue
        
        filtered.append(video)
    
    return filtered


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_basic():
    """Basic example: get related videos for a song."""
    print("=" * 70)
    print("EXAMPLE 1: Get Related Videos (Basic)")
    print("=" * 70)
    
    youtube = get_youtube_client()
    
    # Example video ID (replace with an actual music video ID)
    video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    print(f"\nFetching related videos for video ID: {video_id}")
    related = get_related_videos(youtube, video_id, max_results=5)
    
    print(f"\nFound {len(related)} related videos:")
    for i, video in enumerate(related, 1):
        print(f"\n{i}. {video['title']}")
        print(f"   Channel: {video['channel_name']}")
        print(f"   Channel ID: {video['channel_id']}")
        print(f"   Video ID: {video['video_id']}")
        print(f"   Description: {video['description'][:100]}...")


def example_with_details():
    """Advanced example: get related videos with full metadata."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Get Related Videos With Full Metadata")
    print("=" * 70)
    
    youtube = get_youtube_client()
    
    video_id = "dQw4w9WgXcQ"
    
    print(f"\nFetching full details for video: {video_id}")
    video_details = get_video_details(youtube, video_id)
    
    if video_details:
        print(f"\nOriginal Video:")
        print(f"  Title: {video_details['title']}")
        print(f"  Channel: {video_details['channel_name']}")
        print(f"  Duration: {video_details['duration_seconds']}s")
        print(f"  Views: {video_details['view_count']:,}")
    
    print(f"\nFetching related videos...")
    related = get_related_videos(youtube, video_id, max_results=5)
    
    print(f"\nFetching full details for {len(related)} related videos...")
    for i, video in enumerate(related, 1):
        details = get_video_details(youtube, video['video_id'])
        if details:
            print(f"\n{i}. {details['title']}")
            print(f"   Channel: {details['channel_name']}")
            print(f"   Duration: {details['duration_seconds']}s ({details['duration_seconds'] // 60}:{details['duration_seconds'] % 60:02d})")
            print(f"   Views: {details['view_count']:,}")


def example_filtered():
    """Example: get related videos and apply filters."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Get Related Videos With Filtering")
    print("=" * 70)
    
    youtube = get_youtube_client()
    
    video_id = "dQw4w9WgXcQ"
    
    print(f"\nFetching related videos...")
    related = get_related_videos(youtube, video_id, max_results=20)
    
    print(f"Fetching full details for {len(related)} videos (to apply filters)...")
    related_with_details = []
    for video in related:
        details = get_video_details(youtube, video['video_id'])
        if details:
            related_with_details.append(details)
    
    print(f"\nApplying filters (min_duration=90s, min_views=10000)...")
    filtered = filter_videos(related_with_details, min_duration=90, min_views=10000)
    
    print(f"\nAfter filtering: {len(filtered)} videos remain")
    for i, video in enumerate(filtered[:5], 1):
        print(f"\n{i}. {video['title']}")
        print(f"   Channel: {video['channel_name']}")
        print(f"   Duration: {video['duration_seconds']}s")
        print(f"   Views: {video['view_count']:,}")


def example_url_to_related():
    """Example: extract video ID from URL and find related videos."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: URL to Related Videos")
    print("=" * 70)
    
    # Test various YouTube URL formats
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    ]
    
    for url in urls:
        vid_id = extract_video_id(url)
        print(f"\nURL: {url}")
        print(f"Extracted ID: {vid_id}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Check if API key is set
    if YOUTUBE_API_KEY == "YOUR_YOUTUBE_API_KEY_HERE":
        print("ERROR: Please set your YouTube API key in the script!")
        print("See the comments at the top for instructions.")
        exit(1)
    
    # Run examples (comment out as needed)
    try:
        example_url_to_related()
        example_basic()
        example_with_details()
        example_filtered()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure your API key is valid and you have YouTube Data API enabled.")
