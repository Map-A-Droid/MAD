import json
import shutil

from utils.logging import logger

mapping_file = './configs/mappings.json'
save_mapping_file = './configs/mappings_org.json'


def convert_mappings():

    with open(mapping_file) as f:
        __raw_json = json.load(f)

    walker = []
    walkersetup = []
    if "walker" not in __raw_json:
        logger.info("Unconverted mapping file found")
        logger.info("Saving current file")
        shutil.copy(mapping_file, save_mapping_file)
        __raw_json['walker'] = []
        count = 0
        walker = []
        exist = {}

        for dev in __raw_json['devices']:
            logger.info("Converting device {}", str(dev['origin']))

            walkersetup = []
            daytime_area = dev.get('daytime_area', False)
            nightime_area = dev.get('nighttime_area', False)
            walkername = str(daytime_area)
            timer_invert = ""
            if nightime_area:
                if (dev.get('switch', False)):
                    timer_old = dev.get('switch_interval', "['0:00','23:59']")
                    walkername = walkername + '-' + str(nightime_area)
                    timer_normal = str(timer_old[0]) + '-' + str(timer_old[1])
                    timer_invert = str(timer_old[1]) + '-' + str(timer_old[0])
                    del __raw_json['devices'][count]['switch_interval']
                    del __raw_json['devices'][count]['switch']

            if len(timer_invert) > 0:
                walkersetup.append(
                    {'walkerarea': daytime_area, "walkertype": "period", "walkervalue": timer_invert})
                walkersetup.append(
                    {'walkerarea': nightime_area, "walkertype": "period", "walkervalue": timer_normal})
            else:
                walkersetup.append(
                    {'walkerarea': daytime_area, "walkertype": "coords", "walkervalue": ""})

            if walkername not in exist:
                walker.append({'walkername': walkername, "setup": walkersetup})
                exist[walkername] = True

            del __raw_json['devices'][count]['daytime_area']
            del __raw_json['devices'][count]['nighttime_area']

            __raw_json['devices'][count]['walker'] = str(walkername)

            count += 1
        __raw_json['walker'] = walker

        with open(mapping_file, 'w') as outfile:
            json.dump(__raw_json, outfile, indent=4, sort_keys=True)
            logger.info('Finished converting mapping file')
