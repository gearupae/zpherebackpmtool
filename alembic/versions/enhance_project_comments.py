"""Enhance project comments for public commenting

Revision ID: enhance_project_comments
Revises: add_task_documents_and_improve_comments
Create Date: 2025-09-20 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'enhance_project_comments'
down_revision = 'add_task_documents_and_improve_comments'
branch_labels = None
depends_on = None


def upgrade():
    """Add columns for public commenting support"""
    
    # Add new columns to project_comments table
    op.add_column('project_comments', sa.Column('author_name', sa.String(100), nullable=True))
    op.add_column('project_comments', sa.Column('author_email', sa.String(255), nullable=True))
    op.add_column('project_comments', sa.Column('is_public', sa.Boolean(), nullable=False, default=False))
    op.add_column('project_comments', sa.Column('is_approved', sa.Boolean(), nullable=False, default=True))
    op.add_column('project_comments', sa.Column('source_type', sa.String(50), nullable=False, default='internal'))
    op.add_column('project_comments', sa.Column('share_id', sa.String(255), nullable=True))
    
    # Make user_id nullable for public comments
    op.alter_column('project_comments', 'user_id', nullable=True)
    
    # Add indexes for better performance
    op.create_index('ix_project_comments_project_id', 'project_comments', ['project_id'])
    op.create_index('ix_project_comments_share_id', 'project_comments', ['share_id'])
    op.create_index('ix_project_comments_parent_comment_id', 'project_comments', ['parent_comment_id'])
    
    # Create project_comment_attachments table if it doesn't exist
    # (This might already exist, so we'll check first)
    try:
        op.create_table('project_comment_attachments',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('comment_id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('filename', sa.String(500), nullable=False),
            sa.Column('original_filename', sa.String(500), nullable=False),
            sa.Column('file_path', sa.String(1000), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('mime_type', sa.String(100), nullable=True),
            sa.ForeignKeyConstraint(['comment_id'], ['project_comments.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_project_comment_attachments_comment_id', 'project_comment_attachments', ['comment_id'])
    except Exception:
        # Table might already exist
        pass


def downgrade():
    """Remove public commenting columns"""
    
    # Drop indexes
    try:
        op.drop_index('ix_project_comments_parent_comment_id', 'project_comments')
        op.drop_index('ix_project_comments_share_id', 'project_comments')
        op.drop_index('ix_project_comments_project_id', 'project_comments')
    except Exception:
        pass
    
    # Remove columns
    op.drop_column('project_comments', 'share_id')
    op.drop_column('project_comments', 'source_type')
    op.drop_column('project_comments', 'is_approved')
    op.drop_column('project_comments', 'is_public')
    op.drop_column('project_comments', 'author_email')
    op.drop_column('project_comments', 'author_name')
    
    # Make user_id not nullable again
    op.alter_column('project_comments', 'user_id', nullable=False)