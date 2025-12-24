import requests

BASE_URL = 'https://dog.ceo/api/breeds/image/random'

try:
    response = requests.get(f"{BASE_URL}")
    
    if response.status_code != 200:
        print(f"Something wrong when fetching the response! Return code : {response.status_code}")
    
    status = response.json().get('status')
    img = response.json().get('message')
    
    if status != 'success':
        print(f"Something wrong when fetching the response! Status : {status}")
    
except Exception as e:
    print(f"An error occured when getting response : {e}")