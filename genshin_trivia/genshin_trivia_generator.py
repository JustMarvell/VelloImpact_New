import requests
import json
import random
import time
from tqdm import tqdm  # Optional: for progress bar (pip install tqdm)
from data_pools import WEAPON_POOL, REGION_POOL, ELEMENT_POOL, TITLE_POOL, SPECIAL_DISH_POOL, CONSTELLATION_POOL, BIRTHDAY_POOL, RELEASED_VERSION_POOL, ENGLISH_VA_POOL, JAPANESE_VA_POOL

BASE_URL = "https://gsi.fly.dev/"
IMAGE_API_BASE = "https://genshin.jmp.blue"


# Question templates ordered by difficulty (easy → medium → hard)
QUESTION_TEMPLATES = [
    # Easy
    {"q": "What is the type of weapon that {name} wields?", "field": "weapon", "pool": WEAPON_POOL, "diff": "Easy"},
    {"q": "From which region does {name} come from?", "field": "region", "pool": REGION_POOL, "diff": "Easy"},
    {"q": "What element is {name}'s vision?", "field": "vision", "pool": ELEMENT_POOL, "diff": "Easy"},
    # Medium
    {"q": "What is the title that {name} has?", "field": "title", 'pool' : TITLE_POOL, "diff": "Medium"},
    {"q": "What is the name of {name}'s special dish?", "field": "special_dish", 'pool' : SPECIAL_DISH_POOL, "diff": "Medium"},
    {"q": "What is the name of {name}'s constellation?", "field": "constellation", 'pool' : CONSTELLATION_POOL, "diff": "Medium"},
    # Hard
    {"q": "When is {name}'s birthday?", "field": "birthday", 'pool' : BIRTHDAY_POOL, "diff": "Hard"},
    {"q": "In which version was {name} released?", "field": "release_version", 'pool' : RELEASED_VERSION_POOL, "diff": "Hard"},
    {"q": "Who is {name}'s English VA?", "field": ("voice_actors", "English"), 'pool' : ENGLISH_VA_POOL, "diff": "Hard"},
    {"q": "Who is {name}'s Japanese VA?", "field": ("voice_actors", "Japanese"), 'pool' : JAPANESE_VA_POOL, "diff": "Hard"},
]

def fetch_all_characters():
    characters = []
    page = 1
    while True:
        response = requests.get(f"{BASE_URL}/characters?page={page}&limit=50")
        if response.status_code != 200:
            break
        data = response.json()
        characters.extend(data.get("results", []))
        if page >= data.get("total_pages", 1):
            break
        page += 1
        time.sleep(1)
    return characters


def fetch_character_detail(char_id):
    response = requests.get(f"{BASE_URL}/characters/{char_id}")
    if response.status_code == 200:
        return response.json().get("result")
    return None


def get_field_value(detail, field):
    """Handle both simple fields and nested voice_actors"""
    if isinstance(field, tuple):
        parent, key = field
        return detail.get(parent, [{}])[0].get(key)
    return detail.get(field)

def get_character_image(char_id):
    """Fetch character icon/splash from genshin.jmp.blue"""
    image_url = f"{IMAGE_API_BASE}/characters/{char_id}/icon"
    
    # Quick existence check (optional but recommended)
    try:
        response = requests.head(image_url, timeout=3)
        if response.status_code == 200:
            return image_url
        else:
            print(f"Image not found for {char_id} using default image")
            return "https://static.wikia.nocookie.net/gensin-impact/images/c/cf/Icon_Archon_Quest.png/revision/latest?cb=20210615060053"
    except:
        print(f"Failed when getting image for {char_id} using default image")
        return "https://static.wikia.nocookie.net/gensin-impact/images/c/cf/Icon_Archon_Quest.png/revision/latest?cb=20210615060053"


def normalize_text(text):
    """Normalize text for comparison by trimming and standardizing case"""
    if not isinstance(text, str):
        return str(text)
    return text.strip()

def generate_options(correct, pool=None, count=3):
    """
    Generate multiple choice options ensuring no duplicates.
    
    Args:
        correct: The correct answer
        pool: List of possible distractors
        count: Number of distractor options needed
    
    Returns:
        List of shuffled options with correct answer included
    """
    # Normalize the correct answer for comparison
    correct_normalized = normalize_text(correct)
    
    if pool:
        # Filter out the correct answer with normalization
        distractors = []
        for option in pool:
            option_normalized = normalize_text(option)
            if option_normalized != correct_normalized:
                distractors.append(option)
        
        # Ensure we have enough distractors
        if len(distractors) < count:
            print(f"Warning: Only {len(distractors)} unique distractors available for '{correct}', "
                  f"need {count}. Generating fallback options.")
            # Add fallback options if pool is too small
            fallback_count = count - len(distractors)
            fallback_start = len(distractors) + 1
            fallback_options = [f"Option {fallback_start + i}" for i in range(fallback_count)]
            distractors.extend(fallback_options)
        
        # Select unique distractors
        selected_distractors = random.sample(distractors, min(count, len(distractors)))
    else:
        # Fallback generic distractors for fields without pool
        selected_distractors = [f"Unknown {i}" for i in range(1, count+1)]
    
    # Combine correct answer with distractors
    options = [correct] + selected_distractors
    
    # Final validation: ensure all options are unique
    unique_options = []
    seen = set()
    
    for option in options:
        option_normalized = normalize_text(option)
        if option_normalized not in seen:
            unique_options.append(option)
            seen.add(option_normalized)
        else:
            # If we encounter a duplicate, try to find a replacement
            if pool:
                # Try to find another unique option from the pool
                for replacement in pool:
                    replacement_normalized = normalize_text(replacement)
                    if (replacement_normalized != option_normalized and 
                        replacement_normalized not in seen):
                        unique_options.append(replacement)
                        seen.add(replacement_normalized)
                        break
    
    # Shuffle the final options
    random.shuffle(unique_options)
    return unique_options


def test_option_generation():
    """Test function to verify duplicate answer prevention works"""
    print("Testing option generation...")
    
    # Test case 1: Normal case
    correct = "Pyro"
    pool = ["Pyro", "Hydro", "Electro", "Anemo", "Geo"]
    options = generate_options(correct, pool, 3)
    print(f"Test 1 - Correct: {correct}")
    print(f"Options: {options}")
    print(f"All unique: {len(options) == len(set(options))}")
    print(f"Contains correct: {correct in options}")
    print()
    
    # Test case 2: Case sensitivity issue
    correct = "pyro"  # lowercase
    pool = ["Pyro", "Hydro", "Electro"]  # different case
    options = generate_options(correct, pool, 2)
    print(f"Test 2 - Correct: {correct}")
    print(f"Options: {options}")
    print(f"All unique: {len(options) == len(set(options))}")
    print(f"Contains correct: {correct in options}")
    print()
    
    # Test case 3: Small pool
    correct = "Sword"
    pool = ["Sword", "Claymore"]  # Only 1 distractor available
    options = generate_options(correct, pool, 3)  # Need 3 distractors
    print(f"Test 3 - Correct: {correct}")
    print(f"Options: {options}")
    print(f"All unique: {len(options) == len(set(options))}")
    print(f"Contains correct: {correct in options}")
    print()


def create_questions_for_character(character, max_per_char=4):
    name = character["name"]
    detail = fetch_character_detail(character["id"])
    if not detail:
        return []

    questions = []
    used_templates = []
    
    char_id = detail["name"].lower().replace(" ", "-")  # normalize if needed
    image_url = get_character_image(char_id)

    # Shuffle templates to get variety, but respect difficulty order
    template_indices = list(range(len(QUESTION_TEMPLATES)))
    random.shuffle(template_indices)

    for idx in template_indices:
        if len(questions) >= max_per_char:
            break

        template = QUESTION_TEMPLATES[idx]
        field = template["field"]

        value = get_field_value(detail, field)
        # Special handling for region/title which might be lists
        if isinstance(value, list):
            value = value[0] if value else None

        if not value or value == "Unknown":
            continue

        # Generate question
        question_text = template["q"].format(name=name)

        if "pool" in template:
            options = generate_options(value, template["pool"])
        else:
            options = generate_options(value)

        q = {
            "question": question_text,
            "options": options,
            "correct": value,
            "difficulty": template["diff"],
            'image' : image_url
        }
        questions.append(q)
        used_templates.append(idx)

    return questions


def main():
    print("Genshin Impact Trivia Generator (Customizable)")
    print("-" * 50)

    # User configuration
    MAX_PER_CHARACTER = int(input("How many questions per character? (recommended 3-6): ") or 4)
    MAX_TOTAL = int(input("Maximum total number of questions? (e.g. 150, 200): ") or 200)

    print(f"\nGenerating up to {MAX_TOTAL} questions ({MAX_PER_CHARACTER} max per character)...")
    print("Fetching character list...")

    all_chars = fetch_all_characters()
    print(f"Found {len(all_chars)} characters")

    trivia_list = []
    char_count = 0

    # Progress bar (optional)
    with tqdm(total=len(all_chars), desc="Processing characters") as pbar:
        random.shuffle(all_chars)  # Randomize character order

        for char in all_chars:
            if len(trivia_list) >= MAX_TOTAL:
                break

            qs = create_questions_for_character(char, MAX_PER_CHARACTER)
            trivia_list.extend(qs)
            char_count += 1
            pbar.update(1)
            time.sleep(0.6)  # Rate limit safety

    # Save result
    with open("genshin_trivia/jsons/genshin_trivia.json", "w", encoding="utf-8") as f:
        json.dump(trivia_list, f, indent=2, ensure_ascii=False)

    print("\n" + "="*50)
    print(f"Generation complete!")
    print(f"Characters processed: {char_count}")
    print(f"Total questions generated: {len(trivia_list)}")
    print(f"Saved to: genshin_trivia.json")
    print("="*50)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")