from bs4 import BeautifulSoup

with open('genshin_trivia/htmls/voice_actors_table.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

table_1 = soup.find('table').find('tbody')
english_va_list = ''

for i in table_1.find_all('tr'):
    f = i.find_all('td')[1].find('a').decode_contents(formatter = lambda x: x.replace(u'\n', ''))
    if f is not None:
        n = f'"{f.strip('\n')}", '
        english_va_list += n
        
print(english_va_list)

print('========================================================================================')

japanese_va_list = ''

for i in table_1.find_all('tr'):
    f = i.find_all('td')[3].find('a')
    if f is not None:        
        n = f'"{f.get_text()}", '
        japanese_va_list += n

print(japanese_va_list)