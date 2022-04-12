"""Add init enum value to settings_area.mode

Revision ID: 6e1ff55fcde7
Revises: eaac70c077bd
Create Date: 2022-04-12 08:37:23.090143

"""
from alembic import op
from sqlalchemy.dialects.mysql import (ENUM)

# revision identifiers, used by Alembic.
revision = '6e1ff55fcde7'
down_revision = 'eaac70c077bd'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("settings_area", "mode", existing_type=ENUM('idle', 'iv_mitm', 'mon_mitm', 'pokestops',
                                                                'raids_mitm'),
                    type_=ENUM('idle', 'iv_mitm', 'mon_mitm', 'pokestops', 'raids_mitm', 'init'))


def downgrade():
    op.alter_column("settings_area", "mode", existing_type=ENUM('idle', 'iv_mitm', 'mon_mitm', 'pokestops',
                                                                'raids_mitm', 'init'),
                    type_=ENUM('idle', 'iv_mitm', 'mon_mitm', 'pokestops', 'raids_mitm'))
