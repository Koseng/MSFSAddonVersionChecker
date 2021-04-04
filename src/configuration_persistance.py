from xml.dom import minidom

XML_FILE = "addons.xml"
NAME = "name"
COMMENT = "comment"
VERSION = "version"
KEY = "key"
URL = "url"

def read_from_xml():
    doc = minidom.parse(XML_FILE)
    communityFolder = ""
    entries = []
    addons = doc.getElementsByTagName("addon")
    if doc.documentElement.hasAttribute("communityFolder"):  
        communityFolder = doc.documentElement.getAttribute("communityFolder")
    for addon in addons:
        entry = {NAME:"", URL:"", VERSION:"", KEY:"", COMMENT:""}
        entry[NAME] = addon.getAttribute(NAME)
        entry[URL] = addon.getAttribute(URL)
        if addon.hasAttribute("installedVersion"):
            entry[VERSION] = addon.getAttribute("installedVersion")
        if addon.hasAttribute("versionKey"):
            entry[KEY] = addon.getAttribute("versionKey")
        if addon.hasAttribute(COMMENT):
            entry[COMMENT] = addon.getAttribute(COMMENT)
        entries.append(entry)
    return entries, communityFolder


def write_to_xml(entries, communityFolder):
    doc = minidom.parseString("<configuration></configuration>")
    if communityFolder:
        doc.documentElement.setAttribute("communityFolder", communityFolder)
    for entry in entries:
        if entry[NAME]:
            addon = doc.createElement("addon")
            addon.setAttribute(NAME, entry[NAME])
            addon.setAttribute(URL, entry[URL])
            if entry[VERSION]:
                addon.setAttribute("installedVersion", entry[VERSION])
            if entry[KEY]:
                addon.setAttribute("versionKey", entry[KEY])
            if entry[COMMENT]:
                addon.setAttribute("comment", entry[COMMENT])
            doc.documentElement.appendChild(addon)
    with open(XML_FILE, 'w') as writer:
        doc.writexml(writer, indent="\t", addindent="\t", newl="\n", encoding="utf-8")