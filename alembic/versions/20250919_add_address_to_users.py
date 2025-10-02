"""
Add address column to users table
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "3b9f0f2a1add"
down_revision = "f4c5250914f6"
branch_labels = None
depends_on = None

def upgrade() -> None:
    try:
        op.add_column("users", sa.Column("address", sa.String(length=255), nullable=True))
    except Exception:
        # If column already exists or table missing in this DB, ignore to allow idempotent runs
        pass


def downgrade() -> None:
    try:
        op.drop_column("users", "address")
    except Exception:
        pass

