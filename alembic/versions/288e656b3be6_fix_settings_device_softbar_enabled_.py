"""Fix settings_device.softbar_enabled default value

Revision ID: 288e656b3be6
Revises: bab9bc231ee5
Create Date: 2021-11-03 19:10:40.587355

"""
from alembic import op
from sqlalchemy import (Column, Float, ForeignKey, Index,
                        String, Table, text)

# revision identifiers, used by Alembic.
revision = '288e656b3be6'
down_revision = 'bab9bc231ee5'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('settings_device', 'softbar_enabled', server_default=text("'0'"))


def downgrade():
    pass
