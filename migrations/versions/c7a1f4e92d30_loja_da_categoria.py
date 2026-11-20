"""loja da categoria

Revision ID: c7a1f4e92d30
Revises: b18d76d814ab
Create Date: 2026-11-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7a1f4e92d30'
down_revision = 'b18d76d814ab'
branch_labels = None
depends_on = None


def upgrade():
    # Categorias que já existem são de peças: era o único tipo vendido até aqui
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('loja', sa.String(length=20), nullable=False, server_default='pecas'))
        batch_op.create_check_constraint('ck_categories_loja', "loja IN ('pecas', 'produtos')")


def downgrade():
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_constraint('ck_categories_loja', type_='check')
        batch_op.drop_column('loja')
