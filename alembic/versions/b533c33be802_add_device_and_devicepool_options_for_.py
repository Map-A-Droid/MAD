"""Add device and devicepool options for extended login

Revision ID: b533c33be802
Revises: 73063d78ff1c
Create Date: 2024-02-10 11:36:15.733010

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'b533c33be802'
down_revision = '73063d78ff1c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('settings_device', sa.Column('extended_login', sa.BOOLEAN(),
                                               server_default=sa.text("'0'"), nullable=False))
    op.add_column('settings_devicepool', sa.Column('extended_login', sa.BOOLEAN(),
                                                   server_default=sa.text("'0'"), nullable=False))


def downgrade():
    op.drop_column('settings_device', 'extended_login')
    op.drop_column('settings_devicepool', 'extended_login')
