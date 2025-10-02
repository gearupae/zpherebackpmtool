"""merge_heads

Revision ID: f4c5250914f6
Revises: 2279d9d7160a, module_tables_001
Create Date: 2025-08-23 19:13:21.477397

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4c5250914f6'
down_revision: Union[str, None] = ('2279d9d7160a', 'module_tables_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
