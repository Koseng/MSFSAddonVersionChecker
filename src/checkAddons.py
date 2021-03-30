import os, sys, json, re
import encodings.idna # necessary for .exe
import webbrowser
import threading
import asyncio
import httpx
import dateutil.parser
import PySimpleGUI as sg
from PySimpleGUI.PySimpleGUI import theme_input_background_color
from xml.dom import minidom
from bs4 import BeautifulSoup

XML_FILE = "addons.xml"
NAME = "name"
COMMENT = "comment"
VERSION = "version"
KEY = "key"
URL = "url"
RESULT = "result"
UNAVAILABLE = "Unavailable"
RUN = "Run"
SAVE = "Save"
GO = "Go"
ERROR_COLOR = "lightsalmon"
INFO_COLOR = "lightyellow"
INPUT_COLOR = theme_input_background_color()
RESULT_COLOR = "lightgrey"
CONFIG_COLUMNS = [NAME, COMMENT, URL, VERSION, KEY]

# Create iterator for handling list in even sized chunks of size n
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def update_from_xml(doc, window):
    addons = doc.getElementsByTagName("addon")
    if doc.documentElement.hasAttribute("communityFolder"):  
        window["cf"].update(doc.documentElement.getAttribute("communityFolder") )
    for i in range(len(addons)):
        window[(i,NAME)].update(addons[i].getAttribute(NAME))
        window[(i,URL)].update(addons[i].getAttribute(URL)) 
        if addons[i].hasAttribute("installedVersion"):
            window[(i,VERSION)].update(addons[i].getAttribute("installedVersion"))
        if addons[i].hasAttribute("versionKey"):
            window[(i,KEY)].update(addons[i].getAttribute("versionKey"))
        if addons[i].hasAttribute("comment"):
            window[(i,COMMENT)].update(addons[i].getAttribute("comment"))


def write_to_xml(values, rows):
    doc = minidom.parseString("<configuration></configuration>")
    if values["cf"]:
        doc.documentElement.setAttribute("communityFolder", values["cf"])
    for j in range(rows):
        if values[(j, NAME)]:
            addon = doc.createElement("addon")
            addon.setAttribute(NAME, values[(j, NAME)])
            addon.setAttribute(URL, values[(j, URL)])
            if values[(j, VERSION)]:
                addon.setAttribute("installedVersion", values[(j, VERSION)])
            if values[(j, KEY)]:
                addon.setAttribute("versionKey", values[(j, KEY)])
            if values[(j, COMMENT)]:
                addon.setAttribute("comment", values[(j, COMMENT)])
            doc.documentElement.appendChild(addon)
    with open(XML_FILE, 'w') as writer:
        doc.writexml(writer, indent="\t", addindent="\t", newl="\n", encoding="utf-8")


def show_error(textElement, text):
    textElement.update(background_color=ERROR_COLOR)
    textElement.update(text)


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


def is_newer_version(installedVersion, onlineVersion):
    isNewer = False
    regex = r'(\d+\.\d+(\.\d+)*)'
    # check if version is newer. xx.yy[.zz][.vv]
    installedCode = re.search(regex, installedVersion)
    onlineCode = re.search(regex, onlineVersion)
    if installedCode and onlineCode: # found results for both
        installedNumbers = installedCode.group(1).split(".")
        onlineNumbers = onlineCode.group(1).split(".")
        positionCount = min(len(installedNumbers), len(onlineNumbers))
        for i in range(positionCount):
            if onlineNumbers[i] < installedNumbers[i]:
                break
            if onlineNumbers[i] > installedNumbers[i]:
                # online version is newer
                isNewer = True
                break
            # if equal check next position
    return isNewer


async def check_addon(window, values, k, communityFolder):
    try:
        errorText = None
        if values[(k,NAME)] and values[(k,URL)]:
            manifestPath = os.path.join(communityFolder, values[(k,NAME)], "manifest.json") 
            installedVersion = UNAVAILABLE
            onlineVersion = UNAVAILABLE
            onlineReleaseDate = UNAVAILABLE 
            # Installed addon
            if os.path.exists(manifestPath):
                with open(manifestPath) as f: 
                    manifestJson = json.load(f)
                installedVersion = manifestJson["package_version"]
            url = values[(k,URL)]
            # Flightsim.to
            if "flightsim.to" in url:
                errorText, onlineVersion, onlineReleaseDate = await check_flightsim(url, onlineVersion, onlineReleaseDate)
            # Github.com
            elif "github.com" in url:
                key = values[(k,KEY)]
                errorText, onlineVersion, onlineReleaseDate = await check_github(url, onlineVersion, onlineReleaseDate,key)
            # Overwrite installed version if set
            if values[(k,VERSION)]:
                installedVersion = values[(k,VERSION)]
            if is_newer_version(installedVersion, onlineVersion):
                window[(k,RESULT)].update(background_color=INFO_COLOR)
                window[(k,NAME)].update(background_color=INFO_COLOR)
            # Output
            if not errorText:
                window[(k,RESULT)].update("{:<16}{:<16}{:<25}".format(installedVersion, onlineVersion, onlineReleaseDate))
            else:
                show_error(window[(k,RESULT)], errorText)
            window.read(0) # refresh
    except Exception as ex:
        show_error(window[(k,RESULT)], repr(ex))


async def check_all_addons(window, values, communityFolder, rows):
    window[RUN].update(disabled=True)
    window[SAVE].update(disabled=True)
    for rowBatch in chunks(range(rows), 10): # batches of 10
        taskList = [asyncio.create_task(check_addon(window, values, k, communityFolder)) for k in rowBatch if values[(k,NAME)] and values[(k,URL)]]
        if taskList:
            await asyncio.gather(*taskList)
            await asyncio.sleep(1) # prevent flooding
    window[RUN].update(disabled=False)
    window[SAVE].update(disabled=False)


def addon_worker_thread(window, values, communityFolder, rows):
    asyncio.run(check_all_addons(window, values, communityFolder, rows))


def read_community_folder(window, values, communityFolder, rows):
    if communityFolder:
        list_subfolders = [f.name for f in os.scandir(communityFolder) if f.is_dir()]
        current_addons = {}
        last_addon_row = -1
        for i in range(rows):
            if values[(i, NAME)]:
                current_addons[values[(i, NAME)]] = values[(i, NAME)]
                last_addon_row = i
        for folder in list_subfolders:
            if folder not in current_addons and last_addon_row < (rows-1):
                last_addon_row = last_addon_row + 1
                window[(last_addon_row, NAME)].update(folder)
                window[(last_addon_row, URL)].update(background_color=ERROR_COLOR)


def collect_complete_entries(values, rows):
    entries=[{ col:values[(r,col)] for col in CONFIG_COLUMNS} for r in range(rows) if values[(r,NAME)] and values[(r,URL)]]
    return entries


def delete_all_entries(window, rows):
    [window[(r, col)].update("", background_color=INPUT_COLOR, disabled=False) for col in CONFIG_COLUMNS for r in range(rows)]
    [window[(r, RESULT)].update("") for r in range(rows)]
    

def delete_all_results(window, rows):
    [window[(r, RESULT)].update("", background_color=RESULT_COLOR) for r in range(rows)]


def write_collected_entries(window, entries):
    [window[(r, col)].update(entries[r][col]) for col in CONFIG_COLUMNS for r in range(len(entries))]


def update_row_state(window, values, row):
    doDisable = "flightsim.to" in values[(row, URL)]
    window[(row, KEY)].update(disabled=doDisable)
    color = INPUT_COLOR
    if values[(row, NAME)] and not values[(row, URL)]:
        color = ERROR_COLOR
    window[(row, URL)].update(background_color = color)
    color = INPUT_COLOR
    if not values[(row, NAME)] and values[(row, URL)]:
        color = ERROR_COLOR
    window[(row, NAME)].update(background_color = color)


def update_all_row_states(window, values, MAX_ROWS):
    for r in range(MAX_ROWS):
        update_row_state(window, values, r)


def main():
    # Set execution folder to folder of .py file
    os.chdir(sys.path[0]) 
    # MS Store
    communityFolder = os.path.join(os.getenv("LOCALAPPDATA"), "Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalCache/Packages/Community")
    if not os.path.exists(communityFolder):
        communityFolder = os.path.join(os.getenv("APPDATA"), "Microsoft Flight Simulator/Packages/Community") # Steam Version
    if not os.path.exists(communityFolder):
        communityFolder = os.path.join(os.getenv("LOCALAPPDATA"), "MSFSPackages/Community") # Box Version
    doc = minidom.parse(XML_FILE)
    if doc.documentElement.hasAttribute("communityFolder"):  
        communityFolder = doc.documentElement.getAttribute("communityFolder") 

    folders = 0
    if communityFolder:
        list_subfolders = [f.name for f in os.scandir(communityFolder) if f.is_dir()] 
        folders = len(list_subfolders) + 5

    doc = minidom.parse(XML_FILE)
    MAX_ROWS = max(len(doc.getElementsByTagName("addon")) + 10, 30, folders)

    # Generate UI
    column_layout= [[sg.Text(size=(50, 1), pad=(1,1), key=(i, RESULT), font=("Courier", 10), background_color=RESULT_COLOR, text_color="black"),
                    sg.Input(size=(28, 1), pad=(1,1), key=(i, NAME), border_width=0, enable_events=True),
                    sg.Input(size=(20, 1), pad=(1,1), key=(i, COMMENT), border_width=0, text_color="grey"),
                    sg.Input(size=(63, 1), pad=(1,1), key=(i, URL), border_width=0, enable_events=True),
                    sg.Button(size=(1, 1), pad=(1,1), key=(i, GO), border_width=1, font=("Arial", 7), button_color="lightgrey" ),
                    sg.Input(size=(10, 1), pad=(1,1), key=(i, VERSION), border_width=0, tooltip="Set fixed installed version"),
                    sg.Input(size=(9, 1), pad=(1,1), key=(i, KEY), disabled_readonly_background_color = "lightgrey", border_width=0, tooltip="Version filter key for github")] 
                    for i in range(MAX_ROWS)]
   
    layout = [[sg.Text("Optional path community folder: "), sg.I(size=(120, 1), pad=(1,15), key="cf")], 
            [sg.B(RUN, size=(10,1)), sg.Text(size=(36, 1)), sg.B(SAVE, size=(10,1)), sg.B("Read Community Folder", size=(25,1)), sg.B("Delete Incomplete Rows", size=(24,1))],
            [sg.HorizontalSeparator(RUN,pad=(1,10) )],
            [sg.Text(size=(50, 1), pad=(1,1), text="{:<16}{:<16}{:<25}".format("INSTALLED", "ONLINE", "RELEASE"), font=("Courier", 10)),
             sg.Text(size=(24, 1), pad=(1,1), text="NAME"),
             sg.Text(size=(17, 1), pad=(1,1), text="COMMENT"),
             sg.Text(size=(57, 1), pad=(1,1), text="URL"),
             sg.Text(size=(9, 1), pad=(1,1), text="FIX Version", tooltip="Set fixed installed version"),
             sg.Text(size=(8, 1), pad=(1,1), text="KEY",  tooltip="Version filter key for github")],
            [sg.Column(column_layout, size=(1355, 660), pad=(0,0), scrollable=True, vertical_scroll_only = True)]]

    window = sg.Window('MSFS Addon Version Checker 2.3.1', layout,  return_keyboard_events=False)
    window.finalize()
    update_from_xml(doc, window)
    event, values = window.read(0)
    update_all_row_states(window, values, MAX_ROWS)

    while True:  
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        elif type(event) is tuple and event[1] == URL:
            update_row_state(window, values, event[0])
        elif type(event) is tuple and event[1] == NAME:
            update_row_state(window, values, event[0])
        elif type(event) is tuple and event[1] == GO and values[event[0], URL]:
            webbrowser.open(values[event[0], URL])
        elif event == SAVE:
            write_to_xml(values, MAX_ROWS)
        elif event == "Read Community Folder":
            read_community_folder(window, values, communityFolder, MAX_ROWS)
        elif event == "Delete Incomplete Rows":
            entries = collect_complete_entries(values, MAX_ROWS)
            delete_all_entries(window, MAX_ROWS)
            delete_all_results(window, MAX_ROWS)
            write_collected_entries(window, entries)
            event, values = window.read(0) # refresh values
            update_all_row_states(window, values, MAX_ROWS)
        elif event == RUN:
            delete_all_results(window, MAX_ROWS)
            th = threading.Thread(target=addon_worker_thread, args=(window, values, communityFolder, MAX_ROWS))
            th.start()

if __name__ == "__main__":
    main()
