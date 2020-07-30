import gettext
import json
import re

from mapadroid.utils.gamemechanicutil import form_mapper
from mapadroid.utils.language import i8ln, open_json_file

gettext.find('quest', 'locales', all=True)
lang = gettext.translation('quest', localedir='locale', fallback=True)
lang.install()


def generate_quest(quest):
    gettext.find('quest', 'locales', all=True)
    lang = gettext.translation('quest', localedir='locale', fallback=True)
    lang.install()

    quest_reward_type = questreward(quest['quest_reward_type'])
    quest_type = questtype(quest['quest_type'])
    if '{0}' in quest_type:
        quest_type = quest_type.replace('{0}', str(quest['quest_target']))

    item_id = 0
    item_amount = 1
    pokemon_id = '000'
    pokemon_name = ''
    item_type = ''
    pokemon_form = '00'
    pokemon_costume = '00'
    pokemon_asset_bundle = '00'

    if quest_reward_type == _('Item'):
        item_amount = quest['quest_item_amount']
        item_type = rewarditem(quest['quest_item_id'])
        item_id = quest['quest_item_id']
    elif quest_reward_type == _('Stardust'):
        item_amount = quest['quest_stardust']
        item_type = _('Stardust')
    elif quest_reward_type == _('Pokemon'):
        item_type = 'Pokemon'
        pokemon_name = i8ln(pokemonname(str(quest['quest_pokemon_id'])))
        pokemon_id = quest['quest_pokemon_id']
        pokemon_form = quest['quest_pokemon_form_id']
        pokemon_costume = quest['quest_pokemon_costume_id']
        if pokemon_form != '00':
            pokemon_asset_bundle = form_mapper(int(pokemon_id), pokemon_form)

    if not quest['task']:
        quest_task = questtask(
            quest['quest_type'], quest['quest_condition'], quest['quest_target'], quest['quest_template'])
    else:
        quest_task = quest['task']

    quest_raw = ({
        'pokestop_id': quest['pokestop_id'],
        'name': quest['name'],
        'url': quest['image'],
        'latitude': quest['latitude'],
        'longitude': quest['longitude'],
        'timestamp': quest['quest_timestamp'],
        'item_id': item_id,
        'item_amount': item_amount,
        'item_type': item_type,
        'pokemon_id': pokemon_id,
        'pokemon_name': pokemon_name,
        'pokemon_form': pokemon_form,
        'pokemon_asset_bundle_id': pokemon_asset_bundle,
        'pokemon_costume': pokemon_costume,
        'quest_type': quest_type,
        'quest_type_raw': quest['quest_type'],
        'quest_reward_type': quest_reward_type,
        'quest_reward_type_raw': quest['quest_reward_type'],
        'quest_task': quest_task,
        'quest_target': quest['quest_target'],
        'quest_condition': quest['quest_condition'],
        'quest_template': quest['quest_template'],

    })
    return quest_raw


def questreward(quest_reward_type):
    type = {
        2: _("Item"),
        3: _("Stardust"),
        7: _("Pokemon")
    }
    return type.get(quest_reward_type, "nothing")


def questtype(quest_type):
    file = open_json_file('types')
    return (file[str(quest_type)]['text'])


def rewarditem(itemid):
    file = open_json_file('items')
    return (file[str(itemid)]['name'])


def pokemonname(id):
    file = open_json_file('pokemon')
    return file[str(int(id))]["name"]


def questtask(typeid, condition, target, quest_template):
    gettext.find('quest', 'locales', all=True)
    lang = gettext.translation('quest', localedir='locale', fallback=True)
    lang.install()

    pokemonTypes = open_json_file('pokemonTypes')
    items = open_json_file('items')
    throwTypes = {"10": _("Nice"), "11": _("Great"),
                  "12": _("Excellent"), "13": _("Curveball")}
    arr = {}
    arr['0'] = target
    text = questtype(typeid)
    # TODO use the dict instead of regex parsing in all logic
    condition_dict = {}
    if condition is not None and condition != '':
        condition_dict = json.loads(condition)

    if typeid == 4:
        arr['wb'] = ""
        arr['type'] = ""
        arr['poke'] = ""
        arr['different'] = ""
        arr['item'] = ""

        text = _("Catch {0}{different} {type}Pokemon{wb}")
        match_object = re.search(r'"pokemon_type": \[([0-9, ]+)\]', condition)
        if match_object is not None:
            pt = match_object.group(1).split(', ')
            last = len(pt)
            cur = 1
            if last == 1:
                arr['type'] = pokemonTypes[pt[0]].title() + _('-type ')
            else:
                for ty in pt:
                    arr['type'] += (_('or ') if last == cur else '') + \
                                   pokemonTypes[ty].title() + (_('-type ')
                                                               if last == cur else '-, ')
                    cur += 1
        if re.search(r'"type": 3', condition) is not None:
            arr['wb'] = _(" with weather boost")
        elif re.search(r'"type": 21', condition) is not None:
            arr['different'] = _(" different species of")
        match_object = re.search(r'"pokemon_ids": \[([0-9, ]+)\]', condition)
        if match_object is not None:
            pt = match_object.group(1).split(', ')
            last = len(pt)
            cur = 1
            if last == 1:
                arr['poke'] = i8ln(pokemonname(pt[0]))
            else:
                for ty in pt:
                    arr['poke'] += (_('or ') if last == cur else '') + \
                                   i8ln(pokemonname(ty)) + ('' if last == cur else ', ')
                    cur += 1
            text = _('Catch {0} {poke}')
    elif typeid == 5:
        text = _("Spin {0} Pokestops or Gyms")
        if re.search(r'"type": 12', condition) is not None:
            text = _("Spin {0} Pokestops you haven't visited before")
    elif typeid == 6:
        text = _("Hatch {0} Eggs")
    elif typeid == 7:
        if re.search(r'"type": 9', condition) is not None:
            text = _("Win {0} Gym Battles")
        elif re.search(r'"type": 10', condition) is not None:
            text = _("Use a supereffective Charged Attack in {0} Gym battles")
        else:
            text = _("Battle in a Gym {0} times")
    elif typeid == 8:
        if re.search(r'"type": 6', condition) is not None:
            text = _("Win {0} Raids")
            if re.search(r'"raid_level": \[3, 4, 5\]', condition) is not None:
                text = _('Win a level 3 or higher raid')
            if re.search(r'"raid_level": \[2, 3, 4, 5\]', condition) is not None:
                text = _('Win a level 2 or higher raid')
        else:
            text = _("Battle in {0} Raids")
    elif typeid == 10:
        text = _("Transfer {0} Pokemon")
    elif typeid == 11:
        text = _("Favourite {0} Pokemon")
    elif typeid == 13:
        text = _('Use {0} {type}Berries to help catch Pokemon')
        arr['type'] = ""
        match_object = re.search(r'"item": ([0-9]+)', condition)
        if match_object is not None:
            arr['type'] = items[match_object.group(
                1)]['name'].replace(_(' Berry'), '') + " "
    elif typeid == 14:
        text = _('Power up Pokemon {0} times')
    elif typeid == 15:
        text = _("Evolve {0} Pokemon")
        for con in condition_dict:
            if con.get('type', 0) == 11:
                text = _("Use an item to evolve {0} Pokemon")
                # Try to find the exact evolution item needed
                # [{"type": 11, "with_item": {"item": 1106}}]
                with_item = con.get('with_item', {}).get('item', None)
                if with_item is not None:
                    text = _('Use {item} to evolve {0} Pokemon')
                    arr['item'] = items[str(with_item)]['name']
            if con.get('type', 0) == 1:
                text = _("Evolve {0} {type}Pokemon")
                arr['wb'] = ""
                arr['type'] = ""
                arr['poke'] = ""
                match_object = re.search(
                    r'"pokemon_type": \[([0-9, ]+)\]', condition)
                if match_object is not None:
                    pt = match_object.group(1).split(', ')
                    last = len(pt)
                    cur = 1
                    if last == 1:
                        arr['type'] = pokemonTypes[pt[0]].title() + _('-type ')
                    else:
                        for ty in pt:
                            arr['type'] += (_('or ') if last == cur else '') + pokemonTypes[ty].title() + (
                                _('-type ') if last == cur else '-, ')
                            cur += 1
            if re.search(r'"type": 2', condition) is not None:
                arr['wb'] = ""
                arr['type'] = ""
                arr['poke'] = ""

                match_object = re.search(
                    r'"pokemon_ids": \[([0-9, ]+)\]', condition)
                if match_object is not None:
                    pt = match_object.group(1).split(', ')
                    last = len(pt)
                    cur = 1
                    if last == 1:
                        arr['poke'] = i8ln(pokemonname(pt[0]))
                    else:
                        for ty in pt:
                            arr['poke'] += (_('or ') if last == cur else '') + i8ln(pokemonname(ty)) + (
                                '' if last == cur else ', ')
                            cur += 1
                    text = _('Evolve {0} {poke}')
    elif typeid == 16:
        arr['inrow'] = ""
        arr['curve'] = ""
        arr['type'] = ""
        if re.search(r'"type": 14', condition) is not None:
            arr['inrow'] = _(" in a row")
        if re.search(r'"type": 15', condition) is not None:
            arr['curve'] = _("Curveball ")
        match_object = re.search(r'"throw_type": ([0-9]{2})', condition)
        if match_object is not None:
            arr['type'] = throwTypes[match_object.group(1)] + " "
        text = _("Make {0} {type}{curve}Throws{inrow}")
    elif typeid == 17:
        text = _('Earn {0} Candies walking with your buddy')
    elif typeid == 22:
        if int(target) == int(1):
            text = _('Make a new friend')
        else:
            text = _('Make {0} new friends')
    elif typeid == 23:
        text = _('Trade {0} Pokemon')
        arr['distance'] = ""
        if re.search(r'"type": 25', condition) is not None:
            arr['distance'] = re.search(r'"distance_km": ([0-9, ]+)', condition).group(1)
            if int(target) == int(1):
                text = _('Trade Pokemon caught {distance} km apart')
            else:
                text = _('Trade {0} Pokemon caught {distance} km apart')
    elif typeid == 24:
        text = _('Send {0} gifts to friends')
    elif typeid == 27:
        for con in condition_dict:
            if con.get('type', 0) == 22:
                # PVP against team leader.
                text = _('Battle a Team Leader {0} times')
            elif con.get('type') == 23:
                gotta_win = con.get('with_pvp_combat', {}).get('requires_win') is True

                if gotta_win:
                    text = _('Win a battle against another Trainer {0} times')
                else:
                    text = _('Battle another Trainer {0} times')

                in_go_battle_league = any(
                    x in con.get('with_pvp_combat', {}).get('combat_league_template_id', []) for x in
                    ["COMBAT_LEAGUE_VS_SEEKER_GREAT", "COMBAT_LEAGUE_VS_SEEKER_ULTRA",
                     "COMBAT_LEAGUE_VS_SEEKER_MASTER"])
                vs_player = any(
                    x in con.get('with_pvp_combat', {}).get('combat_league_template_id', []) for x in
                    ["COMBAT_LEAGUE_DEFAULT_GREAT", "COMBAT_LEAGUE_DEFAULT_ULTRA",
                     "COMBAT_LEAGUE_DEFAULT_MASTER"])
                if not vs_player and in_go_battle_league and gotta_win:
                    text = _('Win in the GO Battle League {0} times')
                elif in_go_battle_league and not vs_player:
                    text = _('Battle in the GO Battle League {0} times')
    elif typeid == 28:
        # Take snapshots quest
        if re.search(r'"type": 28', condition) is not None:
            text = _("Take {0} snapshots of your Buddy")
        elif re.search(r'"type": 2', condition) is not None:
            arr['poke'] = ""

            match_object = re.search(
                r'"pokemon_ids": \[([0-9, ]+)\]', condition)
            if match_object is not None:
                pt = match_object.group(1).split(', ')
                last = len(pt)
                cur = 1
                if last == 1:
                    arr['poke'] = i8ln(pokemonname(pt[0]))
                else:
                    for ty in pt:
                        arr['poke'] += (_('or ') if last == cur else '') + i8ln(pokemonname(ty)) + (
                            '' if last == cur else ', ')
                        cur += 1
                text = _("Take {0} snapshots of {poke}")
        elif re.search(r'"type": 1', condition) is not None:
            text = _("Take {0} snapshots of {type} Pokemon")
            arr['wb'] = ""
            arr['type'] = ""
            arr['poke'] = ""
            match_object = re.search(
                r'"pokemon_type": \[([0-9, ]+)\]', condition)
            if match_object is not None:
                pt = match_object.group(1).split(', ')
                last = len(pt)
                cur = 1
                if last == 1:
                    arr['type'] = pokemonTypes[pt[0]].title() + _('-type ')
                else:
                    for ty in pt:
                        arr['type'] += (_('or ') if last == cur else '') + pokemonTypes[ty].title() + (
                            _('-type ') if last == cur else '-, ')
                        cur += 1
    elif typeid == 29:
        # QUEST_BATTLE_TEAM_ROCKET Team Go rucket grunt batles.
        if int(target) == int(1):
            text = _('Battle a Team Rocket Grunt')

        for con in condition_dict:
            if con.get('type', 0) == 27 and con.get('with_invasion_character', {}).get('category') == 1:
                text = _('Battle {0} times against the Team GO Rocket Leaders')
                # TODO Handle category for specific team leaders as well (Arlo, Cliff, Sierra)
            if con.get('type', 0) == 18:
                # Condition type 18 means win a battle
                # TODO change WIN to Defeat like in-game
                text = text.replace(_('Battle'), _('Defeat'))

    quest_templates = open_json_file('quest_templates')
    if quest_template is not None and quest_template in quest_templates:
        text = _(quest_templates[quest_template])

    if int(target) == int(1):
        text = text.replace(_(' Eggs'), _('n Egg'))
        text = text.replace(_(' Raids'), _(' Raid'))
        text = text.replace(_(' Battles'), _(' Battle'))
        text = text.replace(_(' candies'), _(' candy'))
        text = text.replace(_(' gifts'), _(' gift'))
        text = text.replace(_(' Pokestops'), _(' Pokestop'))
        text = text.replace(_(' {0} snapshots'), _(' a snapshot'))
        text = text.replace(_('Make {0} {type}{curve}Throws'), _('Make a {type}{curve}Throw'))
        text = text.replace(_(' {0} times'), '')
        text = text.replace(_('{0} hearts'), _('a heart'))
        arr['0'] = _("a")

    for key, val in arr.items():
        text = text.replace('{' + key + '}', str(val))

    text = text.replace('  ', ' ').strip()
    return text
