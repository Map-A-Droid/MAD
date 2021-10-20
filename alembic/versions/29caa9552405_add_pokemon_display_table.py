"""Add pokemon_display table

Revision ID: 29caa9552405
Revises: 867783e63a90
Create Date: 2021-10-18 09:57:04.069330

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import (BIGINT, ENUM, INTEGER, LONGBLOB,
                                       LONGTEXT, MEDIUMINT, SMALLINT, TINYINT,
                                       VARCHAR)

# revision identifiers, used by Alembic.
revision = '29caa9552405'
down_revision = '867783e63a90'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.create_table(
            'pokemon_display',
            sa.Column('encounter_id', BIGINT(20, unsigned=True), primary_key=True),
            sa.Column('pokemon', SMALLINT(6), nullable=False, index=True),
            sa.Column('gender', SMALLINT(6), server_default=None, nullable=True),
            sa.Column('form', SMALLINT(6), server_default=None, nullable=True),
            sa.Column('costume', SMALLINT(6), server_default=None, nullable=True),
        )
    except:
        print("Failed adding pokemon_display table. Likely present already...")


def downgrade():
    try:
        op.drop_table('pokemon_display')
    except:
        print("Failed dropping table pokemon_display")
