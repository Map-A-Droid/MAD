import logging
import json
import os

log = logging.getLogger(__name__)

def set_status(origin, data):
    if os.path.exists('status.json'):
        with open('status.json') as f:
            status = json.load(f)
    else:
        status = {}
        
    if 'player' in status[origin]:
        player_stats = status[origin]['player']
        
    status[origin] = data
    status[origin]['player'] = player_stats 

    with open('status.json', 'w') as outfile:
        json.dump(status, outfile, indent=4, sort_keys=True)