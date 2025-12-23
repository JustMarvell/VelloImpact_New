from bs4 import BeautifulSoup

with open('genshin_trivia/htmls/title_table.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

table_1 = soup.find('td', class_ = 'block-holder').find('tbody')
char_1_list = ''

for i in table_1.find_all('tr'):
    f = i.find('td', class_ = 'force-light-mode-text')
    if f is not None:
        f = f.find('div').decode_contents()
        n = f'"{f}", '
        char_1_list += n
        
print(char_1_list)

print("============================================")

table_2 = soup.find_all('td', class_ = 'block-holder')[1].find('tbody')
char_2_list = ''

for i in table_2.find_all('tr'):
    f = i.find('td', class_ = 'force-light-mode-text')
    if f is not None:
        f = f.find('div').decode_contents()
        n = f'"{f}", '
        char_2_list += n
        
print(char_2_list)
