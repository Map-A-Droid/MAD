"""Tidy up indexes

Revision ID: a744c3b912ac
Revises: 4702cf22a7af
Create Date: 2021-07-22 09:01:41.687491

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a744c3b912ac'
down_revision = '4702cf22a7af'
branch_labels = None
depends_on = None


def upgrade():
    # Table trs_stats_location_raw
    # Remove count_same_events
    try:
        op.drop_index("count_same_events", table_name="trs_stats_location_raw")
    except:
        pass
    try:
        # Create indexes for columns accessed regularly
        op.create_index(index_name='trs_stats_location_raw_success', table_name='trs_stats_location_raw',
                        columns=['success'])
    except:
        pass

    try:
        op.create_index(index_name='trs_stats_location_raw_type', table_name='trs_stats_location_raw',
                        columns=['type'])
    except:
        pass

    try:
        op.create_index(index_name='trs_stats_location_raw_walker', table_name='trs_stats_location_raw',
                        columns=['walker'])
    except:
        pass

    try:
        op.create_index(index_name='trs_stats_location_raw_worker', table_name='trs_stats_location_raw',
                        columns=['worker'])
    except:
        pass

    try:
        op.create_index(index_name='trs_stats_location_raw_period', table_name='trs_stats_location_raw',
                        columns=['period'])
    except:
        pass

    # Table gym
    try:
        op.create_index(table_name='gym', index_name='gym_team_id', columns=['team_id'])
    except:
        pass

    # Table pokemon
    try:
        op.create_index(table_name='pokemon', index_name='pokemon_disappear_time', columns=['disappear_time'])
    except:
        pass
    try:
        op.create_index(table_name='pokemon', index_name='pokemon_seen_type', columns=['seen_type'])
    except:
        pass

    # Table raid
    try:
        op.create_index(table_name='raid', index_name='raid_pokemon_id', columns=['pokemon_id'])
    except:
        pass

    # Table settings_routecalc
    try:
        op.create_index(table_name='settings_routecalc', index_name='settings_routecalc_instance_id',
                        columns=['instance_id'])
    except:
        pass

    # Table trs_event
    try:
        op.create_index(table_name='trs_event', index_name='trs_event_event_start_end',
                        columns=['event_start', 'event_end'])
    except:
        pass

    # Table trs_quest
    try:
        op.create_index(table_name='trs_quest', index_name='trs_quest_quest_timestamp', columns=['quest_timestamp'])
    except:
        pass

    # Table trs_s2cells
    try:
        op.create_index(table_name='trs_s2cells', index_name='trs_s2cells_center_lat_lng',
                        columns=['center_latitude', 'center_longitude'])
    except:
        pass

    try:
        op.create_index(table_name='trs_s2cells', index_name='trs_s2cells_updated', columns=['updated'])
    except:
        pass

    # Table trs_spawn
    try:
        op.create_index(table_name='trs_spawn', index_name='trs_spawn_eventid', columns=['eventid'])
    except:
        pass
    try:
        op.create_index(table_name='trs_spawn', index_name='trs_spawn_calc_endminsec', columns=['calc_endminsec'])
    except:
        pass
    try:
        op.create_index(table_name='trs_spawn', index_name='trs_spawn_lat_lng', columns=['latitude', 'longitude'])
    except:
        pass
    try:
        op.create_index(table_name='trs_spawn', index_name='trs_spawn_last_scanned', columns=['last_scanned'])
    except:
        pass
    try:
        op.create_index(table_name='trs_spawn', index_name='trs_spawn_last_non_scanned', columns=['last_non_scanned'])
    except:
        pass

    # Table trs_stats_detect
    try:
        op.create_index(table_name='trs_stats_detect', index_name='trs_stats_detect_timestamp_scan',
                        columns=['timestamp_scan'])
    except:
        pass


    # Table trs_stats_detect_wild_mon_raw
    try:
        op.create_index(table_name='trs_stats_detect_wild_mon_raw', index_name='trs_stats_detect_wild_mon_raw_is_shiny',
                        columns=['is_shiny'])
    except:
        pass

    try:
        op.create_index(table_name='trs_stats_detect_wild_mon_raw',
                        index_name='trs_stats_detect_wild_mon_raw_last_scanned',
                        columns=['last_scanned'])
    except:
        pass

    # Table trs_stats_location
    try:
        op.create_index(table_name='trs_stats_location', index_name='trs_stats_location_timestamp_scan',
                        columns=['timestamp_scan'])
    except:
        pass

    # Table trs_usage
    try:
        op.create_index(table_name='trs_usage', index_name='trs_usage_inst_ts', columns=['instance', 'timestamp'])
    except:
        pass
    try:
        op.create_index(table_name='trs_usage', index_name='trs_usage_instance', columns=['instance'])
    except:
        pass
    try:
        op.create_index(table_name='trs_usage', index_name='trs_usage_timestamp', columns=['timestamp'])
    except:
        pass

    # Table settings_pogoauth
    try:
        op.create_index(table_name='settings_pogoauth', index_name='settings_pogoauth_login_type',
                        columns=['login_type'])
    except:
        pass


# TODO: Downgrade + set index=True in model.
def downgrade():
    op.create_index(table_name='trs_stats_location_raw', index_name='count_same_events',
                    columns=['worker', 'lat', 'lng', 'type', 'period'],
                    unique=True)
