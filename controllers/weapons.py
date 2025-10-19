import firebase_admin, settings, glob, json, os, discord
from firebase_admin import credentials, db

cred = credentials.Certificate(f'{settings.BASE_DIR}/key.json')
weapon_list_dir = f'{settings.BASE_DIR}/json_data/weapon_list.json'

firebase_admin.initialize_app(cred, {
    'databaseURL' : f'{settings.FIREBASE_API_SECRET}'
})

onestarcolor = discord.Color.greyple()
twostarcolor = discord.Color.dark_green()
threestarcolor = discord.Color.og_blurple()
fourstarcolor = discord.Color.purple()
fivestarcolor = discord.Color.gold()

async def get_character_list():
    with open(weapon_list_dir, 'r') as f:
        data = json.load(f)
    return data

async def get_weapon_data(weapon_name):
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
            return 1
    except Exception as e:
        return 2