"""Add table 'route'

Revision ID: 258ab2aaf284
Revises: d85b527673d9
Create Date: 2023-07-31 19:48:42.492509

"""
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import (BIGINT, ENUM, INTEGER, LONGBLOB,
                                       LONGTEXT, MEDIUMINT, SMALLINT, TINYINT,
                                       VARCHAR)

from alembic import op

# revision identifiers, used by Alembic.
revision = '258ab2aaf284'
down_revision = 'd85b527673d9'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.create_table(
            'route',
            sa.Column('route_id', sa.String(50), primary_key=True),
            sa.Column('waypoints', LONGTEXT, nullable=False),
            sa.Column('type', TINYINT(2), nullable=False, server_default=sa.text("'0'")),
            sa.Column('path_type', TINYINT(2), nullable=False, server_default=sa.text("'0'")),
            sa.Column('name', sa.String(255, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('description', sa.String(255, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('version', INTEGER(11), nullable=False),
            sa.Column('reversible', sa.BOOLEAN(), server_default="0", nullable=False),
            sa.Column('submission_time', sa.DateTime(), nullable=False),
            sa.Column('route_distance_meters', INTEGER(11), nullable=False),
            sa.Column('route_duration_seconds', INTEGER(11), nullable=False),
            sa.Column('pins', LONGTEXT, nullable=False, server_default=None),
            sa.Column('tags', LONGTEXT, nullable=False),
            sa.Column('image', sa.String(255, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('image_border_color_hex', sa.String(8, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('route_submission_status', TINYINT(2), nullable=False, server_default=sa.text("'0'")),
            sa.Column('route_submission_update_time', sa.DateTime(), nullable=False),
            sa.Column('start_poi_fort_id', sa.String(50, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('start_poi_latitude', sa.Float(asdecimal=True), nullable=False),
            sa.Column('start_poi_longitude', sa.Float(asdecimal=True), nullable=False),
            sa.Column('start_poi_image_url', sa.String(255, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('end_poi_fort_id', sa.String(50, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('end_poi_latitude', sa.Float(asdecimal=True), nullable=False),
            sa.Column('end_poi_longitude', sa.Float(asdecimal=True), nullable=False),
            sa.Column('end_poi_image_url', sa.String(255, 'utf8mb4_unicode_ci'), nullable=False),
            sa.Column('last_updated', sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))
        )
    except:
        print("Failed adding pokemon_display table. Likely present already...")


def downgrade():
    try:
        op.drop_table('route')
    except:
        print("Failed dropping table route")
