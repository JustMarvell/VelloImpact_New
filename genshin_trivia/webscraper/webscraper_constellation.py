from bs4 import BeautifulSoup

with open('genshin_trivia/htmls/constellation_table.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

table_1 = soup.find('table').find('tbody')
const_list = ''

for i in table_1.find_all('tr'):
    f = i.find_all('td')[1].find('a', title = True)['title']
    if f is not None:
        n = f'"{f}", '
        const_list += n
        
print(const_list)
