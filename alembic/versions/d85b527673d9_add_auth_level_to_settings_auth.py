"""Add auth level to settings_auth

Revision ID: d85b527673d9
Revises: a37ee4b66dd1
Create Date: 2023-04-08 21:19:54.897233

"""
import sys

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.dialects.mysql import INTEGER

from alembic import op
from mapadroid.db.model import AuthLevel

# revision identifiers, used by Alembic.
revision = 'd85b527673d9'
down_revision = 'a37ee4b66dd1'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.create_unique_constraint('unique_username', 'settings_auth', ['username'])
    except Exception as e:
        logger.error("Failed adding uniqueness constraint on settings_auth's username. "
                     "Please make sure a single username is only used once in the table.")
        logger.exception(e)
        sys.exit(1)
    op.add_column('settings_auth', sa.Column('auth_level', INTEGER(10, unsigned=True), server_default="0"))
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"""
                UPDATE settings_auth
                SET auth_level = {AuthLevel.MITM_DATA.value}
            """
        ),
    )


def downgrade():
    try:
        conn = op.get_bind()
        conn.execute(
            sa.text(
                f"""
                    ALTER TABLE settings_auth DROP INDEX unique_username
                """
            ),
        )
        op.drop_column('settings_auth', 'auth_level')
    except Exception as e:
        logger.error("Failed removing settings_auth.unique_username index or settings_auth.auth_level - "
                     "please check it manually")
