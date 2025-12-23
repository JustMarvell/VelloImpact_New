from bs4 import BeautifulSoup

with open('genshin_trivia/htmls/birthday_table.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

table_1 = soup.find('table').find('tbody')
birth_list = ''

for i in table_1.find_all('tr'):
    f = i.find_all('td')[2].decode_contents()
    if f is not None:
        n = f'"{f}", '
        birth_list += n
        
print(birth_list)
