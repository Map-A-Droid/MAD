import gettext
import json
import re
from typing import Dict

import requests

from mapadroid.utils.gamemechanicutil import form_mapper
from mapadroid.utils.language import i8ln, open_json_file
from mapadroid.utils.logging import LoggerEnums, get_logger

QUEST_LANGUAGES: Dict[str, str] = {
    'de': 'German',
    'en': 'English',
    'fr': 'French'
}

logger = get_logger(LoggerEnums.utils)


class QuestGen:
    def __init__(self, args):
        gettext.find('quest', 'locales', all=True)
        self.lang = gettext.translation('quest', localedir='locale', fallback=True)
        self.lang.install()

        self.pokemon_types = open_json_file('pokemonTypes')
        self.items = open_json_file('items')
        self.quest_type_file = open_json_file('types')
        self.quest_templates = open_json_file('quest_templates')
        self.pokemen_file = open_json_file('pokemon')

        self.quest_rewards = {
            1: _("Experience"),
            2: _("Item"),
            4: _("Candy"),
            3: _("Stardust"),
            7: _("Pokemon"),
            12: _("Energy")
        }

        if not args.no_quest_titles:
            locale_url = "https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Texts/Latest%20APK/{0}.txt"
            remote_locale_url = "https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Texts/Latest%20Remote/" \
                                "{0}.txt"

            asset_language = QUEST_LANGUAGES.get(args.language, 'English')
            apk_locale = self.__gen_assets_locale(locale_url.format(asset_language))
            remote_locale = self.__gen_assets_locale(remote_locale_url.format(asset_language))
            if apk_locale is None and remote_locale is None:
                self.locale_resources = None
                return

            if apk_locale is None:
                apk_locale = {}
            if remote_locale is None:
                remote_locale = {}
            self.locale_resources = {**apk_locale, **remote_locale}
        else: self.locale_resources = None

    @staticmethod
    def __gen_assets_locale(url):
        try:
            req = requests.get(url, timeout=10)
            if req.status_code != 200:
                return None

            raw = req.text
            keys = re.findall(r"(?<=RESOURCE ID: ).*", raw)
            values = re.findall(r"(?<=TEXT: ).*", raw)
            return {keys[i].strip("\r"): values[i].strip("\r") for i in range(len(keys))}
        except requests.exceptions.Timeout:
            return None

    def generate_quest(self, quest):
        quest_reward_type = self.questreward(quest['quest_reward_type'])
        quest_type = self.questtype(quest['quest_type'])
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
            item_type = self.rewarditem(quest['quest_item_id'])
            item_id = quest['quest_item_id']
        elif quest_reward_type == _('Stardust'):
            item_amount = quest['quest_stardust']
            item_type = _('Stardust')
        elif quest_reward_type == _('Pokemon'):
            item_type = 'Pokemon'
            pokemon_name = i8ln(self.pokemonname(str(quest['quest_pokemon_id'])))
            pokemon_id = quest['quest_pokemon_id']
            pokemon_form = quest['quest_pokemon_form_id']
            pokemon_costume = quest['quest_pokemon_costume_id']
            if pokemon_form != '00':
                pokemon_asset_bundle = form_mapper(int(pokemon_id), pokemon_form)
        elif quest_reward_type == _('Energy'):
            item_type = _('Mega Energy')
            if quest['quest_pokemon_id'] and int(quest['quest_pokemon_id']) > 0:
                pokemon_name = i8ln(self.pokemonname(str(quest['quest_pokemon_id'])))
                pokemon_id = quest['quest_pokemon_id']
            else:
                pokemon_name = ''
            item_amount = quest['quest_item_amount']
        elif quest_reward_type == _("Candy"):
            # TODO maybe we should be doing deep parsing against the reward array
            item_amount = quest['quest_item_amount']
            item_type = quest_reward_type
            pokemon_id = quest['quest_pokemon_id']
            pokemon_name = pokemon_name = i8ln(self.pokemonname(str(pokemon_id)))
        elif quest_reward_type == _('Experience'):
            item_type = quest_reward_type
            item_amount = quest.quest_stardust

        if not quest['task']:
            quest_task = self.questtask(
                quest['quest_type'], quest['quest_condition'], quest['quest_target'], quest['quest_template'],
                quest['quest_title'])
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
            'quest_reward_raw': quest['quest_reward'],
            'is_ar_scan_eligible': quest['is_ar_scan_eligible'],
            'quest_title': quest['quest_title']
        })
        return quest_raw

    def questreward(self, quest_reward_type):
        return self.quest_rewards.get(quest_reward_type, "nothing")

    def questtype(self, quest_type):
        if str(quest_type) in self.quest_type_file:
            return self.quest_type_file[str(quest_type)]['text']

        return "Unknown quest type placeholder: {0}"

    def rewarditem(self, itemid):
        file = open_json_file('items')
        if str(itemid) in file:
            return (file[str(itemid)]['name'])
        return "Item " + str(itemid)

    def pokemonname(self, id):
        return self.pokemen_file[str(int(id))]["name"]

    def get_pokemon_type_str(self, pt):
        return self.pokemon_types[str(pt)].title() + _('-type')

    def questtask(self, typeid, condition, target, quest_template, quest_title):
        if quest_title is not None and self.locale_resources is not None and quest_title in self.locale_resources:
            qt = self.locale_resources[quest_title]
            if '{0}' in qt:
                return qt.format(target)
            return qt

        gettext.find('quest', 'locales', all=True)
        throw_types = {"10": _("Nice"), "11": _("Great"),
                       "12": _("Excellent"), "13": _("Curveball")}
        buddyLevels = {2: _("Good"), 3: _("Great"), 4: _("Ultra"), 5: _("Best")}
        arr = {'0': target}
        text = self.questtype(typeid)
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

            for con in condition_dict:
                condition_type = con.get('type', 0)
                if condition_type == 1:
                    # Condition type 1 is pokemon_types
                    pokemon_type_array = con.get('with_pokemon_type', {}).get('pokemon_type', [])
                    num_of_pokemon_types = len(pokemon_type_array)
                    if num_of_pokemon_types > 1:
                        arr['type'] = "{}- or {} ".format(
                            _('-, ').join(self.pokemon_types[str(pt)].title() for pt in pokemon_type_array[::-1]),
                            self.get_pokemon_type_str(pokemon_type_array[-1]))
                    elif num_of_pokemon_types == 1:
                        arr['type'] = self.get_pokemon_type_str(pokemon_type_array[0]) + " "
                elif condition_type == 2:
                    # Condition type 2 is to catch certain kind of pokemons
                    pokemon_id_array = con.get('with_pokemon_category', {}).get('pokemon_ids', [])

                    if len(pokemon_id_array) > 0:
                        text = _('Catch {0} {poke}')
                        if len(pokemon_id_array) == 1:
                            arr['poke'] = i8ln(self.pokemonname(pokemon_id_array[0]))
                        else:
                            # More than one mon, let's make sure to list them comma separated ending with or
                            arr['poke'] = "{} or {} ".format(
                                _(', ').join(i8ln(self.pokemonname(pt)) for pt in pokemon_id_array[::-1]),
                                i8ln(self.pokemonname(pokemon_id_array[-1])))
                elif condition_type == 3:
                    # Condition type 3 is weather boost.
                    arr['wb'] = _(" with weather boost")
                elif condition_type == 21:
                    # condition type 21 is unique pokemon
                    arr['different'] = _(" different species of")
                elif condition_type == 26:
                    # Condition type 26 is alignment
                    alignment = con.get('with_pokemon_alignment', {}).get('alignment', [])
                    # POKEMON_ALIGNMENT_UNSET = 0;
                    # POKEMON_ALIGNMENT_SHADOW = 1;
                    # POKEMON_ALIGNMENT_PURIFIED = 2;
                    if len(alignment) == 1 and alignment[0] == 1:
                        arr['different'] = _(" shadow")
                    elif len(alignment) == 1 and alignment[0] == 2:
                        # AFAIK you can't catch purified pokemon directly, but who knows..
                        arr['different'] = _(" purified")
        elif typeid == 5:
            if '"type": 12' in condition:
                text = _("Spin {0} Pokestops you haven't visited before")
            else:
                text = _("Spin {0} Pokestops or Gyms")
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
            # type 8 is to do raids
            raid_levels = []
            arr['min_level'] = ''
            arr['speedy'] = ''
            arr['verb'] = 'Battle in'
            text = _("{verb} {0} {min_level}raids{speedy}")
            for con in condition_dict:
                con_type = con.get('type', 0)
                if con_type == 6:
                    # Gotta win it
                    arr['verb'] = 'Win'
                elif con_type == 7:
                    # do a certain level raid
                    raid_levels = con.get('with_raid_level', {}).get('raid_level', [])
                elif con_type == 44:
                    # have to do it quick
                    how_fast = con.get('with_elapsed_time', {}).get('elapsed_time', 60000)
                    if how_fast > 1000:
                        how_fast = how_fast / 1000
                    arr['speedy'] = _(' in {time} seconds')
                    arr['time'] = int(how_fast)
            if len(raid_levels) == 1 == raid_levels[0] == 6:
                arr['min_level'] = _('Mega ')
            elif len(raid_levels) > 0:
                arr['min_level'] = '{} {} {}'.format(_('level'), min(raid_levels), _(' or higher '))
        elif typeid == 10:
            text = _("Transfer {0} Pokemon")
        elif typeid == 11:
            text = _("Favourite {0} Pokemon")
        elif typeid == 13:
            text = _('Use {0} {type}Berries to help catch Pokemon')
            arr['type'] = ""
            match_object = re.search(r'"item": ([0-9]+)', condition)
            if match_object is not None:
                arr['type'] = self.items[match_object.group(
                    1)]['name'].replace(_(' Berry'), '') + " "
        elif typeid == 14:
            text = _('Power up Pokemon {0} times')
        elif typeid == 15 or typeid == 43:
            arr['mega'] = ""
            text = _("{mega}Evolve {0} Pokemon")
            if typeid == 43:
                arr['mega'] = _("Mega ")

            for con in condition_dict:
                if con.get('type', 0) == 11:
                    text = _("Use an item to {mega}evolve {0} Pokemon")
                    # Try to find the exact evolution item needed
                    # [{"type": 11, "with_item": {"item": 1106}}]
                    with_item = con.get('with_item', {}).get('item', None)
                    if with_item is not None:
                        text = _('Use {item} to {mega}evolve {0} Pokemon')
                        arr['item'] = self.items[str(with_item)]['name']
                if con.get('type', 0) == 1:
                    text = _("{mega}Evolve {0} {type}Pokemon")
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
                            arr['type'] = self.pokemon_types[pt[0]].title() + _('-type ')
                        else:
                            for ty in pt:
                                arr['type'] += (_('or ') if last == cur else '') + self.pokemon_types[ty].title() + (
                                    _('-type ') if last == cur else '-, ')
                                cur += 1
                if con.get('type', 0) == 2:
                    arr['wb'] = ""
                    arr['type'] = ""
                    arr['poke'] = ""

                    match_object = re.search(r'"pokemon_ids": \[([0-9, ]+)\]', condition)
                    if match_object is not None:
                        pt = match_object.group(1).split(', ')
                        last = len(pt)
                        cur = 1
                        if last == 1:
                            arr['poke'] = i8ln(self.pokemonname(pt[0]))
                        else:
                            for ty in pt:
                                arr['poke'] += (_('or ') if last == cur else '') + i8ln(self.pokemonname(ty)) + (
                                    '' if last == cur else ', ')
                                cur += 1
                        text = _('{mega}Evolve {0} {poke}')
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
                arr['type'] = throw_types[match_object.group(1)] + " "
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
            arr['verb'] = 'Battle'
            for con in condition_dict:
                if con.get('type', 0) == 22:
                    # PVP against team leader.
                    text = _('Battle a Team Leader {0} times')
                elif con.get('type') == 23:
                    gotta_win = con.get('with_pvp_combat', {}).get('requires_win') is True

                    if gotta_win:
                        arr['verb'] = 'Win'
                        text = _('Win a battle against another Trainer {0} times')
                    else:
                        text = _('Battle another Trainer {0} times')

                    # TODO this seems unused deprecated or just wrong
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
                elif con.get('type') == 41:
                    combat_type = con.get("with_combat_type", {}).get("combat_type", [])
                    if 6 in combat_type:
                        text = _('{verb} in the GO Battle League {0} times')
                    elif 3 in combat_type:
                        text = _('{verb} against a friend {0} times')
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
                        arr['poke'] = i8ln(self.pokemonname(pt[0]))
                    else:
                        for ty in pt:
                            arr['poke'] += (_('or ') if last == cur else '') + i8ln(self.pokemonname(ty)) + (
                                '' if last == cur else ', ')
                            cur += 1
                    text = _("Take {0} snapshots of {poke}")
            elif re.search(r'"type": 1', condition) is not None:
                # [{"type": 1, "with_pokemon_type": {"pokemon_type": [6]}}]
                text = _("Take {0} snapshots of wild {type} Pokemon")
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
                        arr['type'] = self.pokemon_types[pt[0]].title() + _('-type ')
                    else:
                        for ty in pt:
                            arr['type'] += (_('or ') if last == cur else '') + self.pokemon_types[ty].title() + (
                                _('-type ') if last == cur else '-, ')
                            cur += 1
        elif typeid == 29:
            # Team Go rucket grunt batles.
            if int(target) == int(1):
                text = _('{verb} a Team Rocket Grunt')

            arr['verb'] = _('Battle')
            for con in condition_dict:
                if con.get('type', 0) == 27:
                    rocket_cat = con.get('with_invasion_character', {}).get('category', [])
                    if 3 in rocket_cat and 4 in rocket_cat and 5 in rocket_cat:
                        text = _('{verb} {0} times against Team GO Rocket Leaders')
                if con.get('type', 0) == 18:
                    # Condition type 18 means win a battle
                    arr['verb'] = _('Defeat')
            if text == _('{verb} {0} times against Team GO Rocket Leaders'):
                if int(target) == int(1):
                    text = _('{verb} a Team GO Rocket Leader')
                else:
                    text = _('{verb} a Team GO Rocket Leader {0} times')
        elif typeid == 36:
            arr['level'] = ""
            for con in condition_dict:
                if con.get('type', 0) == 28:
                    level = con.get('with_buddy', {}).get('min_buddy_level', 0)
                    arr['level'] = buddyLevels.get(level, level)
        elif typeid == 53:
            # type 53 is to do charged attacks (any kind of way gym/pvp/rocket)
            arr['type'] = ''
            text = _('Use {0} {type} Charged Attacks')
            for con in condition_dict:
                if con.get('type', 0) == 10:
                    # Super effective
                    arr['type'] = _('supereffective')
        elif typeid == 55:
            # type 55 is to battle a challenger, which is a special type of pokestop invasion
            if int(target) == int(1):
                text = _('Battle a Challenger')

        if quest_template is not None and quest_template in self.quest_templates:
            text = _(self.quest_templates[quest_template])

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
            text = text.replace(_('PVP Battle(s)'), _('PVP Battle'))
            arr['0'] = _("a")

        for key, val in arr.items():
            text = text.replace('{' + key + '}', str(val))

        text = text.replace('  ', ' ').strip()
        return text
