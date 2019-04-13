from adb.client import Client as AdbClient
from pprint import pprint
# Default is "127.0.0.1" and 5037
client = AdbClient(host="127.0.0.1", port=5037)
devices = client.devices()

for device in devices:
    print(device.serial)