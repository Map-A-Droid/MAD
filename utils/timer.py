import logging
import os, sys
from pathlib import Path
import json

log = logging.getLogger(__name__)

class PlayerStats(object):
    def __init__(self, id):
        self._sleep = false
        self._switch = false
        self._sleeptime = "0"
        
        
    def set_sleep(self, switch):
        log.info('[%s] - set sleep: %s' % (str(self._id), str(sleep)))
        self._switch = switch
        return
        
    def get_sleep(self):
        return self._switch
        
    def check_sleeptimer(self, sleep, sleeptime):
        if sleep:
            self._sleeptime = sleeptime
            t_sleeptimer = Thread(name='sleeptimer',
                                  target=sleeptimer)
            t_sleeptimer.daemon = True
            t_sleeptimer.start()
            
    def _gen_player_stats(self, data):
        if 'inventory_delta' not in data:
            log.debug('{{gen_player_stats}} cannot generate new stats')
            return True
        stats= data['inventory_delta'].get("inventory_items", None)
        if len(stats) > 0 :
            for data_inventory in stats:
                player_level = data_inventory['inventory_item_data']['player_stats']['level']
                if int(player_level) > 0:
                    log.debug('{{gen_player_stats}} saving new playerstats')
                    self.set_level(int(player_level))
                            
                    data = {}  
                    data[self._id] = []
                    data[self._id].append({  
                        'level': str(data_inventory['inventory_item_data']['player_stats']['level']), 
                        'experience': str(data_inventory['inventory_item_data']['player_stats']['experience']),
                        'km_walked': str(data_inventory['inventory_item_data']['player_stats']['km_walked']),
                        'pokemons_encountered': str(data_inventory['inventory_item_data']['player_stats']['pokemons_encountered']),
                        'poke_stop_visits': str(data_inventory['inventory_item_data']['player_stats']['poke_stop_visits'])
                    })
                    with open(self._id + '.stats', 'w') as outfile:  
                        json.dump(data, outfile, indent=4, sort_keys=True)

    def sleeptimer():
        sleeptime = _sleeptime
        sts1 = sleeptime[0].split(':')
        sts2 = sleeptime[1].split(':')
        while True:
            tmFrom = datetime.datetime.now().replace(hour=int(sts1[0]),minute=int(sts1[1]),second=0,microsecond=0)
            tmTil = datetime.datetime.now().replace(hour=int(sts2[0]),minute=int(sts2[1]),second=0,microsecond=0)
            tmNow = datetime.datetime.now()

            # check if current time is past start time
            # and the day has changed already. thus shift
            # start time back to the day before
            if tmFrom > tmTil > tmNow:
                tmFrom = tmFrom + datetime.timedelta(days=-1)

            # check if start time is past end time thus
            # shift start time one day into the future
            if tmTil < tmFrom:
                tmTil = tmTil + datetime.timedelta(days=1)

            log.debug("Time now: %s" % tmNow)
            log.debug("Time From: %s" % tmFrom)
            log.debug("Time Til: %s" % tmTil)

            if tmFrom <= tmNow < tmTil:
                log.info('Going to sleep - bye bye')
                self.set_sleep(True)

                while MadGlobals.sleep:
                    log.info("Currently sleeping...zzz")
                    log.debug("Time now: %s" % tmNow)
                    log.debug("Time From: %s" % tmFrom)
                    log.debug("Time Til: %s" % tmTil)
                    tmNow = datetime.datetime.now()
                    log.info('Still sleeping, current time... %s' % str(tmNow.strftime("%H:%M")))
                    if tmNow >= tmTil:
                        log.warning('sleeptimer: Wakeup - here we go ...')
                        self.set_sleep(False)
                        break
                    time.sleep(30)
            time.sleep(30)