"""add project_id and customer_id to purchase_orders

Revision ID: 6a9b2d847d1b
Revises: c07b7e9b1a3a
Create Date: 2025-09-19 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6a9b2d847d1b'
down_revision: Union[str, None] = 'c07b7e9b1a3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns
    op.add_column('purchase_orders', sa.Column('project_id', sa.String(), nullable=True))
    op.add_column('purchase_orders', sa.Column('customer_id', sa.String(), nullable=True))

    # Indexes
    op.create_index('ix_purchase_orders_project_id', 'purchase_orders', ['project_id'], unique=False)
    op.create_index('ix_purchase_orders_customer_id', 'purchase_orders', ['customer_id'], unique=False)

    # Foreign keys
    op.create_foreign_key(
        'fk_purchase_orders_project_id_projects',
        source_table='purchase_orders',
        referent_table='projects',
        local_cols=['project_id'],
        remote_cols=['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_purchase_orders_customer_id_customers',
        source_table='purchase_orders',
        referent_table='customers',
        local_cols=['customer_id'],
        remote_cols=['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_purchase_orders_customer_id_customers', 'purchase_orders', type_='foreignkey')
    op.drop_constraint('fk_purchase_orders_project_id_projects', 'purchase_orders', type_='foreignkey')
    op.drop_index('ix_purchase_orders_customer_id', table_name='purchase_orders')
    op.drop_index('ix_purchase_orders_project_id', table_name='purchase_orders')
    op.drop_column('purchase_orders', 'customer_id')
    op.drop_column('purchase_orders', 'project_id')

