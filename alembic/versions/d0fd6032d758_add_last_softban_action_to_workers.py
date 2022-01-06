"""Add last softban action to workers

Revision ID: d0fd6032d758
Revises: eca0559702f6
Create Date: 2022-01-06 11:10:07.881477

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from mapadroid.db.GeometryColumnType import GeometryColumnType

revision = 'd0fd6032d758'
down_revision = 'eca0559702f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('trs_status', sa.Column('last_softban_action', sa.DateTime(), nullable=True))
    op.add_column('trs_status', sa.Column('last_softban_action_location', GeometryColumnType(), nullable=True))


def downgrade():
    op.drop_column('trs_status', 'last_softban_action')
    op.drop_column('trs_status', 'last_softban_action_location')
