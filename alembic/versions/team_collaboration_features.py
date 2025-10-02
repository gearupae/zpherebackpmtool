"""Add team collaboration features

Revision ID: team_collaboration_001
Revises: add_enhanced_subscription_and_dunning_management
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'team_collaboration_001'
down_revision = 'f4c5250914f6'
branch_labels = None
depends_on = None


def upgrade():
    # Create Permission enum
    permission_enum = postgresql.ENUM(
        'create_project', 'edit_project', 'delete_project', 'view_project',
        'create_task', 'edit_task', 'delete_task', 'assign_task', 'view_task',
        'invite_member', 'remove_member', 'manage_roles', 'view_members',
        'upload_file', 'delete_file', 'view_file',
        'create_comment', 'edit_comment', 'delete_comment',
        'view_analytics', 'view_reports',
        name='permission'
    )
    permission_enum.create(op.get_bind())

    # Create user_role_permissions table
    op.create_table('user_role_permissions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('permission', permission_enum, nullable=False),
        sa.Column('granted_by_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['granted_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_role_permissions_id'), 'user_role_permissions', ['id'], unique=False)

    # Create teams table
    op.create_table('teams',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_teams_id'), 'teams', ['id'], unique=False)

    # Create team_members table
    op.create_table('team_members',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('team_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_team_members_id'), 'team_members', ['id'], unique=False)

    # Create task_watchers table
    op.create_table('task_watchers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('task_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('notify_on_comment', sa.Boolean(), nullable=True),
        sa.Column('notify_on_status_change', sa.Boolean(), nullable=True),
        sa.Column('notify_on_assignment', sa.Boolean(), nullable=True),
        sa.Column('notify_on_due_date', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_task_watchers_id'), 'task_watchers', ['id'], unique=False)


def downgrade():
    # Drop tables
    op.drop_index(op.f('ix_task_watchers_id'), table_name='task_watchers')
    op.drop_table('task_watchers')
    
    op.drop_index(op.f('ix_team_members_id'), table_name='team_members')
    op.drop_table('team_members')
    
    op.drop_index(op.f('ix_teams_id'), table_name='teams')
    op.drop_table('teams')
    
    op.drop_index(op.f('ix_user_role_permissions_id'), table_name='user_role_permissions')
    op.drop_table('user_role_permissions')
    
    # Drop enum
    permission_enum = postgresql.ENUM(name='permission')
    permission_enum.drop(op.get_bind())
