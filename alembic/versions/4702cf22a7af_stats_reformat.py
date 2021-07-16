"""Stats reformat

Revision ID: 4702cf22a7af
Revises: c7ec9d7f3f8a
Create Date: 2021-07-13 08:46:10.571086

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import (BIGINT, ENUM, INTEGER, LONGBLOB,
                                       LONGTEXT, MEDIUMINT, SMALLINT, TINYINT,
                                       VARCHAR)

# revision identifiers, used by Alembic.
revision = '4702cf22a7af'
down_revision = 'c7ec9d7f3f8a'
branch_labels = None
depends_on = None


def upgrade():
    # Drop table trs_stats_detect_mon_raw and create a new one with PK (origin, encounter_id) as it's only used for
    # shiny stats anyways -> We can use last_seen for the time-frame or use the known despawn time of a spawn...
    # TODO: Consider data migration...
    try:
        op.drop_table('trs_stats_detect_mon_raw')
    except Exception as e:
        print("Failed deleting trs_stats_detect_mon_raw")
    # Drop fort_raw, useless
    try:
        op.drop_table('trs_stats_detect_fort_raw')
    except Exception as e:
        print("Failed deleting trs_stats_detect_fort_raw")
    # Unused since... god knows
    try:
        op.drop_table('trs_spawnsightings')
    except Exception as e:
        print("Failed deleting trs_spawnsightings")

    try:
        op.create_table(
            'trs_stats_detect_wild_mon_raw',
            sa.Column("worker", sa.String(128, 'utf8mb4_unicode_ci'), primary_key=True),
            sa.Column('encounter_id', BIGINT(20, unsigned=True), sa.ForeignKey('pokemon.encounter_id', ondelete='CASCADE',
                                                                               onupdate='CASCADE'),
                      primary_key=True),
            sa.Column('count', sa.INT(), nullable=False),
            sa.Column('is_shiny', sa.BOOLEAN(), server_default="0", index=True, nullable=False),
            sa.Column('first_scanned', sa.DateTime(), nullable=False),
            sa.Column('last_scanned', sa.DateTime(), nullable=False),
        )
    except Exception as e:
        print(e)

    try:
        # Drop location_count as it is simply the sum of location_ok and location_nok...
        op.drop_column('trs_stats_location', 'location_count')
    except Exception as e:
        print(e)

    # Pointless column given autoincrement - should hardly be used
    try:
        op.drop_column('trs_stats_location_raw', 'count')
    except Exception as e:
        print(e)


def downgrade():
    try:
        op.drop_table('trs_stats_detect_wild_mon_raw')
    except Exception as e:
        print("Failed dropping table trs_stats_detect_wild_mon_raw")
    try:
        op.create_table(
            'trs_stats_detect_mon_raw',
            sa.Column('id', sa.INT(), primary_key=True, autoincrement=True),
            sa.Column('worker', sa.String(128, 'utf8mb4_unicode_ci'), nullable=False, index=True),
            sa.Column('encounter_id', sa.BIGINT(), nullable=False, index=True),
            sa.Column('type', sa.String(10, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('count', sa.INT(), nullable=False),
            sa.Column('is_shiny', sa.SMALLINT(), nullable=False, index=True, server_default='0'),
            sa.Column('timestamp_scan', sa.INT(), nullable=False, index=True),
        )
        op.create_index('worker', 'trs_stats_detect_mon_raw', ['worker'])
        op.create_index('encounter_id', 'trs_stats_detect_mon_raw', ['encounter_id'])
        op.create_index('is_shiny', 'trs_stats_detect_mon_raw', ['is_shiny'])
        op.create_index('timestamp_scan', 'trs_stats_detect_mon_raw', ['timestamp_scan'])
    except Exception as e:
        print("Failed creating table trs_stats_detect_mon_raw")

    try:
        op.create_table(
            'trs_stats_detect_fort_raw',
            sa.Column('id', sa.INTEGER(), primary_key=True, autoincrement=True),
            sa.Column('worker', sa.String(100, 'utf8mb4_unicode_ci'), nullable=False, index=True),
            sa.Column('guid', sa.String(50, 'utf8mb4_unicode_ci'), nullable=False, index=True),
            sa.Column('type', sa.String(10, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('count', sa.INTEGER(), nullable=False),
            sa.Column('timestamp_scan', sa.INTEGER(), nullable=False)
        )
        op.create_index('worker', 'trs_stats_detect_fort_raw', ['worker'])
        op.create_index('guid', 'trs_stats_detect_fort_raw', ['guid'])
    except Exception as e:
        print("Failed creating table trs_stats_detect_fort_raw")

    try:
        op.create_table(
            'trs_spawnsightings',
            sa.Column('id', sa.INTEGER(), primary_key=True, autoincrement=True),
            sa.Column('encounter_id', sa.BIGINT(), nullable=False),
            sa.Column('spawnpoint_id', sa.BIGINT(), nullable=False, index=True),
            sa.Column('scan_time', sa.DATETIME(), nullable=False),
            sa.Column('tth_secs', sa.INTEGER(), nullable=False)
        )
        op.create_index('trs_spawnpointdd_spawnpoint_id', 'trs_spawnsightings', ['spawnpoint_id'])
    except Exception as e:
        print("Failed creating table trs_spawnsightings")

    try:
        op.add_column('trs_stats_location',
                      sa.Column('location_count', sa.INTEGER(), nullable=False))
    except Exception as e:
        print("Failed adding column to table trs_stats_location")

    try:
        op.add_column('trs_stats_location_raw',
                      sa.Column('count', sa.INTEGER(), nullable=False))
    except Exception as e:
        print("Failed adding column to table trs_stats_location")
