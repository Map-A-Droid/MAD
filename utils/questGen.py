import logging
import json
import re

log = logging.getLogger(__name__)


def generate_quest(quest):
    
        pokestop_id  = (quest['pokestop_id'])
        quest_reward_type = (questreward(quest['quest_reward_type']))
        quest_reward_type_raw = quest['quest_reward_type']
        quest_type_raw = quest['quest_type']
        quest_type = (questtype(quest['quest_type']))
        quest_condition = quest['quest_condition']
        name = quest['name']
        latitude = quest['latitude']
        longitude = quest['longitude']
        url = quest['image']
        timestamp = quest['quest_timestamp']
        quest_target = str(quest['quest_target'])
        
        if quest_reward_type == 'Item':
            item_amount = str(quest['quest_item_amount'])
            item_id = quest['quest_item_id']
            item_type = str(rewarditem(quest['quest_item_id']))
            pokemon_id = "0"
            pokemon_name = ""
        elif quest_reward_type == 'Stardust':
            item_amount = str(quest['quest_stardust'])
            item_type = "Stardust"
            item_id = "000"
            pokemon_id = "0"
            pokemon_name = ""
        elif quest_reward_type == 'Pokemon':
            item_amount = "1"
            item_type = "Pokemon"
            item_id = "000"
            pokemon_name = pokemonname(str(quest['quest_pokemon_id']))
            pokemon_id = str(quest['quest_pokemon_id'])

        if '{0}' in quest_type:
            quest_type_text = quest_type.replace('{0}', quest_target)

        quest_task = questtask(quest_type_raw, quest_condition, quest_target)
        
        quest_raw = ({'pokestop_id': pokestop_id, 'latitude': latitude, 'longitude': longitude, 
            'quest_type_raw': quest_type_raw, 'quest_type': quest_type_text, 'quest_condition': quest_condition, 'item_amount': item_amount, 'item_type': item_type, 
            'quest_target': quest_target, 'name': name, 'url': url, 'timestamp': timestamp, 'pokemon_id': pokemon_id, 'item_id': item_id,
            'pokemon_name': pokemon_name, 'quest_reward_type': quest_reward_type, 'quest_reward_type_raw': quest_reward_type_raw, 'quest_task': quest_task})
        return quest_raw
    
def questreward(quest_reward_type):
    type = {
        2: "Item",
        3: "Stardust",
        7: "Pokemon"
    }
    return type.get(quest_reward_type, "nothing")
    
def questtype(quest_type):
    with open('utils/quest/types.json') as f:
        types = json.load(f)
    return (types[str(quest_type)]['text'])
    
def rewarditem(itemid):
    with open('utils/quest/items.json') as f:
        items = json.load(f)
    return (items[str(itemid)]['name'])
    
def pokemonname(id):
    with open('pokemon.json') as f:
        mondata = json.load(f)
    return mondata[str(int(id))]["name"]

def questtask(typeid, condition, target):
    with open('utils/quest/pokemonTypes.json') as f:
        pokemonTypes = json.load(f)
    with open('utils/quest/items.json') as f:
        items = json.load(f)
    throwTypes = {"10":"Nice", "11":"Great", "12":"Excellent", "13":"Curveball"}
    arr = {}
    arr['0'] = target
    text = questtype(typeid)

    if typeid == 4:
        arr['wb'] = ""
        arr['type'] = ""
        text = "Catch {0} {type}Pokemon{wb}."
        match_object = re.search(r"'pokemon_type': \[([0-9, ]+)\]", condition)
        if match_object is not None:
                pt = match_object.group(1).split(', ')
                last = len(pt)
                cur = 1
                if last == 1:
                    arr['type'] = pokemonTypes[pt[0]].title() + '-type '
                else:
                    for ty in pt:
                        arr['type'] += ('or ' if last == cur else '') + pokemonTypes[ty].title() + ('-type ' if last == cur else '-, ')
                        cur += 1
        if re.search(r"'type': 3", condition) is not None:
                arr['wb'] = " with weather boost"
        match_object = re.search(r"'pokemon_ids': \[([0-9, ]+)\]", condition)
        if match_object is not None:
                pt = match_object.group(1).split(', ')
                last = len(pt)
                cur = 1
                if last == 1:
                    arr['poke'] = pokemonname[pt[0]]
                text = 'Catch a {poke}.'
    elif typeid == 5:
        text = "Spin {0} Pokestops or Gyms."
    elif typeid == 6:
        text = "Hatch {0} Eggs."
    elif typeid == 7:
        if re.search(r"'type': 9", condition) is not None:
            text = "Win {0} Gym Battles."
        elif re.search(r"'type': 10",condition) is not None:
            text = "Use a supereffective Charged Attack in {0} Gym battles."
        else:
            text = "Battle in a Gym {0} times."
    elif typeid == 8:
        if re.search(r"'type': 6",condition) is not None:
            text = "Win {0} Raids."
            if re.search(r"'raid_level': \[3, 4, 5\]",condition) is not None:
                text = 'Win a level 3 or higher raid.'
        else:
            text = "Battle in {0} Raids."
    elif typeid == 10:
        text = "Transfer {0} Pokemon."
    elif typeid == 11:
        "Favourite {0} Pokemon."
    elif typeid == 13:
        text = 'Use {0} {type}Berries to help catch Pokemon.'
        arr['type'] = "";
        match_object = re.search(r"'item': ([0-9]+)",condition)
        if match_object is not None:
            arr['type'] = items[match_object.group(1)]['name'].replace(' Berry','')+" ";
    elif typeid == 14:
        text = 'Power up Pokemon {0} times.'
    elif typeid == 15:
        text = "Evolve {0} Pokemon."
        if re.search(r"'type': 11",condition) is not None:
            text = "Use an item to evolve a Pokemon."
    elif typeid == 16:
        arr['inrow'] = ""
        arr['curve'] = ""
        arr['type'] = ""
        if re.search(r"'type': 14",condition) is not None:
            arr['inrow'] = " in a row"
        if re.search(r"'type': 15",condition) is not None:
            arr['curve'] = "Curveball "
        match_object = re.search(r"'throw_type': ([0-9]{2})",condition)
        if match_object is not None:
            arr['type'] = throwTypes[match_object.group(1)]+" "
        text = "Make {0} {type}{curve}Throws{inrow}."
    elif typeid == 17:
        text = 'Earn {0} Candies walking with your buddy.'
    elif typeid == 23:
        text = 'Trade {0} Pokemon.'
    elif typeid == 24:
        text = 'Send {0} gifts to friends.'

    if str(target) == str(1):
        text = text.replace(' Eggs','n Egg')
        text = text.replace(' Raids',' Raid')
        text = text.replace(' Battles',' Battle')
        text = text.replace(' candies',' candy')
        text = text.replace(' gifts',' gift')
        text = text.replace(' {0} times','')
        arr['0'] = "a";

    for key, val in arr.items():
            text = text.replace('{'+key+'}', val)
    return text
