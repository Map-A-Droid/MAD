"""Refactor trs_visited

Revision ID: ed4770cbf39c
Revises: a2e69d3ecf7c
Create Date: 2023-03-12 12:29:19.549399

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'ed4770cbf39c'
down_revision = 'a2e69d3ecf7c'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('trs_visited', 'origin',
                    existing_type=sa.String(50, 'utf8mb4_unicode_ci'),
                    nullable=False,
                    new_column_name='username')


def downgrade():
    op.alter_column('trs_visited', 'username',
                    existing_type=sa.String(50, 'utf8mb4_unicode_ci'),
                    nullable=False,
                    new_column_name='origin')
