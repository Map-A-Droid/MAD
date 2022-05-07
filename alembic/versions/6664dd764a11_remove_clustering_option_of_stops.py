"""Remove clustering option of stops

Revision ID: 6664dd764a11
Revises: d8ceb8f31205
Create Date: 2022-05-07 12:35:56.443050

"""
from alembic import op
from sqlalchemy import (Column, text, BOOLEAN)

# revision identifiers, used by Alembic.
revision = '6664dd764a11'
down_revision = 'd8ceb8f31205'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('settings_area_pokestops', 'enable_clustering')
    op.drop_column('settings_devicepool', 'enhanced_mode_quest')
    op.drop_column('settings_device', 'enhanced_mode_quest')


def downgrade():
    op.add_column('settings_area_pokestops', Column('enable_clustering', BOOLEAN(), server_default=text("'0'"),
                                                    nullable=False))
    op.add_column('settings_devicepool', Column('enhanced_mode_quest', BOOLEAN(), server_default=text("'0'"),
                                                nullable=False))
    op.add_column('settings_device', Column('enhanced_mode_quest', BOOLEAN(), server_default=text("'0'"),
                                            nullable=False))
