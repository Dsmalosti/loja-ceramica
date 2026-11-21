"""tentativas de acesso (limite contra robôs no login, cadastro e esqueci a senha)

Revision ID: f2b7c9d4e810
Revises: e5f9b2c3d6a1
Create Date: 2026-11-20 21:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'f2b7c9d4e810'
down_revision = 'e5f9b2c3d6a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tentativas_acesso',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chave', sa.String(length=300), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('tentativas_acesso', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tentativas_acesso_chave'), ['chave'], unique=False)
        batch_op.create_index(batch_op.f('ix_tentativas_acesso_criado_em'), ['criado_em'], unique=False)


def downgrade():
    with op.batch_alter_table('tentativas_acesso', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tentativas_acesso_criado_em'))
        batch_op.drop_index(batch_op.f('ix_tentativas_acesso_chave'))
    op.drop_table('tentativas_acesso')
