"""Add Pokemon size col

Revision ID: 0451db7421d4
Revises: 6664dd764a11
Create Date: 2023-01-12 17:07:20.053043

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0451db7421d4'
down_revision = '6664dd764a11'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pokemon', sa.Column('size', sa.SMALLINT, nullable=True))


def downgrade():
    op.drop_column('pokemon', 'size')
