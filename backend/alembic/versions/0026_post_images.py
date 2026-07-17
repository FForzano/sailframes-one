"""Multiple images per post (``post_images``), replacing ``posts.image_id``.

A post can carry several images now (e.g. a flyer plus additional pages),
so the single ``image_id`` FK is replaced by a ``post_images`` join table —
mirrors ``boat_photos`` except both sides CASCADE, since a post's images
serve no purpose once the post is gone.

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0026'
down_revision: Union[str, None] = '0025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'post_images',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('post_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('image_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], name=op.f('fk_post_images_post_id_posts'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['image_id'], ['images.id'], name=op.f('fk_post_images_image_id_images'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_post_images')),
        sa.UniqueConstraint('post_id', 'image_id', name=op.f('uq_post_images_post_id_image_id')),
    )
    op.execute(
        "INSERT INTO post_images (post_id, image_id) "
        "SELECT id, image_id FROM posts WHERE image_id IS NOT NULL"
    )
    op.drop_constraint(op.f('fk_posts_image_id_images'), 'posts', type_='foreignkey')
    op.drop_column('posts', 'image_id')


def downgrade() -> None:
    op.add_column('posts', sa.Column('image_id', sa.Uuid(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f('fk_posts_image_id_images'), 'posts', 'images', ['image_id'], ['id'], ondelete='SET NULL',
    )
    op.execute(
        "UPDATE posts SET image_id = sub.image_id FROM ("
        "  SELECT DISTINCT ON (post_id) post_id, image_id FROM post_images ORDER BY post_id, id"
        ") AS sub WHERE posts.id = sub.post_id"
    )
    op.drop_table('post_images')
