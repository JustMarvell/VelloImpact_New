from bs4 import BeautifulSoup

with open('genshin_trivia/htmls/release_version_table.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

table_1 = soup.find('table').find('tbody')
version_list = ''

for i in table_1.find_all('tr'):
    f = i.find_all('td')[-1].get('data-version')
    if f is not None:
        n = f'"v{f}", '
        version_list += n
        
print(version_list)
