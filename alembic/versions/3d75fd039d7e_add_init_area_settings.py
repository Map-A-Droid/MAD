"""Add init area settings

Revision ID: 3d75fd039d7e
Revises: 3d16f94ed34a
Create Date: 2022-03-21 07:59:31.504866

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import (BIGINT, ENUM, INTEGER, LONGBLOB,
                                       LONGTEXT, MEDIUMINT, SMALLINT, TINYINT,
                                       VARCHAR)

# revision identifiers, used by Alembic.
revision = '3d75fd039d7e'
down_revision = '3d16f94ed34a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'settings_area_init_mitm',
        sa.Column('area_id', INTEGER(10, unsigned=True),
                  sa.ForeignKey('settings_area.area_id', ondelete='CASCADE'),
                  primary_key=True,
                  autoincrement=True),
        sa.Column('geofence_included', INTEGER(10, unsigned=True),
                  sa.ForeignKey('settings_geofence.geofence_id'), nullable=False, index=True),
        sa.Column('geofence_excluded', sa.String(256, 'utf8mb4_unicode_ci')),
        sa.Column('routecalc', INTEGER(10, unsigned=True),
                  sa.ForeignKey('settings_routecalc.routecalc_id'), nullable=False, index=True),
        sa.Column('init_mode_rounds', INTEGER(11, unsigned=True)),
        sa.Column('monlist_id', INTEGER(10, unsigned=True),
                  sa.ForeignKey('settings_monivlist.monlist_id'), index=True),
        sa.Column('all_mons', sa.BOOLEAN, nullable=False, server_default=sa.text("'0'")),
        sa.Column('speed', sa.Float),
        sa.Column('max_distance', sa.Float),
    )

    # Remove init related parameters from other settings_area
    op.drop_column('settings_area_raids_mitm', 'init_mode_rounds')
    op.drop_column('settings_area_raids_mitm', 'init')
    op.drop_column('settings_area_pokestops', 'init')
    op.drop_column('settings_area_mon_mitm', 'init')
    op.drop_column('settings_area_mon_mitm', 'init_mode_rounds')
    op.drop_column('trs_status', 'init')


def downgrade():
    pass
