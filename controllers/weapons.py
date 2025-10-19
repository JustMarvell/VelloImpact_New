import firebase_admin, settings, glob, json, os, discord
from firebase_admin import credentials, db

weapon_list_dir = f'{settings.BASE_DIR}/json_data/weapon_list.json'


onestarcolor = discord.Color.greyple()
twostarcolor = discord.Color.dark_green()
threestarcolor = discord.Color.og_blurple()
fourstarcolor = discord.Color.purple()
fivestarcolor = discord.Color.gold()

async def get_weapon_list():
    with open(weapon_list_dir, 'r') as f:
        data = json.load(f)
    return data

async def get_weapon_data(weapon_name: str):
    try:
        # Sanitize character name for Firebase key
        invalid_chars = ['.', '#', '$', '/', '[', ']']
        for char in invalid_chars:
            weapon_name = weapon_name.replace(char, '_')
            
        # Create a reference to the node "Char_[character-name]"
        ref = db.reference(f"Weapon_{weapon_name}")
        
        data = ref.get()

        if data:
            return data
        else:
            print(f"No data found for {weapon_name}")
            return 1
    except Exception as e:
        print(f"Error reading data for {weapon_name}: {e}")
        return 2
    
async def convert_quality_to_star(quality: int):
    star = "⭐"
    result = ""
    
    for i in range(int(quality)):
        result += star
    
    return result

async def get_color_based_on_quality(quality: int):
    
    quality = int(quality)
    
    if quality == 1:
        return onestarcolor
    elif quality == 2:
        return twostarcolor
    elif quality == 3:
        return threestarcolor
    elif quality == 4:
        return fourstarcolor
    elif quality == 5:
        return fivestarcolor