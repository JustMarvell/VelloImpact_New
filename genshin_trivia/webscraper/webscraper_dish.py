from bs4 import BeautifulSoup

with open('genshin_trivia/htmls/special_dish_table.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

table_1 = soup.find('table').find('tbody')
dish_list = ''

for i in table_1.find_all('tr'):
    f = i.find('td').find('span', class_ = 'item-text').find('a', title=True)['title']
    if f is not None:
        n = f'"{f}", '
        dish_list += n
        
print(dish_list)
