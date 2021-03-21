# MSFS Addon Version Checker

### Introduction
This simple application shows the installed versions and online available version of configured addons and tools for the Microsoft Flight Simulator. So it can be used to get an overview whether new versions are available.

Supported sources for addons and tools are:
* flightsim.to
* github.com

### Installation and Execution
Download the latest released version. Unpack to a folder. For configuration edit addons.xml. Execute checkAddons.exe.

### Configuration
For configuration edit addons.xml with a proper editor. E.g. "Notepad", "Editor", ["Notepad++"](https://notepad-plus-plus.org/downloads/) or ["Visual Studio Code"](https://code.visualstudio.com/)". 

For each addon or tool add a new line in the xml file and adjust the attributes like name and url accordingly. Edit the parts between the "".

* **name**: Enter the exact name of the addon folder in your community folder. For a tool just enter the name of the tool.
* **url**: Enter the url to the flightsim or github page to the tool or addon like in the examples.
* **installedVersion**: For tools enter you installed version manually. For addons in the community folder it is auto detected. You can also manually enter an installed version for addons. That can be useful if the addon maker does not properly update its version information.
* **versionKey**: For github you can optionally add a versionKey. That is necessary if an addon maker does release different addons in the the same github repository like Working-Title.

### Development information
#### Execute Python Script
If you want to run the python script directly:
* Install [Python](https://www.python.org/downloads/). On Installation check box for Path inclusion.
* Install additional libraries via command shell:
    * `pip install requests`
    * `pip install beautifulsoup4`
    * `pip install pyinstaller`
* Now switch to the directory and you can run the python script via `python checkAddons.py`. Also it is possible to create a batch file like checkAddons.bat which contains `python checkAddons.py`.

#### Build Executable
Comment out os.chdir(sys.path[0]) in checkAddons.py. Then run createExecutable.bat.

