"""enable encounters in quest mode

Revision ID: f5173474bad6
Revises: 288e656b3be6
Create Date: 2021-11-10 20:41:19.051158

"""
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

# revision identifiers, used by Alembic.
revision = 'f5173474bad6'
down_revision = '288e656b3be6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("settings_area_pokestops", sa.Column("all_mons", mysql.TINYINT(1), nullable=False,
                                                       server_default=sa.text("'0'")))
    op.add_column("settings_area_pokestops", sa.Column("monlist_id", mysql.INTEGER(unsigned=True),
                                                       sa.ForeignKey('settings_monivlist.monlist_id',
                                                                     name="fk_ap_monid"),
                                                       nullable=True, index=True))
    pass


def downgrade():
    try:
        op.drop_constraint("fk_ap_monid", "settings_area_pokestops", type_='foreignkey')
        op.drop_column("settings_area_pokestops", "all_mons")
        op.drop_column("settings_area_pokestops", "monlist_id")
        pass
    except Exception as e:
        print(e)
