import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import settings
import glob
import json
import os

cred = credentials.Certificate(f'{settings.BASE_DIR}/key.json')

firebase_admin.initialize_app(cred, {
    'databaseURL': f'{settings.FIREBASE_API_SECRET}'
})

# json_dir = f'{settings.BASE_DIR}/json_data/'

def upload_character_json_file():
    for json_file in glob.glob(os.path.join(settings.JSON_CHARACTER_DIR, '*.json')):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            char_name = data.get('name')
            if not char_name:
                print("name not found, skipping")
                continue
            
            ref = db.reference(f'Char_{char_name}')

            ref.set(data)
            
            print(f"Successfully uploaded data for {char_name} from {json_file}")
        
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            
def read_char_data(char_name):
    try:
        # Sanitize character name for Firebase key
        invalid_chars = ['.', '#', '$', '/', '[', ']']
        for char in invalid_chars:
            char_name = char_name.replace(char, '_')
        
        # Create a reference to the node "Char_[character-name]"
        ref = db.reference(f"Char_{char_name}")
        
        # Get the data
        data = ref.get()
        
        if data:
            return data
        else:
            print(f"No data found for {char_name}")
            return None
    
    except Exception as e:
        print(f"Error reading data for {char_name}: {e}")
        return None
    
def create_char_name_list(output_file):
    """
    Retrieves all character names from Firebase nodes starting with 'Char_' and saves them to a JSON file.
    
    Args:
        output_file (str): Path to the output JSON file where the list of names will be saved.
    
    Returns:
        bool: True if the file was created successfully, False otherwise.
    """
    try:
        # Get a reference to the root of the database
        ref = db.reference('/')
        
        # Fetch all data at the root
        all_data = ref.get()
        
        if not all_data:
            print("No data found in the database.")
            return False
        
        # List to store character names
        char_names = []
        
        # Iterate through all top-level nodes
        for key, value in all_data.items():
            if key.startswith('Char_') and isinstance(value, dict):
                # Extract the name field from the node
                name = value.get('name')
                if name:
                    char_names.append(name)
        
        if not char_names:
            print("No character names found in nodes starting with 'Char_'.")
            return False
        
        # Save the list of names to a JSON file
        with open(output_file, 'w') as f:
            json.dump(char_names, f, indent=4)
        
        print(f"Character name list saved to {output_file}: {char_names}")
        return True
    
    except Exception as e:
        print(f"Error creating character name list: {e}")
        return False
    
def get_character_list():
    with open(settings.JSON_CHARACTER_DIR, 'r') as f:
        data = json.load(f)
    return data


# upload_json_file()
# data = read_char_data("Citlali")
create_char_name_list(f'{settings.BASE_DIR}/json_data/list.json')
# print(get_character_list())



