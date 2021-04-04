import os, sys, json, re
import encodings.idna # necessary for .exe
import webbrowser
import threading
import asyncio
import PySimpleGUI as sg
from release_info_parser import *
from configuration_persistance import *
from PySimpleGUI.PySimpleGUI import theme_input_background_color

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
CONFIG_COLUMNS = [NAME, COMMENT, URL, VERSION, KEY]
ERROR_COLOR = "lightsalmon"
INFO_COLOR = "lightyellow"
INPUT_COLOR = theme_input_background_color()
RESULT_COLOR = "lightgrey"


def show_error(textElement, text):
    print(text)
    textElement.update(background_color=ERROR_COLOR)
    textElement.update(text)


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
            if "flightsim.to" in url:
                errorText, onlineVersion, onlineReleaseDate = await check_flightsim(url, onlineVersion, onlineReleaseDate)
            elif "github.com" in url:
                key = values[(k,KEY)]
                errorText, onlineVersion, onlineReleaseDate = await check_github(url, onlineVersion, onlineReleaseDate,key)
            elif "justflight.com" in url:
                errorText, onlineVersion, onlineReleaseDate = await check_justflight(url, onlineVersion, onlineReleaseDate)
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


# Create iterator for handling list in even sized chunks of size n
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


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
    if os.path.exists(communityFolder):
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


def read_complete_table_entries(values, rows):
    entries=[{ col:values[(r,col)] for col in CONFIG_COLUMNS} for r in range(rows) if values[(r,NAME)] and values[(r,URL)]]
    return entries


def read_table_entries_with_name(values, rows):
    entries=[{ col:values[(r,col)] for col in CONFIG_COLUMNS} for r in range(rows) if values[(r,NAME)]]
    return entries


def delete_all_table_entries(window, rows):
    [window[(r, col)].update("", background_color=INPUT_COLOR, disabled=False) for col in CONFIG_COLUMNS for r in range(rows)]
    [window[(r, RESULT)].update("") for r in range(rows)]
    

def delete_all_results(window, rows):
    [window[(r, RESULT)].update("", background_color=RESULT_COLOR) for r in range(rows)]
    [window[(r, NAME)].update(background_color=INPUT_COLOR) for r in range(rows)]


def update_table_from_entries(window, entries):
    [window[(r, col)].update(entries[r][col]) for col in CONFIG_COLUMNS for r in range(len(entries))]


def update_table_row_state(window, values, row):
    # disalbe key fields if not github
    doDisable = "github.com" not in values[(row, URL)]
    window[(row, KEY)].update(disabled=doDisable)
    # error color for missing url
    if values[(row, NAME)] and not values[(row, URL)]:
        window[(row, URL)].update(background_color = ERROR_COLOR)
    else:
        window[(row, URL)].update(background_color = INPUT_COLOR)
    # error color for missing name
    if not values[(row, NAME)] and values[(row, URL)]:
        window[(row, NAME)].update(background_color = ERROR_COLOR)
    else:
        window[(row, NAME)].update(background_color = INPUT_COLOR)


def update_community_folder_state(window, newFolder, folderDetected):
    if folderDetected:
        window["cf"].update(background_color = INPUT_COLOR, disabled = True)
    else:
        if newFolder and os.path.exists(newFolder):
            window["cf"].update(background_color = INPUT_COLOR)
        else:
            window["cf"].update(background_color = ERROR_COLOR)


def update_all_table_row_states(window, values, MAX_ROWS):
    for r in range(MAX_ROWS):
        update_table_row_state(window, values, r)


def main():
    # Set execution folder to folder of .py file
    os.chdir(sys.path[0])
    communityFolder = ""
    msStoreFolder = os.path.join(os.getenv("LOCALAPPDATA"), "Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalCache/Packages/Community") 
    steamFolder = os.path.join(os.getenv("APPDATA"), "Microsoft Flight Simulator/Packages/Community")
    boxFolder = os.path.join(os.getenv("LOCALAPPDATA"), "MSFSPackages/Community")
    if os.path.exists(msStoreFolder):
        communityFolder = msStoreFolder
    elif os.path.exists(steamFolder):
        communityFolder =  steamFolder
    elif os.path.exists(boxFolder):
        communityFolder =  boxFolder

    folderDetected = communityFolder != ""
    entries, configCF = read_from_xml()
    # Overwrite auto detected community folder
    if configCF and configCF != communityFolder:
        folderDetected = False
        communityFolder = configCF
   
    folderCount = 0
    if communityFolder and os.path.exists(communityFolder):
        list_subfolders = [f.name for f in os.scandir(communityFolder) if f.is_dir()] 
        folderCount = len(list_subfolders) + 5
    MAX_ROWS = max(len(entries) + 10, 30, folderCount)

    # Generate UI Layout
    column_layout= [[sg.Text(size=(45, 1), pad=(1,1), key=(i, RESULT), font=("Courier", 10), background_color=RESULT_COLOR, text_color="black"),
                    sg.Input(size=(28, 1), pad=(1,1), key=(i, NAME), border_width=0, enable_events=True),
                    sg.Input(size=(20, 1), pad=(1,1), key=(i, COMMENT), border_width=0, text_color="grey"),
                    sg.Input(size=(68, 1), pad=(1,1), key=(i, URL), border_width=0, enable_events=True),
                    sg.Button(size=(1, 1), pad=(1,1), key=(i, GO), border_width=1, font=("Arial", 7), button_color="lightgrey" ),
                    sg.Input(size=(10, 1), pad=(1,1), key=(i, VERSION), border_width=0, tooltip="Set fixed installed version"),
                    sg.Input(size=(9, 1), pad=(1,1), key=(i, KEY), disabled_readonly_background_color = "lightgrey", border_width=0, tooltip="Version filter key for github")] 
                    for i in range(MAX_ROWS)]
   
    layout = [[sg.Text("Community folder: "), sg.Input(size=(140, 1), pad=(1,15), enable_events=True, key="cf", disabled_readonly_background_color = "lightgrey")], 
            [sg.B(RUN, size=(10,1)), sg.Text(size=(36, 1)), sg.B(SAVE, size=(10,1)), sg.B("Read Community Folder", size=(25,1)), sg.B("Delete Incomplete Rows", size=(24,1))],
            [sg.HorizontalSeparator(RUN,pad=(1,10) )],
            [sg.Text(size=(45, 1), pad=(1,1), text="{:<16}{:<16}{:<25}".format("INSTALLED", "ONLINE", "RELEASE"), font=("Courier", 10)),
             sg.Text(size=(24, 1), pad=(1,1), text="NAME"),
             sg.Text(size=(17, 1), pad=(1,1), text="COMMENT"),
             sg.Text(size=(61, 1), pad=(1,1), text="URL"),
             sg.Text(size=(9, 1), pad=(1,1), text="FIX Version", tooltip="Set fixed installed version"),
             sg.Text(size=(8, 1), pad=(1,1), text="KEY",  tooltip="Version filter key for github")],
            [sg.Column(column_layout, size=(1355, 660), pad=(0,0), scrollable=True, vertical_scroll_only = True)]]

    window = sg.Window('MSFS Addon Version Checker 2.4', layout,  return_keyboard_events=False)
    window.finalize()

    # Fill content to UI
    update_table_from_entries(window, entries)
    window["cf"].update(communityFolder)
    event, values = window.read(0)
    update_all_table_row_states(window, values, MAX_ROWS)
    update_community_folder_state(window, communityFolder, folderDetected)

    # Process UI events
    while True:  
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        elif event == "cf": # change community Folder
            update_community_folder_state(window, values[event], folderDetected)
        elif type(event) is tuple and event[1] == URL: # change in URL
            update_table_row_state(window, values, event[0])
        elif type(event) is tuple and event[1] == NAME: # change in Name
            update_table_row_state(window, values, event[0])
        elif type(event) is tuple and event[1] == GO and values[event[0], URL]:
            webbrowser.open(values[event[0], URL])
        elif event == SAVE:
            nameEntries = read_table_entries_with_name(values, MAX_ROWS)
            if os.path.exists(values["cf"]):
                write_to_xml(nameEntries, values["cf"])
            else:
                write_to_xml(nameEntries, "")
        elif event == "Read Community Folder":
            read_community_folder(window, values, values["cf"], MAX_ROWS)
        elif event == "Delete Incomplete Rows":
            entries = read_complete_table_entries(values, MAX_ROWS)
            delete_all_table_entries(window, MAX_ROWS)
            delete_all_results(window, MAX_ROWS)
            update_table_from_entries(window, entries)
            event, values = window.read(0) # refresh values
            update_all_table_row_states(window, values, MAX_ROWS)
        elif event == RUN:
            delete_all_results(window, MAX_ROWS)
            th = threading.Thread(target=addon_worker_thread, args=(window, values, values["cf"], MAX_ROWS))
            th.start()

if __name__ == "__main__":
    main()
