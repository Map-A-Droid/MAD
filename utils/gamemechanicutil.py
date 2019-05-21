import time
from datetime import datetime, timedelta

from utils.language import open_json_file


def calculate_mon_level(cp_multiplier):
    if cp_multiplier < 0.734:
        pokemon_level = (
            58.35178527 * cp_multiplier * cp_multiplier
            - 2.838007664 * cp_multiplier
            + 0.8539209906
        )
    else:
        pokemon_level = 171.0112688 * cp_multiplier - 95.20425243
    return round(pokemon_level) * 2 / 2


def get_raid_boss_cp(mon_id):
    cp = 0

    if int(mon_id) > 0:
        pokemon_file = open_json_file("pokemon")
        cp = pokemon_file.get(str(mon_id), 0)
    return cp


def gen_despawn_timestamp(known_despawn):
    despawn_time = datetime.now() + timedelta(seconds=300)
    despawn_time = datetime.utcfromtimestamp(
        time.mktime(despawn_time.timetuple())
    ).strftime("%Y-%m-%d %H:%M:%S")

    if known_despawn is False:
        return int(time.time()) + 3 * 60

    hrmi = known_despawn.split(":")
    known_despawn = datetime.now().replace(
        hour=0, minute=int(hrmi[0]), second=int(hrmi[1]), microsecond=0
    )
    now = datetime.now()
    if now.minute <= known_despawn.minute:
        despawn = now + timedelta(
            minutes=known_despawn.minute - now.minute,
            seconds=known_despawn.second - now.second,
        )
    elif now.minute > known_despawn.minute:
        despawn = (
            now
            + timedelta(hours=1)
            - timedelta(
                minutes=(now.minute - known_despawn.minute),
                seconds=now.second - known_despawn.second,
            )
        )

    despawn_uts = int(time.mktime(despawn.timetuple()))

    return despawn_uts


def calculate_iv(ind_atk, ind_def, ind_stm):
    iv = 100.0 * (ind_atk + ind_def + ind_stm) / 45
    return iv
