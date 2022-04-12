"""Add missing init_type column to settings_area_init_mitm

Revision ID: d8ceb8f31205
Revises: 6e1ff55fcde7
Create Date: 2022-04-12 08:50:08.894700

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import (ENUM)

# revision identifiers, used by Alembic.
revision = 'd8ceb8f31205'
down_revision = '6e1ff55fcde7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('settings_area_init_mitm', sa.Column('init_type', ENUM('mons', 'forts'),
                                                       nullable=False))


def downgrade():
    op.drop_column('settings_area_init_mitm', 'init_type')
