"""Stats reformat

Revision ID: 4702cf22a7af
Revises: c7ec9d7f3f8a
Create Date: 2021-07-13 08:46:10.571086

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4702cf22a7af'
down_revision = 'c7ec9d7f3f8a'
branch_labels = None
depends_on = None


def upgrade():
    # Drop table trs_stats_detect_mon_raw and create a new one with PK (origin, encounter_id) as it's only used for
    # shiny stats anyways -> We can use last_seen for the time-frame or use the known despawn time of a spawn...
    # TODO: Consider data migration...
    op.drop_table('trs_stats_detect_mon_raw')
    # Drop fort_raw, useless
    op.drop_table('trs_stats_detect_fort_raw')
    # Unused since... god knows
    op.drop_table('trs_spawnsightings')
    # wild mon raw is only
    op.create_table(
        'trs_stats_detect_wild_mon_raw',
        sa.Column("worker", sa.String(128, 'utf8mb4_unicode_ci'), primary_key=True),
        sa.Column('encounter_id', sa.BIGINT(), sa.ForeignKey('pokemon.encounter_id', ondelete='CASCADE'),
                  onupdate='CASCADE',
                  primary_key=True),
        sa.Column('count', sa.INT(), nullable=False),
        sa.Column('is_shiny', sa.BOOLEAN(), server_default=False),
        sa.Column('first_scanned', sa.DateTime(), nullable=False),
        sa.Column('last_scanned', sa.DateTime(), nullable=False),
    )
    # Drop location_count as it is simply the sum of location_ok and location_nok...
    op.drop_column('trs_stats_location', 'location_count')
    # Pointless column given autoincrement - should hardly be used
    op.drop_column('trs_stats_location_raw', 'count')


def downgrade():
    op.drop_table('trs_stats_detect_wild_mon_raw')
    op.create_table(
        'trs_stats_detect_mon_raw',
        sa.Column('id', sa.INT(), primary_key=True, autoincrement=True),
        sa.Column("worker", sa.String(128, 'utf8mb4_unicode_ci'), nullable=False, index=True),
        sa.Column('encounter_id', sa.BIGINT(), nullable=False, index=True),
        sa.Column('type', sa.String(10, 'utf8mb4_unicode_ci'), nullable=False),
        sa.Column('count', sa.INT(), nullable=False),
        sa.Column('is_shiny', sa.SMALLINT(), nullable=False, index=True, server_default=0),
        sa.Column('timestamp_scan', sa.INT(), nullable=False),
    )

    op.create_table(
        'trs_stats_detect_fort_raw',
        sa.Column(sa.INTEGER(), primary_key=True),
        sa.Column(sa.String(100, 'utf8mb4_unicode_ci'), nullable=False, index=True),
        sa.Column(sa.String(50, 'utf8mb4_unicode_ci'), nullable=False, index=True),
        sa.Column(sa.String(10, 'utf8mb4_unicode_ci'), nullable=False),
        sa.Column(sa.INTEGER(), nullable=False),
        sa.Column(sa.INTEGER(), nullable=False)
    )
    op.add_column('trs_stats_location',
                  sa.Column('location_count', sa.INTEGER(), nullable=False),
                  insert_after="timestamp_scan")
