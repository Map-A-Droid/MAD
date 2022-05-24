"""Add constraint on pokemon_display.encounter_id

Revision ID: bab9bc231ee5
Revises: 29caa9552405
Create Date: 2021-10-19 17:55:29.641940

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bab9bc231ee5'
down_revision = '29caa9552405'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    DELETE FROM pokemon_display
    WHERE encounter_id NOT IN (SELECT p.encounter_id 
                        FROM pokemon p)
    """)
    op.create_foreign_key(constraint_name="pokemon_encounter_id_casc", source_table="pokemon_display",
                          referent_table="pokemon",
                          local_cols=["encounter_id"], remote_cols=["encounter_id"], ondelete="CASCADE")


def downgrade():
    try:
        op.drop_constraint('pokemon_encounter_id_casc', 'trs_stats_detect_wild_mon_raw', type_='foreignkey')
    except Exception as e:
        print("Safe to ignore: Failed to drop constraint. It may have not been added before.")

