"""Add keyblobs for pogoauth

Revision ID: a2e69d3ecf7c
Revises: 5d925338cee4
Create Date: 2023-03-04 10:38:41.514110

"""
import sys

import sqlalchemy as sa
from loguru import logger
from sqlalchemy import text
from sqlalchemy.dialects.mysql import (BIGINT, ENUM, INTEGER, LONGBLOB,
                                       LONGTEXT, MEDIUMBLOB, MEDIUMINT,
                                       SMALLINT, TINYINT, VARCHAR)

from alembic import op
from mapadroid.db.GeometryColumnType import GeometryColumnType

# revision identifiers, used by Alembic.
revision = 'a2e69d3ecf7c'
down_revision = '5d925338cee4'
branch_labels = None
depends_on = None


def upgrade():
    # Add unique constraint first
    try:
        op.create_unique_constraint('unique_device_id', 'settings_pogoauth', ['device_id'])
    except Exception as e:
        logger.error("Failed adding uniqueness constraint on settings_pogoauth's device_id. "
                     "Please make sure a single device is only mapped by one auth ")
        sys.exit(1)
    op.add_column('settings_pogoauth', sa.Column('key_blob', MEDIUMBLOB(), nullable=True))
    op.add_column('settings_pogoauth', sa.Column('level', sa.SMALLINT(), server_default=text("'0'"),
                                                 nullable=True))
    op.add_column('settings_pogoauth', sa.Column('last_burn', sa.DateTime(), nullable=True))
    op.add_column('settings_pogoauth', sa.Column('last_burn_type', sa.Enum("ban", "suspended", "maintenance"),
                                                 server_default=None,
                                                 nullable=True))
    op.add_column('settings_pogoauth', sa.Column('last_softban_action', sa.DateTime(), nullable=True))
    op.add_column('settings_pogoauth', sa.Column('last_softban_action_location', GeometryColumnType(), nullable=True))

    # Drop logintype from settings_device since we want to avoid this spaghetti
    op.drop_column('settings_device', 'logintype')


def downgrade():
    op.drop_constraint('unique_device_id', 'settings_pogoauth')

    op.drop_column('settings_pogoauth', 'key_blob')
    op.drop_column('settings_pogoauth', 'level')
    op.drop_column('settings_pogoauth', 'last_burn')
    op.drop_column('settings_pogoauth', 'last_burn_type')
    op.drop_column('settings_pogoauth', 'last_softban_action')
    op.drop_column('settings_pogoauth', 'last_softban_action_location')
    # TODO: migrate by reading content of settings_pogoauth for device_id and cross check to insert values
    #  for enum/ggl user
    op.add_column('settings_device', sa.Column('logintype', ENUM('google', 'ptc')))
