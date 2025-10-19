import requests
from bs4 import BeautifulSoup
import json, os, random, settings, test

# Making a GET request
#link = 'https://genshin-impact.fandom.com/wiki/Talking_Stick'


def scrape_weapon(url: str):
    link = url
    
    r = requests.get(link)

    # Parsing the HTML
    soup = BeautifulSoup(r.content, 'html.parser')

    weapon_name = soup.find('h2', class_ = 'pi-item pi-item-spacing pi-title pi-secondary-background').decode_contents(formatter = lambda x: x.replace(u'\xad', ''))
    weapon_description = soup.find('div', class_ = 'description-content')
    
    for i in weapon_description.find_all('span'):
        i.unwrap()
    for i in weapon_description.find_all('a'):
        i.unwrap()
    for i in weapon_description.find_all('b'):
        i.unwrap()
    
    weapon_passive_name = soup.find('th', class_ = 'pi-horizontal-group-item pi-data-label pi-secondary-font pi-border-color pi-item-spacing').decode_contents()
        
    url = []
    for a in soup.find('div', class_ = 'pi-image-collection wds-tabber').find_all('a', href = True):
        url.append(a['href'])

    icon_url = url[1]

    weapon_base_atk = soup.find('div', class_ = 'pi-smart-data-value pi-data-value pi-font pi-item-spacing pi-border-color').decode_contents().strip()[5:]
    weapon_type = soup.find_all('section', class_ = 'pi-item pi-panel pi-border-color wds-tabber')[0].find('a', title = True)['title']
    weapon_quality = soup.find_all('section', class_ = 'pi-item pi-panel pi-border-color wds-tabber')[0].find_all('div', class_ = 'pi-item pi-data pi-item-spacing pi-border-color')[1].find('img', alt = True)['alt'][0]
    weapon_sct = soup.find_all('div', class_ = 'pi-smart-data-value pi-data-value pi-font pi-item-spacing pi-border-color')[1].find('a', title = True)['title']
    weapon_sct_atr = soup.find_all('div', class_ = 'pi-smart-data-value pi-data-value pi-font pi-item-spacing pi-border-color')[2].decode_contents().strip()[5:]
    weapon_atr_dec = soup.find_all('td', class_ = 'pi-horizontal-group-item pi-data-value pi-font pi-border-color pi-item-spacing')

    for i in weapon_atr_dec[4].find_all('span'):
        i.unwrap()
    for i in weapon_atr_dec[4].find_all('a'):
        i.unwrap()
    for i in weapon_atr_dec[4].find_all('b'):
        i.unwrap()
        
    weapon_release_date_ = soup.find_all('section', class_ = 'pi-item pi-panel pi-border-color wds-tabber')[0].find('div', attrs = {'data-source' : 'releaseDate'}).find('div', class_ = 'pi-data-value pi-font')

    weapon_release_date = weapon_release_date_.decode_contents().replace('<br/>', ' | ')


    # print(f'Weapon Name : {weapon_name}')
    # print(f'Weapon Type : {weapon_type}')
    # print(f'Weapon Quality : {weapon_quality}')
    # print(f'Release Date : {s}')
    # print("---------------------------")
    # print(f'Weapon Description : {weapon_description.decode_contents()}')
    # print("---------------------------")
    # print(f'Passive Name : {weapon_passive_name}')
    # print("---------------------------")
    # print(f'Attribute Description : {weapon_atr_dec[4].decode_contents()}')
    # print("---------------------------")
    # print(f'Icon URL : {icon_url}')
    # print(f'Base ATK : {weapon_base_atk}')
    # print(f'Secondary Attribute : {weapon_sct_atr} {weapon_sct}')

        
    weapon_icon = soup.find('div', class_ = 'pi-image-collection wds-tabber').findAll('div', class_ = 'wds-tab__content')[1].find('a', href = True)['href']

    def set_id(quality: str, weapon_type: str):
        if weapon_type == "Sword":
            wpn_id = "1"
        elif weapon_type == "Claymore":
            wpn_id = "2"
        elif weapon_type == "Bow":
            wpn_id = "3"
        elif weapon_type == "Catalyst":
            wpn_id = "4"
        elif weapon_type == "Polearm":
            wpn_id = "5"
            
        rand1 = random.randint(100, 999)
        rand2 = random.randint(10, 99)
        rand3 = random.randint(0, 9)
        
        res = f'{quality}{wpn_id}{rand1}{rand2}{rand3}'
        return res
    id = set_id(weapon_quality, weapon_type)
    
    def add_to_json():
        data = {
            "id" : id,
            "weapon_name" : weapon_name,
            "weapon_type" : weapon_type,
            "weapon_quality" : weapon_quality,
            "base_attack" : weapon_base_atk,
            "secondary_attribute_type" : weapon_sct,
            "secondary_attribute" : f'{weapon_sct} {weapon_sct_atr}',
            "weapon_description" : weapon_description.decode_contents(),
            "weapon_skill_name" : weapon_passive_name,
            "weapon_skill_description" : weapon_atr_dec[4].decode_contents(),
            "weapon_icon" : weapon_icon
        }
        
        dir = settings.JSON_WEAPON_DIR
        file_path = os.path.join(dir, f'{weapon_name}.json')
        
        os.makedirs(dir, exist_ok=True)

        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)

        print(f"JSON file has been created and saved to {file_path}")

    add_to_json()
    return weapon_name

def start_scrapping(lists : list):
    print(f'begin scrapping weapons, Remaining : {len(lists)} of {len(lists)}')
    i = 1
    for link in lists:
        n = scrape_weapon(link)
        lists_count = len(lists)
        print(f'{n} Added to Database, Remaining : {lists_count - i} of {lists_count}')
        i += 1
    print("All Weapons Has Been Added To Database")
    
link_list = []

def input_automatically(limit : int):
    link = input("Input link here > ")
    
    req = requests.get(link)
    sp = BeautifulSoup(req.content, 'html.parser')
    mwpu = sp.find('div', id = 'content').find('div', id = 'mw-content-text').find('div', class_ = 'mw-parser-output')
    
    table = mwpu.find_all('table').pop(0)
    tbody = table.find('tbody')
    
    if limit == 0:
        tr = tbody.find_all('tr')[1:]
    else:
        tr = tbody.find_all('tr', limit = limit+1)[1:]  
        
    for tds in tr:
        td = tds.find('td')
        
        href = td.find('a', href = True)['href']
        url = f'https://genshin-impact.fandom.com{href}'
        link_list.append(url)
        
    start_scrapping(link_list)
    test.upload_weapon_json_file()

input_automatically(2)