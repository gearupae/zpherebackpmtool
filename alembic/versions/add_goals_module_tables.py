"""Add Goals module tables

Revision ID: add_goals_module_tables
Revises: f4c5250914f6
Create Date: 2025-09-14 19:41:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_goals_module_tables'
down_revision: Union[str, None] = 'f4c5250914f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create Goals table
    op.create_table('goal',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        
        # Basic Information
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        
        # Dates
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        
        # Goal Classification
        sa.Column('goal_type', sa.Enum('PERSONAL', 'TEAM', 'SALES', 'PROJECT', 'CUSTOM', name='goaltype'), nullable=False, server_default='PERSONAL'),
        sa.Column('status', sa.Enum('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'PAUSED', 'CANCELLED', 'OVERDUE', name='goalstatus'), nullable=False, server_default='NOT_STARTED'),
        sa.Column('priority', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='goalpriority'), nullable=False, server_default='MEDIUM'),
        
        # Progress Tracking
        sa.Column('target_value', sa.Float(), nullable=True, default=0),
        sa.Column('current_value', sa.Float(), nullable=True, default=0),
        sa.Column('unit', sa.String(), nullable=True),
        sa.Column('completion_percentage', sa.Float(), nullable=True, default=0.0),
        
        # Metadata
        sa.Column('created_by', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id'), nullable=True),
        sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id'), nullable=True),
        
        # Additional Configuration
        sa.Column('is_archived', sa.Boolean(), nullable=True, default=False),
        sa.Column('auto_update_progress', sa.Boolean(), nullable=True, default=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_goal_id'), 'goal', ['id'], unique=False)
    op.create_index(op.f('ix_goal_title'), 'goal', ['title'], unique=False)
    op.create_index(op.f('ix_goal_created_by'), 'goal', ['created_by'], unique=False)
    op.create_index(op.f('ix_goal_organization_id'), 'goal', ['organization_id'], unique=False)
    op.create_index(op.f('ix_goal_status'), 'goal', ['status'], unique=False)
    op.create_index(op.f('ix_goal_goal_type'), 'goal', ['goal_type'], unique=False)

    # Create Goal Members association table
    op.create_table('goal_members',
        sa.Column('goal_id', sa.String(), sa.ForeignKey('goal.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('role', sa.String(), nullable=True, default='member'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        
        sa.PrimaryKeyConstraint('goal_id', 'user_id')
    )
    op.create_index(op.f('ix_goal_members_goal_id'), 'goal_members', ['goal_id'], unique=False)
    op.create_index(op.f('ix_goal_members_user_id'), 'goal_members', ['user_id'], unique=False)

    # Create Goal Checklist table
    op.create_table('goal_checklist',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        
        sa.Column('goal_id', sa.String(), sa.ForeignKey('goal.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=True, default=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_by', sa.String(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('priority', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='checklistpriority'), nullable=False, server_default='MEDIUM'),
        sa.Column('order_index', sa.Integer(), nullable=True, default=0),
        
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_goal_checklist_id'), 'goal_checklist', ['id'], unique=False)
    op.create_index(op.f('ix_goal_checklist_goal_id'), 'goal_checklist', ['goal_id'], unique=False)
    op.create_index(op.f('ix_goal_checklist_order_index'), 'goal_checklist', ['order_index'], unique=False)

    # Create Goal Progress table
    op.create_table('goal_progress',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        
        sa.Column('goal_id', sa.String(), sa.ForeignKey('goal.id', ondelete='CASCADE'), nullable=False),
        sa.Column('previous_value', sa.Float(), nullable=True, default=0),
        sa.Column('new_value', sa.Float(), nullable=True, default=0),
        sa.Column('change_amount', sa.Float(), nullable=True, default=0),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        
        # Automatic tracking fields
        sa.Column('source', sa.String(), nullable=True),  # manual, automatic, integration
        sa.Column('reference_id', sa.String(), nullable=True),  # ID from external system if auto-updated
        
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_goal_progress_id'), 'goal_progress', ['id'], unique=False)
    op.create_index(op.f('ix_goal_progress_goal_id'), 'goal_progress', ['goal_id'], unique=False)
    op.create_index(op.f('ix_goal_progress_created_at'), 'goal_progress', ['created_at'], unique=False)

    # Create Goal Reminder table
    op.create_table('goal_reminder',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        
        sa.Column('goal_id', sa.String(), sa.ForeignKey('goal.id', ondelete='CASCADE'), nullable=False),
        sa.Column('interval', sa.Enum('DAILY', 'WEEKLY', 'BIWEEKLY', 'MONTHLY', 'CUSTOM', name='reminderinterval'), nullable=False, server_default='WEEKLY'),
        sa.Column('custom_interval_days', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_reminder_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reminder_message', sa.Text(), nullable=True),
        
        # Notification preferences
        sa.Column('send_email', sa.Boolean(), nullable=True, default=True),
        sa.Column('send_in_app', sa.Boolean(), nullable=True, default=True),
        sa.Column('send_to_members', sa.Boolean(), nullable=True, default=True),
        
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_goal_reminder_id'), 'goal_reminder', ['id'], unique=False)
    op.create_index(op.f('ix_goal_reminder_goal_id'), 'goal_reminder', ['goal_id'], unique=False)
    op.create_index(op.f('ix_goal_reminder_next_reminder_at'), 'goal_reminder', ['next_reminder_at'], unique=False)
    op.create_index(op.f('ix_goal_reminder_is_active'), 'goal_reminder', ['is_active'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order to handle foreign key constraints
    op.drop_table('goal_reminder')
    op.drop_table('goal_progress')
    op.drop_table('goal_checklist')
    op.drop_table('goal_members')
    op.drop_table('goal')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS goaltype CASCADE')
    op.execute('DROP TYPE IF EXISTS goalstatus CASCADE')
    op.execute('DROP TYPE IF EXISTS goalpriority CASCADE')
    op.execute('DROP TYPE IF EXISTS checklistpriority CASCADE')
    op.execute('DROP TYPE IF EXISTS reminderinterval CASCADE')
