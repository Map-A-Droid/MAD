"""Increase quest_condition length

Revision ID: 5d925338cee4
Revises: 830757363f4b
Create Date: 2023-02-25 15:17:29.959367

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '5d925338cee4'
down_revision = '830757363f4b'
branch_labels = None
depends_on = None


def upgrade():
    # sa.Column("worker", sa.String(128, 'utf8mb4_unicode_ci'), primary_key=True),
    #     quest_condition = Column(String(500, 'utf8mb4_unicode_ci')) to 2500 in size
    op.alter_column('trs_quest', 'quest_condition',
                    existing_type=sa.String(length=500, collation='utf8mb4_unicode_ci'),
                    type_=sa.String(length=2500, collation='utf8mb4_unicode_ci'),
                    existing_nullable=True)


def downgrade():
    op.alter_column('trs_quest', 'quest_condition',
                    existing_type=sa.String(length=2500, collation='utf8mb4_unicode_ci'),
                    type_=sa.String(length=500, collation='utf8mb4_unicode_ci'),
                    existing_nullable=True)
