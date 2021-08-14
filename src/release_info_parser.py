
import asyncio
import re
import httpx
from bs4 import BeautifulSoup
import dateutil.parser
from datetime import datetime

async def check_flightsim(url, onlineVersion, onlineReleaseDate):
    errorText = None
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers={'user-agent': 'Mozilla/5.0'}, allow_redirects=True, timeout=10)
        if(r.status_code == httpx.codes.OK):
            soup = BeautifulSoup(r.content, 'html.parser') 
            headerDict = {}
            th = soup.find_all('th')
            for h in th:
                if h.next_sibling.next_sibling:
                    # last entries on the page are the correct ones, overwriting is ok
                    headerDict[h.text] = h.next_sibling.next_sibling.text
            if "Version" in headerDict:
                onlineVersion = headerDict["Version"]
            if "Last Updated" in headerDict:
                releaseDateString = headerDict["Last Updated"]
                onlineReleaseDate = datetime.strptime(releaseDateString, "%B %d, %Y")
        else:
            errorText = f"Url: {r.status_code} {r.reason_phrase}"
    return errorText, onlineVersion, onlineReleaseDate


async def check_justflight(url, onlineVersion, onlineReleaseDate):
    errorText = None
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers={'user-agent': 'Mozilla/5.0'}, allow_redirects=True, timeout=10)
        if(r.status_code == httpx.codes.OK):
            soup = BeautifulSoup(r.content, 'html.parser') 
            metas = soup.find_all('meta')
            for m in metas:
                if "content" in m.attrs:
                    content = m["content"]
                    regex= r'.*(\d\d/\d\d/\d\d\d\d).*v(\d+\.\d+(\.\d+)*)' 
                    versionDate = re.search(regex, content)
                    if versionDate:
                        releaseDateString = versionDate.group(1)
                        onlineReleaseDate = datetime.strptime(releaseDateString, '%d/%m/%Y')
                        onlineVersion = versionDate.group(2)
        else:
            errorText = f"Url: {r.status_code} {r.reason_phrase}"
    return errorText, onlineVersion, onlineReleaseDate


async def check_github(url, onlineVersion, onlineReleaseDate, key):
    errorText = None
    if not url.endswith("/releases"):
        url =  url + "/releases"
    apiUrl = url.replace("https://github.com", "https://api.github.com/repos") + "?per_page=100"
    async with httpx.AsyncClient() as client:
        r = await client.get(apiUrl, headers={'user-agent': 'Mozilla/5.0'}, allow_redirects=True, timeout=10)
        if(r.status_code == httpx.codes.OK):
            releasesJson = r.json()
            versionJson = releasesJson[0]
            if key:
                versionKey = key
                versionJson = next((x for x in releasesJson if versionKey in x["tag_name"]), None)
            if versionJson:
                onlineVersion = versionJson["tag_name"]
                onlineReleaseDate = dateutil.parser.isoparse(versionJson["published_at"])
        else:
            errorText = f"Url: {r.status_code} {r.reason_phrase}"
    return errorText, onlineVersion, onlineReleaseDate