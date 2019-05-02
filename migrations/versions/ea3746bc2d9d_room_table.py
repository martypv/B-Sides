"""room_table

Revision ID: ea3746bc2d9d
Revises: 
Create Date: 2019-05-01 17:10:48.633180

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ea3746bc2d9d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('room',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('room_name', sa.String(length=64), nullable=True),
    sa.Column('room_code', sa.String(length=64), nullable=True),
    sa.Column('vote_a', sa.Integer(), nullable=True),
    sa.Column('vote_b', sa.Integer(), nullable=True),
    sa.Column('vote_open', sa.BOOLEAN(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_room_room_code'), 'room', ['room_code'], unique=False)
    op.create_index(op.f('ix_room_room_name'), 'room', ['room_name'], unique=False)
    op.create_index(op.f('ix_room_vote_a'), 'room', ['vote_a'], unique=False)
    op.create_index(op.f('ix_room_vote_b'), 'room', ['vote_b'], unique=False)
    op.create_index(op.f('ix_room_vote_open'), 'room', ['vote_open'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_room_vote_open'), table_name='room')
    op.drop_index(op.f('ix_room_vote_b'), table_name='room')
    op.drop_index(op.f('ix_room_vote_a'), table_name='room')
    op.drop_index(op.f('ix_room_room_name'), table_name='room')
    op.drop_index(op.f('ix_room_room_code'), table_name='room')
    op.drop_table('room')
    # ### end Alembic commands ###