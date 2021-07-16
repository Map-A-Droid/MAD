"""Nearby scanning

Revision ID: c7ec9d7f3f8a
Revises: 415b64e87252
Create Date: 2021-07-07 16:50:39.121515

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import (BIGINT, ENUM, INTEGER, LONGBLOB,
                                       LONGTEXT, MEDIUMINT, SMALLINT, TINYINT,
                                       VARCHAR)

# revision identifiers, used by Alembic.
revision = 'c7ec9d7f3f8a'
down_revision = '415b64e87252'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pokemon', sa.Column('fort_id', sa.String(50, 'utf8mb4_unicode_ci'), default=None))
    op.add_column('pokemon', sa.Column('cell_id', BIGINT(20, unsigned=True), default=None))
    op.add_column('pokemon', sa.Column('seen_type', sa.Enum("wild", "encounter", "nearby_stop", "nearby_cell",
                                                            "lure_wild", "lure_encounter"), default=None))

    op.create_table(
        'trs_stats_detect_seen_type',
        sa.Column('encounter_id', BIGINT(20, unsigned=True), primary_key=True),
        sa.Column('encounter', sa.DateTime(), nullable=True, default=None),
        sa.Column('wild', sa.DateTime(), nullable=True, default=None),
        sa.Column('nearby_stop', sa.DateTime(), nullable=True, default=None),
        sa.Column('nearby_cell', sa.DateTime(), nullable=True, default=None),
        sa.Column('lure_encounter', sa.DateTime(), nullable=True, default=None),
        sa.Column('lure_wild', sa.DateTime(), nullable=True, default=None)
    )


def downgrade():
    op.drop_table('trs_stats_detect_seen_type')

    op.drop_column('pokemon', 'fort_id')
    op.drop_column('pokemon', 'cell_id')
    op.drop_column('pokemon', 'seen_type')
