"""add item_id to purchase_order_items

Revision ID: c07b7e9b1a3a
Revises: 2713631f58a0
Create Date: 2025-09-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c07b7e9b1a3a'
down_revision: Union[str, None] = '2713631f58a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add item_id column to purchase_order_items
    op.add_column('purchase_order_items', sa.Column('item_id', sa.String(), nullable=True))
    # Create index for faster lookups
    op.create_index('ix_purchase_order_items_item_id', 'purchase_order_items', ['item_id'], unique=False)
    # Create foreign key constraint to items table
    op.create_foreign_key(
        'fk_purchase_order_items_item_id_items',
        source_table='purchase_order_items',
        referent_table='items',
        local_cols=['item_id'],
        remote_cols=['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop foreign key and index, then column
    op.drop_constraint('fk_purchase_order_items_item_id_items', 'purchase_order_items', type_='foreignkey')
    op.drop_index('ix_purchase_order_items_item_id', table_name='purchase_order_items')
    op.drop_column('purchase_order_items', 'item_id')

