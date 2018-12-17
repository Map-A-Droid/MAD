# Map'A'Droid
![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)

Map'A'Droid is a Raid & Pokémon scanner for Pokémon GO, based on Android devices.

## Information
*  [Discord](https://discord.gg/7TT58jU) - For general support
*  [Github Issues](https://github.com/Map-A-Droid/MAD/issues) - For reporting bugs (not for support!)

## Requirements
- Python 3.6
- MySQL database, with RocketMap or Monocle structure
- Rooted Android device
- PogoDroid token, obtainable [via Patreon](https://www.patreon.com/user?u=14159560)

## Setup
### Ubuntu/Debian

Install `python 3.6` & `pip3` according to docs for your platform.  

Once Python is installed, ensure that `pip` and `python` is installed correctly by running:
* `python3.6 --version` - should return `3.6.X`
* `pip3 --version` - If it returns a version, it is working.  

Clone this repository:
```bash
git clone https://github.com/Map-A-Droid/MAD.git
```

Make sure you're in the directory of MAD and run:
```bash
pip3 install -r requirements.txt
```
If you want to use OCR to scan raids, run with `requirements_ocr.txt`  

![MAD concept graphic](https://github.com/Map-A-Droid/MAD/static/concept.jpg)

>MAD is compatible with [this Monocle schema](https://github.com/whitewillem/PMSF/blob/master/cleandb.sql) and [this RocketMap fork](https://github.com/cecpk/OSM-Rocketmap). Please use them or change your database accordingly.

## Configuration
Inside the `config` folder, duplicate the `config.ini.example` and rename it to `config.ini`. Then populate it with at least the database and websocket configurations.

### Multiple Devices
In order to map devices to areas, do the same with `mappings_example.json` and rename it to `mappings.json`
Refer to mappings_example.json for examples or run `python3.6 start.py -wm` and open the MADMIN mappings editor (http://localhost:5000).  

### Geofence
Each area *requires* `geofence_included`. A geofence can easily be created with [geo.jesparke.net](http://geo.jasparke.net/)
> A geofence requires a name:
> `[geofence name]`
> with `lat, lng` per line, no empty lines at the end of file  


## Applications
[RGC (Remote GPS Controller)](https://github.com/Map-A-Droid/MAD/blob/master/APK/RemoteGpsController.apk) and [PogoDroid](https://www.maddev.de/apk/PogoDroid.apk) both require an Origin header field that's configured in mappings.json.
These Origins need to be unique per running python instance.
Furthermore, RGC takes the websocket port as destination, Pogodroid the `mitmreceiver_port`.

To login into PogoDroid, you need a token. You can obtain a token with sending the command `!token` to the MAD Discord Bot. This will only work, if you're a [Patreon supporter](https://www.patreon.com/user?u=14159560) and linked your account to Discord.

## Launching MAD
Make sure you're in the directory of MAD and run:
```bash
python3.6 start.py
```  

Usually you want to append `-wm` and `-os`
as arguments to start madmin (browser based monitoring) and the scanner (`-os`) responsible
for controlling devices and receiving data from Pogodroid (if OCR enabled, also take screenshots).

If you want to run OCR on screenshots, run `-oo` to analyse screenshots

## Security
RGC and PogoDroid both support wss/HTTPS respectively. Thus you may setup
reverse proxies for MAD. The Auth headers in RGC and Pogodroid both use Basic auth.
Meaning the password/username is not encrypted per default, that's to be done by SSL/TLS (wss, HTTPS).
