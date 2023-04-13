"""Default level 1 settings_pogoauth

Revision ID: a37ee4b66dd1
Revises: ed4770cbf39c
Create Date: 2023-03-13 05:17:57.161740

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'a37ee4b66dd1'
down_revision = 'ed4770cbf39c'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_bind() as conn:
        conn.execute(
            sa.text(
                """
                    UPDATE settings_pogoauth
                    SET level = 0
                    WHERE level is null
                """
            ),
        )
    op.alter_column('settings_pogoauth', 'level',
                    existing_type=sa.SMALLINT(),
                    server_default=str(0),
                    nullable=False)


def downgrade():
    op.alter_column('settings_pogoauth', 'level',
                    existing_type=sa.SMALLINT(),
                    server_default=sa.text("'0'"),
                    nullable=True)
