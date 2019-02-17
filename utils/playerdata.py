import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class PlayerData(object):
    def __init__(self, name):
        self._name = name

    def set_name(self, name):
        log.info('Set name %s' % (str(name)))
        self._name = str(name)
        return True

    def get_name(self):
        return self._name

    def _gen_player_data(self, data):
        if 'username' not in data:
            log.debug('{{gen_player_data}} cannot generate new playerdata')
            return True

        username = data['username']

        if len(username) > 0:
            self.set_name(str(username))

            newdata = {}
            newdata[self._name] = []
            newdata[self._name].append({
                'creation_timestamp_ms': str(data['creation_timestamp_ms']),
                'username': str(data['username']),
                'team': str(data['team']),
                'tutorial_state': str(data['tutorial_state']),
                'avatar': str(data['avatar']),
                'max_pokemon_storage': str(data['max_pokemon_storage']),
                'max_item_storage': str(data['max_item_storage']),
                'daily_bonus': str(data['daily_bonus']),
                'equipped_badge': str(data['equipped_badge']),
                'contact_settings': str(data['contact_settings']),
                'currency_balance': str(data['currency_balance']),
                'remaining_codename_claims': str(data['remaining_codename_claims']),
                'buddy_pokemon': str(data['buddy_pokemon']),
                'battle_lockout_end_ms': str(data['battle_lockout_end_ms']),
                'secondary_player_avatar': str(data['secondary_player_avatar']),
                'name_is_blacklisted': str(data['name_is_blacklisted']),
                'social_player_settings': str(data['social_player_settings']),
                'combat_player_preferences': str(data['combat_player_preferences']),
                'player_support_id': str(data['player_support_id'])
            })

            with open(self._name + '.playerdata', 'w') as outfile:
                json.dump(newdata, outfile, indent=4, sort_keys=True)

    def _open_player_data(self):
        name = Path(str(self._name) + '.playerdata')
        if not name.is_file():
            log.error('[%s] - no PlayerData found' % (str(self._name)))
            self.set_name(0)
            return False

        with open(str(self._name) + '.playerdata') as f:
            data = json.load(f)

        self.set_name(data[self._name][0]['username'])

