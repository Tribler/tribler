import requests
import time
import treq

VERSION_CHECK_URL = 'https://api.github.com/repos/tribler/tribler/releases/latest'


response = requests.get(VERSION_CHECK_URL)
print response

def on_response(resp):
    print resp

treq.get(VERSION_CHECK_URL).addCallback(on_response)


time.sleep(5)