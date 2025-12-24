import requests
from PIL import Image

BASE_URL = 'https://api.qrserver.com/v1/create-qr-code/'

data = "ExampleData"

size = 200

qr = requests.get(f"{BASE_URL}?data={data}&size={size}x{size}")

print(qr.content)