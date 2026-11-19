"""peso e medidas do produto

Revision ID: d4e8a1c07b52
Revises: c7a1f4e92d30
Create Date: 2026-11-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e8a1c07b52'
down_revision = 'c7a1f4e92d30'
branch_labels = None
depends_on = None


def upgrade():
    # Colunas vazias nos produtos que já existem: o painel pede ao salvar produto para cerâmica
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('peso_gramas', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('altura_cm', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('largura_cm', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('comprimento_cm', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('comprimento_cm')
        batch_op.drop_column('largura_cm')
        batch_op.drop_column('altura_cm')
        batch_op.drop_column('peso_gramas')
