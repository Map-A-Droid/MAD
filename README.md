# Requirements
- Python3.6
- MySQL DB holding basic Monocle or RM structure
- Rooted Android device running RemoteGPSController and Pogodroid

# Setup
## Debian

Install python3.6, pip3 (TODO: detailed description...)
```bash
pip install requirements.txt
```
in case you want to use OCR to scan raids, run it with `requirements_ocr.txt`


## General config
Populate configs/config.ini with at least the DB and websocket configurations 
(examples on the values to be inserted can be found in config.ini.example)

In order to map devices to areas, populate configs/mappings.json.
Refer to mappings_example.json for examples or run `python3.6 start.py -wm` and open the mappings editor.
Each area *requires* `geofence_included`. A geofence can easily be created with http://geo.jasparke.net/.
> A geofence requires a name:
> `[geofence name]`
> with `lat, lng` per line, no empty lines at the end of file


## Apps
RGC and Pogodroid both require an Origin header field that's configured in mappings.json.
These Origins need to be unique per running python instance.
Furthermore, RGC takes the websocket port as destination, Pogodroid the `mitmreceiver_port`.

# Starting MAD
Simply run `python3.6 start.py`

Usually you will want to append `-wm` and `-os` 
as arguments to start madmin (browser based monitoring) and the scanner (`-os`) responsible 
for controlling devices and receiving data from Pogodroid (if OCR enabled, also take screenshots).

If you want to run OCR on screenshots, run `-oo` to analyse screenshots

# Security
RGC and Pogodroid both support wss/HTTPS respectively. Thus you may setup 
reverse proxies for MAD. The Auth headers in RGC and Pogodroid both use Basic auth.
Meaning the password/username is not encrypted per default, that's to be done by SSL/TLS (wss, HTTPS).
