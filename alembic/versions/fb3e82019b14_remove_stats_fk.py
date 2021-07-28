"""Remove stats fk

Revision ID: fb3e82019b14
Revises: a744c3b912ac
Create Date: 2021-07-28 13:58:05.075757

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fb3e82019b14'
down_revision = 'a744c3b912ac'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.drop_constraint(u'trs_stats_detect_wild_mon_raw_ibfk_1', 'trs_stats_detect_wild_mon_raw', type_='foreignkey')
    except Exception as e:
        print("Safe to ignore: Failed to drop constraint. It may have not been added before.")


def downgrade():
    # We do not add it back in. It is just causing issues...
    pass
