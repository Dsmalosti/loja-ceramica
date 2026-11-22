"""frete do Melhor Envio: serviço e prazo no pedido

Revision ID: c1d9e4a7f3b6
Revises: a3c8e1f5b9d2
Create Date: 2026-11-21 10:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d9e4a7f3b6'
down_revision = 'a3c8e1f5b9d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pedidos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('frete_servico', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('frete_prazo_dias', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('pedidos', schema=None) as batch_op:
        batch_op.drop_column('frete_prazo_dias')
        batch_op.drop_column('frete_servico')
