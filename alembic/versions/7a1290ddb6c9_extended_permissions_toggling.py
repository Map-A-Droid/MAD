"""Extended permissions toggling

Revision ID: 7a1290ddb6c9
Revises: ea08ea07c88e
Create Date: 2021-12-13 08:32:30.507261

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import (Column, Float, ForeignKey, Index,
                        String, Table, text)


# revision identifiers, used by Alembic.
revision = '7a1290ddb6c9'
down_revision = 'ea08ea07c88e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('settings_device', sa.Column('extended_permission_toggling', sa.BOOLEAN(), server_default=text("'0'"),
                                               nullable=False))


def downgrade():
    op.drop_column('settings_device', 'extended_permission_toggling')
