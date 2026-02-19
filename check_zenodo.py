import urllib.request
import re

url = "https://zenodo.org/record/259444"
try:
    with urllib.request.urlopen(url) as response:
        content = response.read().decode('utf-8')
        links = re.findall(r'href=[\'"]?([^\'" >]+)', content)
        for link in links:
            if "HASY" in link:
                print(link)
except Exception as e:
    print(e)
