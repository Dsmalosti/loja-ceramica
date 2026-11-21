"""painel da Julia: destaque, ordem, foto do serviço e textos do site

Revision ID: a3c8e1f5b9d2
Revises: f2b7c9d4e810
Create Date: 2026-11-20 23:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3c8e1f5b9d2'
down_revision = 'f2b7c9d4e810'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('destaque', sa.Boolean(), server_default=sa.false(), nullable=False))
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ordem', sa.Integer(), server_default='0', nullable=False))
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.add_column(sa.Column('foto', sa.String(length=500), server_default='', nullable=False))
        batch_op.add_column(sa.Column('ordem', sa.Integer(), server_default='0', nullable=False))
    op.create_table(
        'textos_site',
        sa.Column('chave', sa.String(length=60), nullable=False),
        sa.Column('valor', sa.Text(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('chave'),
    )


def downgrade():
    op.drop_table('textos_site')
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.drop_column('ordem')
        batch_op.drop_column('foto')
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('ordem')
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('destaque')
