"""Add pokestop_incident Table

Revision ID: 830757363f4b
Revises: 6664dd764a11
Create Date: 2023-01-10 13:27:48.628229

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import (BIGINT, ENUM, INTEGER, LONGBLOB,
                                       LONGTEXT, MEDIUMINT, SMALLINT, TINYINT,
                                       VARCHAR)

# revision identifiers, used by Alembic.
revision = '830757363f4b'
down_revision = '0451db7421d4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pokestop_incident',
        sa.Column('pokestop_id', sa.String(50, 'utf8mb4_unicode_ci'),
                  sa.ForeignKey('pokestop.pokestop_id', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('incident_id', sa.String(50, 'utf8mb4_unicode_ci'),
                  nullable=False, unique=True, index=True, primary_key=True),
        sa.Column('incident_start', sa.DateTime(), nullable=False),
        sa.Column('incident_expiration', sa.DateTime(), nullable=False, index=True),
        sa.Column('hide_incident', sa.BOOLEAN, nullable=False, server_default=sa.text("'0'")),
        sa.Column('incident_display_type', SMALLINT(3), server_default=None, nullable=True),
        sa.Column('incident_display_order_priority', INTEGER(11), server_default=None, nullable=True),
        sa.Column('custom_display', sa.String(50, 'utf8mb4_unicode_ci'), server_default=None, nullable=True),
        sa.Column('is_cross_stop_incident', sa.BOOLEAN, nullable=False, server_default=sa.text("'0'")),
        sa.Column('character_display', SMALLINT(4), server_default=None, nullable=True),
    )

    op.drop_column('pokestop', 'incident_start')
    op.drop_column('pokestop', 'incident_expiration')
    op.drop_column('pokestop', 'incident_grunt_type')


def downgrade():
    op.drop_table("pokestop_incident")
    op.add_column("pokestop", sa.Column('incident_start',
                                        sa.DateTime(), server_default=None,
                                        nullable=True))
    op.add_column("pokestop", sa.Column('incident_expiration',
                                        sa.DateTime(), server_default=None,
                                        nullable=True))
    op.add_column("pokestop", sa.Column('incident_grunt_type',
                                        SMALLINT(1), server_default=None,
                                        nullable=True))
