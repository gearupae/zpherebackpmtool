"""
Alembic migration: add focus_blocks table

Note: This migration targets the current (active) database. In production with per-tenant DBs,
run migrations per-tenant or ensure creation via app.db.database.init_db which calls Base.metadata.create_all.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_focus_blocks_table'
down_revision = 'f4c5250914f6'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'focus_blocks',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='UTC'),
        sa.Column('reason', sa.Text()),
        sa.Column('created_by_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
    )


def downgrade() -> None:
    op.drop_table('focus_blocks')

