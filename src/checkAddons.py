import os, sys, json, re
import encodings.idna # necessary for .exe
import asyncio
import httpx
import dateutil.parser
import PySimpleGUI as sg
from xml.dom import minidom
from bs4 import BeautifulSoup

_xmlFile = "addons.xml"

def update_from_xml(doc, window):
    addons = doc.getElementsByTagName("addon")
    if doc.documentElement.hasAttribute("communityFolder"):  
        window["cf"].update(doc.documentElement.getAttribute("communityFolder") )
    for i in range(len(addons)):
        window[(i,"name")].update(addons[i].getAttribute("name"))
        window[(i,"url")].update(addons[i].getAttribute("url")) 
        if addons[i].hasAttribute("installedVersion"):
            window[(i,"version")].update(addons[i].getAttribute("installedVersion"))
        if addons[i].hasAttribute("versionKey"):
            window[(i,"key")].update(addons[i].getAttribute("versionKey"))

def write_to_xml(values, rows):
    doc = minidom.parseString("<configuration></configuration>")
    if values["cf"]:
        doc.documentElement.setAttribute("communityFolder", values["cf"])
    for j in range(rows):
        if values[(j, "name")]:
            addon = doc.createElement("addon")
            addon.setAttribute("name", values[(j, "name")])
            addon.setAttribute("url", values[(j, "url")])
            if values[(j, "version")]:
                addon.setAttribute("installedVersion", values[(j, "version")])
            if values[(j, "key")]:
                addon.setAttribute("versionKey", values[(j, "key")])
            doc.documentElement.appendChild(addon)
    with open(_xmlFile, 'w') as writer:
        doc.writexml(writer, indent="\t", addindent="\t", newl="\n", encoding="utf-8")

def show_error(textElement, text):
    textElement.update(background_color='lightsalmon')
    textElement.update(text)


def disable_input_fields(window, values, rows):
    for j in range(rows):
        if values:
            doDisable = "flightsim.to" in values[(j,"url")]
            window[(j,"key")].update(disabled=doDisable)


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
                    if h.text not in headerDict:
                        headerDict[h.text] = h.next_sibling.next_sibling.text
            if "Version" in headerDict:
                onlineVersion = headerDict["Version"]
            if "Last Updated" in headerDict:
                onlineReleaseDate = headerDict["Last Updated"]
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
                dt = dateutil.parser.isoparse(versionJson["published_at"])
                onlineReleaseDate = dt.strftime("%B %d, %Y")
        else:
            errorText = f"Url: {r.status_code} {r.reason_phrase}"
    return errorText, onlineVersion, onlineReleaseDate


async def check_addon(window, values, k, communityFolder):
    try:
        errorText = None
        if values[(k,"name")] and values[(k,"url")]:
            manifestPath = os.path.join(communityFolder, values[(k,"name")], "manifest.json") 
            installedVersion = "Unavailable"
            onlineVersion = "Unavailable"
            onlineReleaseDate = "Unavailable" 
            # Installed addon
            if os.path.exists(manifestPath):
                with open(manifestPath) as f: 
                    manifestJson = json.load(f)
                installedVersion = manifestJson["package_version"]
            url = values[(k,"url")]
            # Flightsim.to
            if "flightsim.to" in url:
                errorText, onlineVersion, onlineReleaseDate = await check_flightsim(url, onlineVersion, onlineReleaseDate)
            # Github.com
            if "github.com" in url:
                key = values[(k,"key")]
                errorText, onlineVersion, onlineReleaseDate = await check_github(url, onlineVersion, onlineReleaseDate,key)
            # Overwrite installed version if set
            if values[(k,"version")]:
                installedVersion = values[(k,"version")]
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
                        # online version is newer, set color
                        window[(k,"result")].update(background_color='lightyellow')
                        window[(k,"name")].update(background_color='lightyellow')
                        break
                    # if equal check next position
            # Output
            if not errorText:
                window[(k,"result")].update("{:<16}{:<16}{:<25}".format(installedVersion, onlineVersion, onlineReleaseDate))
            else:
                show_error(window[(k,"result")], errorText)
            window.read(0) # refresh
    except Exception as ex:
        show_error(window[(k,"result")], str(ex))

        
async def main():
    # Set execution folder to folder of .py file
    os.chdir(sys.path[0]) 
    # MS Store
    communityFolder = os.path.join(os.getenv("LOCALAPPDATA"), "Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalCache/Packages/Community")
    if not os.path.exists(communityFolder):
        communityFolder = os.path.join(os.getenv("APPDATA"), "Microsoft Flight Simulator/Packages/Community") # Steam Version
    if not os.path.exists(communityFolder):
        communityFolder = os.path.join(os.getenv("LOCALAPPDATA"), "MSFSPackages/Community") # Box Version
    doc = minidom.parse(_xmlFile)
    if doc.documentElement.hasAttribute("communityFolder"):  
        communityFolder = doc.documentElement.getAttribute("communityFolder")  

    doc = minidom.parse(_xmlFile)
    MAX_ROWS = max(len(doc.getElementsByTagName("addon")) + 10, 30)

    column_layout= [[ sg.Text(size=(52, 1), pad=(1,1), key=(i, "result"), font=("Courier", 10), background_color="lightgrey", text_color="black"),
                    sg.Input(size=(30, 1), pad=(1,1), key=(i, "name"), border_width=0),
                    sg.Input(size=(70, 1), pad=(1,1), key=(i, "url"), border_width=0),
                    sg.Input(size=(10, 1), pad=(1,1), key=(i, "version"), border_width=0, tooltip="Set fixed installed version"),
                    sg.Input(size=(10, 1), pad=(1,1), key=(i, "key"), disabled_readonly_background_color = "lightgrey", border_width=0, tooltip="Version filter key for github")] 
                    for i in range(MAX_ROWS)]

    layout = [[sg.B("Run", size=(10,1)), sg.B("Save", size=(10,1)), sg.Text("Optional path community folder: "), sg.I(size=(110, 1), pad=(1,15), key="cf") ], 
            [sg.HorizontalSeparator("Run",pad=(1,10) )],
            [sg.Text(size=(52, 1), pad=(1,1), text="{:<16}{:<16}{:<25}".format("INSTALLED", "ONLINE", "RELEASE"), font=("Courier", 10)),
            sg.Text(size=(26, 1), pad=(1,1), text="NAME"),
            sg.Text(size=(61, 1), pad=(1,1), text="URL"),
            sg.Text(size=(9, 1), pad=(1,1), text="FIX Version", tooltip="Set fixed installed version"),
            sg.Text(size=(9, 1), pad=(1,1), text="KEY",  tooltip="Version filter key for github")],
            [sg.Column(column_layout, size=(1300, 700), pad=(0,0), scrollable=True, vertical_scroll_only = True)]]

    window = sg.Window('MSFS Addon Version Checker 2.0', layout,  return_keyboard_events=True)
    window.finalize()
    update_from_xml(doc, window)
    event, values = window.read(0)
    disable_input_fields(window, values, MAX_ROWS)

    while True:  
        event, values = window.read()
        disable_input_fields(window, values, MAX_ROWS)
        # --- Process buttons --- #
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        elif event == "Save":
            write_to_xml(values, MAX_ROWS)
        elif event == "Run":
            window["Run"].update(disabled=True)
            window["Save"].update(disabled=True)
            # run the whole thing
            taskList = []
            for k in range(MAX_ROWS):
                taskList.append(asyncio.create_task(check_addon(window, values, k, communityFolder)))
            await asyncio.gather(*taskList)
            window["Run"].update(disabled=False)
            window["Save"].update(disabled=False)

if __name__ == "__main__":
    asyncio.run(main())

