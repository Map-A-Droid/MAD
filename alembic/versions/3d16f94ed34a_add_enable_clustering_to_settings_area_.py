"""Add enable_clustering to settings_area_pokestops

Revision ID: 3d16f94ed34a
Revises: d0fd6032d758
Create Date: 2022-01-10 09:38:39.443745

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3d16f94ed34a'
down_revision = 'd0fd6032d758'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('settings_area_pokestops', sa.Column('enable_clustering', sa.BOOLEAN(), server_default=sa.text("'0'"),
                                                       nullable=False))


def downgrade():
    op.drop_column('settings_area_pokestops', 'enable_clustering')
