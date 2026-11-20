"""cursos completos: turma, professor e fotos

Revision ID: e5f9b2c3d6a1
Revises: d4e8a1c07b52
Create Date: 2026-11-19 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f9b2c3d6a1'
down_revision = 'd4e8a1c07b52'
branch_labels = None
depends_on = None


def upgrade():
    # Cursos que já existem ficam com turma aberta e sem professor
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('turma_aberta', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('professor_nome', sa.String(length=120), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('professor_instagram', sa.String(length=30), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('professor_foto', sa.String(length=500), nullable=False, server_default=''))

    op.create_table('course_images',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('curso_id', sa.Integer(), nullable=False),
    sa.Column('caminho', sa.String(length=500), nullable=False),
    sa.Column('alt', sa.String(length=200), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['curso_id'], ['courses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('course_images', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_course_images_curso_id'), ['curso_id'], unique=False)


def downgrade():
    with op.batch_alter_table('course_images', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_course_images_curso_id'))
    op.drop_table('course_images')

    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('professor_foto')
        batch_op.drop_column('professor_instagram')
        batch_op.drop_column('professor_nome')
        batch_op.drop_column('turma_aberta')
