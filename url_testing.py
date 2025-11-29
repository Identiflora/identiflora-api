from urllib.parse import urljoin
import os

HOST = "localhost"
PORT = 8000

url = urljoin(f'http://{HOST}:{PORT}', '/plant-images')
url = urljoin(url, '/API_test_img.png')

# print(url)

def build_base_url(host: str, port: int, path: str):
    path = path.lstrip('/')
    host_port = f'{host}:{port}'
    return os.path.join('http://', host_port, path)

print(build_base_url(HOST, PORT, '/plant-images'))