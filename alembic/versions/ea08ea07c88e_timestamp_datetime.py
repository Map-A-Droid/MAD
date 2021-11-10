"""TIMESTAMP -> datetime

Revision ID: ea08ea07c88e
Revises: 288e656b3be6
Create Date: 2021-11-10 20:18:36.301632

"""
from alembic import op
from sqlalchemy.dialects.mysql import (BIGINT, ENUM, INTEGER, LONGBLOB,
                                       LONGTEXT, MEDIUMINT, SMALLINT, TINYINT,
                                       VARCHAR, DATETIME, TIMESTAMP)


# revision identifiers, used by Alembic.
revision = 'ea08ea07c88e'
down_revision = '288e656b3be6'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('trs_status', 'lastProtoDateTime', type_=DATETIME)
    op.alter_column('trs_status', 'lastPogoRestart', type_=DATETIME)
    op.alter_column('trs_status', 'lastPogoReboot', type_=DATETIME)


def downgrade():
    op.alter_column('trs_status', 'lastProtoDateTime', type_=TIMESTAMP)
    op.alter_column('trs_status', 'lastPogoRestart', type_=TIMESTAMP)
    op.alter_column('trs_status', 'lastPogoReboot', type_=TIMESTAMP)

