"""create module tables

Revision ID: module_tables_001
Revises: 6252189c402e
Create Date: 2025-08-22 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'module_tables_001'
down_revision = '6252189c402e'
branch_labels = None
depends_on = None


def upgrade():
    # Create modules table
    op.create_table('modules',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('price_per_month', sa.Float(), nullable=False),
    sa.Column('is_core', sa.Boolean(), nullable=True),
    sa.Column('is_available', sa.Boolean(), nullable=True),
    sa.Column('features', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    # Create tenant_modules table
    op.create_table('tenant_modules',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('tenant_id', sa.String(), nullable=False),
    sa.Column('module_id', sa.String(), nullable=False),
    sa.Column('is_enabled', sa.Boolean(), nullable=True),
    sa.Column('enabled_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['module_id'], ['modules.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'module_id', name='_tenant_module_uc')
    )

    # Insert default modules
    op.execute("""
        INSERT INTO modules (id, name, description, category, price_per_month, is_core, is_available, features) VALUES
        ('core-001', 'Project Management', 'Complete project management suite with tasks, milestones, and Gantt charts', 'Core', 0.0, true, true, '["Task Management", "Milestones", "Gantt Charts", "Project Templates"]'),
        ('core-002', 'User Management', 'User roles, permissions, and authentication system', 'Core', 0.0, true, true, '["User Roles", "Permissions", "Authentication", "Team Management"]'),
        ('productivity-001', 'Time Tracking', 'Advanced time tracking and reporting capabilities', 'Productivity', 49.0, false, true, '["Time Tracking", "Timesheet Reports", "Billable Hours", "Time Analytics"]'),
        ('productivity-002', 'Team Chat', 'Real-time team communication and collaboration', 'Communication', 29.0, false, true, '["Real-time Chat", "File Sharing", "Team Channels", "Message History"]'),
        ('finance-001', 'Invoice Management', 'Generate and manage invoices with Stripe integration', 'Finance', 79.0, false, true, '["Invoice Generation", "Payment Tracking", "Stripe Integration", "Tax Calculations"]'),
        ('finance-002', 'Expense Tracking', 'Track and categorize business expenses', 'Finance', 39.0, false, true, '["Expense Logging", "Receipt Scanning", "Category Management", "Expense Reports"]'),
        ('analytics-001', 'Advanced Analytics', 'Detailed analytics and reporting dashboard', 'Analytics', 149.0, false, true, '["Custom Reports", "Data Visualization", "Export Tools", "Scheduled Reports"]'),
        ('integration-001', 'API Access', 'Full API access for custom integrations', 'Integration', 99.0, false, true, '["REST API", "Webhooks", "Custom Integrations", "API Documentation"]')
    """)


def downgrade():
    op.drop_table('tenant_modules')
    op.drop_table('modules')


