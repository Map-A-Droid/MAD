"""Add quest title column

Revision ID: 867783e63a90
Revises: 5fc3214266b4
Create Date: 2021-10-16 16:23:50.841025

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '867783e63a90'
down_revision = '5fc3214266b4'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('trs_quest', sa.Column('quest_title', sa.String(100, 'utf8mb4_unicode_ci'), server_default=None,
                                             nullable=True))
    except Exception as e:
        print("Failed adding column quest_title to trs_quest. Likely was placed there beforehand (master branch)")


def downgrade():
    try:
        op.drop_column('trs_quest', 'quest_title')
    except Exception as e:
        print("Failed dropping column quest_title of trs_quest.")

