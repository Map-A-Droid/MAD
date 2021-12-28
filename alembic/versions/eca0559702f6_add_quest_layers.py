"""Add quest layers

Revision ID: eca0559702f6
Revises: 7a1290ddb6c9
Create Date: 2021-12-21 09:25:50.574990

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import (BIGINT, ENUM, INTEGER, LONGBLOB,
                                       LONGTEXT, MEDIUMINT, SMALLINT, TINYINT,
                                       VARCHAR, BOOLEAN)

# revision identifiers, used by Alembic.
revision = 'eca0559702f6'
down_revision = '7a1290ddb6c9'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('PRIMARY', 'trs_quest', type_='primary')
    op.add_column('trs_quest', sa.Column('layer', TINYINT(3), server_default=sa.text("'1'"), nullable=False,
                                         primary_key=True,
                                         autoincrement=False))
    op.create_primary_key("guid_layer_pk", "trs_quest", ["GUID", "layer", ])
    op.add_column('settings_area_pokestops', sa.Column('layer', TINYINT(3), server_default=sa.text("'1'"),
                                                       nullable=False))


def downgrade():
    # does that even work that easily?
    op.drop_column('trs_quest', 'layer')
    op.drop_column('settings_area_pokestops', 'layer')
