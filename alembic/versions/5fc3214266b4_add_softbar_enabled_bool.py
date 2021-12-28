"""Add softbar enabled bool

Revision ID: 5fc3214266b4
Revises: fb3e82019b14
Create Date: 2021-08-22 08:50:24.041540

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import (Column, Float, ForeignKey, Index,
                        String, Table, text)

# revision identifiers, used by Alembic.
revision = '5fc3214266b4'
down_revision = 'fb3e82019b14'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('settings_device', sa.Column('softbar_enabled', sa.BOOLEAN(), server_default=text("'0'"), nullable=False))


def downgrade():
    op.drop_column('settings_device', 'softbar_enabled')
