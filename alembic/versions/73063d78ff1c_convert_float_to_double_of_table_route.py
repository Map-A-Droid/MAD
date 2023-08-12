"""Convert FLOAT to DOUBLE of table route

Revision ID: 73063d78ff1c
Revises: 258ab2aaf284
Create Date: 2023-08-12 08:20:45.607223

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '73063d78ff1c'
down_revision = '258ab2aaf284'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('route', 'start_poi_latitude',
                    existing_type=sa.Float(asdecimal=True),
                    type_=sa.Double(asdecimal=True),
                    existing_nullable=True)
    op.alter_column('route', 'start_poi_longitude',
                    existing_type=sa.Float(asdecimal=True),
                    type_=sa.Double(asdecimal=True),
                    existing_nullable=True)
    op.alter_column('route', 'end_poi_latitude',
                    existing_type=sa.Float(asdecimal=True),
                    type_=sa.Double(asdecimal=True),
                    existing_nullable=True)
    op.alter_column('route', 'end_poi_longitude',
                    existing_type=sa.Float(asdecimal=True),
                    type_=sa.Double(asdecimal=True),
                    existing_nullable=True)


def downgrade():
    op.alter_column('route', 'start_poi_latitude',
                    existing_type=sa.Double(asdecimal=True),
                    type_=sa.Float(asdecimal=True),
                    existing_nullable=True)
    op.alter_column('route', 'start_poi_longitude',
                    existing_type=sa.Double(asdecimal=True),
                    type_=sa.Float(asdecimal=True),
                    existing_nullable=True)
    op.alter_column('route', 'end_poi_latitude',
                    existing_type=sa.Double(asdecimal=True),
                    type_=sa.Float(asdecimal=True),
                    existing_nullable=True)
    op.alter_column('route', 'end_poi_longitude',
                    existing_type=sa.Double(asdecimal=True),
                    type_=sa.Float(asdecimal=True),
                    existing_nullable=True)
