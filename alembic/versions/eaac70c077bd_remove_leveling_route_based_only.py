"""Remove leveling route based only

Revision ID: eaac70c077bd
Revises: 3d75fd039d7e
Create Date: 2022-04-07 21:48:03.145019

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import (ENUM)

# revision identifiers, used by Alembic.
revision = 'eaac70c077bd'
down_revision = '3d75fd039d7e'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('settings_area_pokestops', 'route_calc_algorithm')


def downgrade():
    op.add_column('settings_area_pokestops',
                  sa.Column('route_calc_algorithm', ENUM('route', 'routefree')))
