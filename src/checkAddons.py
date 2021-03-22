import requests, os, sys, json, re
import dateutil.parser
from xml.dom import minidom
from bs4 import BeautifulSoup

# Set execution folder to folder of .py file
os.chdir(sys.path[0]) 
# MS Store
communityFolder = os.path.join(os.getenv("LOCALAPPDATA"), "Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalCache/Packages/Community")
if not os.path.exists(communityFolder):
    communityFolder = os.path.join(os.getenv("APPDATA"), "Microsoft Flight Simulator/Packages/Community") # Steam Version
if not os.path.exists(communityFolder):
    communityFolder = os.path.join(os.getenv("LOCALAPPDATA"), "MSFSPackages/Community") # Box Version
doc = minidom.parse("addons.xml")
addons = doc.getElementsByTagName("addon")
if doc.documentElement.hasAttribute("communityFolder"):  
    communityFolder = doc.documentElement.getAttribute("communityFolder")  
headers = {'user-agent': 'Mozilla/5.0'}

print("")
print("{:<35}{:<20}{:<20}{:<25}".format("Name", "Installed", "Online", "Release Date"))
print("================================================================================================")
for addon in addons:
    addonName = addon.getAttribute("name")
    manifestPath = os.path.join(communityFolder, addonName, "manifest.json") 
    manifestJso = "Unavailable"
    installedVersion = "Unavailable"
    onlineVersion = "Unavailable"
    onlineReleaseDate = "Unavailable" 
    # Installed addon
    if os.path.exists(manifestPath):
        with open(manifestPath) as f: 
            manifestJson = json.load(f)
        installedVersion = manifestJson["package_version"]
    url = addon.getAttribute("url")
    # Flightsim.to
    if "flightsim.to" in url:
        r = requests.get(url, headers=headers, allow_redirects=True)
        if(r.ok):
            soup = BeautifulSoup(r.content, 'html.parser') 
            headerDict = {}
            th = soup.find_all('th')
            for h in th:
                if h.next_sibling.next_sibling:
                    if h.text not in headerDict:
                        headerDict[h.text] = h.next_sibling.next_sibling.text
            if "Version" in headerDict:
                onlineVersion = headerDict["Version"]
            if "Last Updated" in headerDict:
                onlineReleaseDate = headerDict["Last Updated"]
    # Github.com
    if "github.com" in url:
        apiUrl = url.replace("https://github.com", "https://api.github.com/repos") + "?per_page=100"
        r = requests.get(apiUrl, headers=headers, allow_redirects=True)
        if(r.ok):
            releasesJson = r.json()
            versionJson = releasesJson[0]
            if addon.hasAttribute("versionKey"):
                versionKey = addon.getAttribute("versionKey")
                versionJson = next((x for x in releasesJson if versionKey in x["tag_name"]), None)
            if versionJson:
                onlineVersion = versionJson["tag_name"]
                dt = dateutil.parser.isoparse(versionJson["published_at"])
                onlineReleaseDate = dt.strftime("%B %d, %Y")
    if addon.hasAttribute("installedVersion"):
        installedVersion = addon.getAttribute("installedVersion")
    newer = ""
    # check if version is newer. xx.yy[.zz][.vv]
    installedCode = re.search(r'(\d+\.\d+(\.\d+)*)', installedVersion)
    onlineCode = re.search(r'(\d+\.\d+(\.\d+)*)', onlineVersion)
    if installedCode and onlineCode: # found results for both
        installedNumbers = installedCode.group(1).split(".")
        onlineNumbers = onlineCode.group(1).split(".")
        positions = min(len(installedNumbers), len(onlineNumbers))
        for i in range(positions):
            if onlineNumbers[i] < installedNumbers[i]:
                break
            if onlineNumbers[i] > installedNumbers[i]:
                newer = "<<<<<"
                break
            # if equal check next position
    # Output
    print("{:<35}{:<10}{:<10}{:<20}{:<25}".format(addonName, installedVersion, newer, onlineVersion, onlineReleaseDate))
    print("------------------------------------------------------------------------------------------------")
input("Press enter to exit.")

