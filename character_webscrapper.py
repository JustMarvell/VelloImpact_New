import requests
from bs4 import BeautifulSoup
import json
import os
import random
import settings
import test

def scrape_data(url : str):
    request = requests.get(url)
    soup = BeautifulSoup(request.content, 'html.parser')
    
    # DONE : Get character information board
    content_container = soup.find('div', id = 'content').find('div', id = 'mw-content-text').find('div', class_ = 'mw-parser-output')
    info_board = content_container.find('aside', class_ = 'portable-infobox pi-background pi-border-color pi-theme-char pi-layout-default')

    # DONE : Get character name
    def get_name():
        try:
            res = info_board.find('h2', attrs = {'data-source' : 'name'})
            if res != None:
                res = res.decode_contents(formatter = lambda x: x.replace(u'\xad', ''))
                return f'{res}'
        except Exception as e:
            return None
    name = get_name()
    
    # DONE : Get quality
    def get_quality():
        try: 
            res = info_board.find('td', attrs = {'data-source' : 'quality'})
            if res != None:
                res = res.find('img', alt = True)['alt']
                return f'{res[0]}'
            else:
                return None
        except exec as e:
            return None
    quality = get_quality()
    
    # DONE : Get weapon type
    def get_weapon_type():
        try:
            res = info_board.find('td', attrs = {'data-source' : 'weapon'})
            if res != None:
                res = res.find('a', title = True)['title']
            return f'{res}'
        except Exception as e:
            return None
    weapon_type = get_weapon_type()
    
    # DONE : Get element
    def get_element():
        try:
            res = info_board.find('td', attrs = {'data-source' : 'element'})
            if res != None:
                res = res.find('a', title = True)['title']
            return f'{res}'
        except Exception as e:
            return None
    element = get_element()
    
    # DONE : Get constelation
    def get_constellation():
        try:
            res = info_board.find('div', attrs = {'data-source' : 'constellation'})
            if res != None:
                res = res.find('div', class_ = 'pi-data-value pi-font').find('a', title = True)['title']
            return f'{res}'
        except Exception as e:
            return None
    constellation = get_constellation()
    
    # DONE : Get region
    def get_region():
        try:
            res = info_board.find('div', attrs = {'data-source' : 'region'})
            if res != None:
                res = res.find('div', class_ = 'pi-data-value pi-font').find('a', title = True)['title']
            return f'{res}'
        except Exception as e:
            return None
    region = get_region()
    
    # DONE : Get paragraph
    def get_paragraph():
        try:
            p_list = content_container.find_all('p', limit = 3)
            a = []
            for s in p_list:
                for i in s.find_all('b'):
                    i.unwrap()
                for i in s.find_all('span'):
                    i.unwrap()
                for i in s.find_all('a'):
                    i.unwrap()
                for i in s.find_all('i'):
                    i.unwrap()
                for i in s.find_all('u'):
                    i.unwrap()
                for i in s.find_all('aside'):
                    i.extract()
                for i in s.find_all('sup'):
                    i.extract()
                s = s.decode_contents()
                a.append(s)            
            r = ""
            a = a[1:]
            for i in a:
                r += i
            return r
        except Exception as e:
            return None
    description = get_paragraph()
    
    # DONE : Get character icon
    def get_icon():
        try:
            g_link = content_container.find('div', class_ = 'custom-tabs-default custom-tabs').find('a', title = f'{name}/Gallery', href = True)['href']
            g_request = requests.get(f'https://genshin-impact.fandom.com{g_link}')
            icon_soup = BeautifulSoup(g_request.content, 'html.parser')
            
            img_gallery0 = icon_soup.find('div', id = 'content').find('div', id = 'mw-content-text').find('div', class_ = 'mw-parser-output').find('div', id = 'gallery-0')
            img_url = img_gallery0.find('div', id = f'{name.replace(" ", "_")}_Icon-png').find('img', src = True)['src']
            
            img_url = img_url.replace('/scale-to-width-down/185', '')
                    
            return f'{img_url}'
        except Exception as e:
            return None
    icon = get_icon()
    
    # DONE : Set ID
    """
    format : 
        > 1 digit based on quality (4, 5, etc...)
        > 1 digit based on reqion :
            - None = 0
            - Mondstadt = 1
            - Liyue = 2
            - Inazuma = 3
            - Sumeru = 4
            - Fontaine = 5
            - Natlan = 6
            - Snezhnaya = 7
            - etc...
        > 1 digit based on weapon type : 
            - Sword = 1
            - Claymore = 2
            - Bow = 3
            - Catalyst = 4
            - Polearm = 5
        > 3 random digit from 100 - 999
        > 2 random digit from 10 - 99
        > 1 random digit from 0 - 9
        # 123444556
    """
    def set_id(quality : str, region : str, weapon_type : str):
        # python 3.8 did'nt have match(switch case) :(
        reg_id = "0"
        if region == "None":
            reg_id = "0"
        elif region == "Mondstadt":
            reg_id = "1"
        elif region == "Liyue":
            reg_id = "2"
        elif region == "Inazuma":
            reg_id = "3"
        elif region == "Sumeru":
            reg_id = "4"
        elif region == "Fontaine":
            reg_id = "5"
        elif region == "Natlan":
            reg_id = "6"
        elif region == "Snezhnaya":
            reg_id = "7"
        elif region == None:
            reg_id = "8"
        
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
        
        res = f'{quality}{reg_id}{wpn_id}{rand1}{rand2}{rand3}'
        return res
    id = set_id(quality, region, weapon_type)
    
    def add_to_json():
        
        data = {
            "id" : id,
            "name" : name,
            "description" : description,
            "constelation" : constellation,
            "element" : element,
            "quality" : quality,
            "weapon_type" : weapon_type,
            "icon" : icon
        }
        
        dir = settings.JSON_CHARACTER_DIR
        file_path = os.path.join(dir, f"{name}.json")

        os.makedirs(dir, exist_ok=True)

        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)

        print(f"JSON file has been created and saved to {file_path}")
    
    add_to_json()
    return name

def start_scrapping(lists : list):
    print(f'begin scrapping characters, Remaining : {len(lists)} of {len(lists)}')
    i = 1
    for link in lists:
        n = scrape_data(link)
        lists_count = len(lists)
        print(f'{n} Added to Database, Remaining : {lists_count - i} of {lists_count}')
        i += 1
    print("All Characters Has Been Added To Database")
    
link_list = []

def input_automatically(limit : int):
    link = input("Input link here > ")
    
    req = requests.get(link)
    sp = BeautifulSoup(req.content, 'html.parser')
    mwpu = sp.find('div', id = 'content').find('div', id = 'mw-content-text').find('div', class_ = 'mw-parser-output')
   
    table = mwpu.find_all('table').pop(1)
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
    test.upload_character_json_file()

input_automatically(0)