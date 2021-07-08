"""Remove inventory_clear_item_amount_tap_duration

Revision ID: 415b64e87252
Revises: 
Create Date: 2021-07-06 18:04:30.271269

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '415b64e87252'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.drop_column('settings_devicepool', 'inventory_clear_item_amount_tap_duration')
    except Exception as e:
        print(e)


def downgrade():
    try:
        op.add_column('settings_devicepool', sa.Column('inventory_clear_item_amount_tap_duration', sa.Integer,
                                                       default=None))
    except Exception as e:
        print(e)