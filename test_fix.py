import requests
import json

BASE_URL = 'https://api.dictionaryapi.dev/api/v2/entries/en/'

word = input("INPUT WORD : ")

req = requests.get(f'{BASE_URL}{word}')

res_word = req.json()[0].get('word')
res_origin = req.json()[0].get('origin')
res_meanings = req.json()[0].get('meanings')
# res_phon = req.json()[0].get('phonetics')[0]['sourceUrl']
# res_phon_audio = req.json()[0].get('phonetics')[1]['sourceUrl']


# print(res_phon)
# print(res_phon_audio)
# print(res_word)
# print(res_origin)
# print(res_meanings)

# with open("test.json", "w", encoding="utf-8") as f:
#     json.dump(req.json(), f, indent=4, ensure_ascii=False)

de = ""
for i in res_meanings:
    print(i['partOfSpeech'])
    for x in i['definitions'][0:3]:
        de += x['definition']
    print(de)