"""
Alembic migration: add FTS GIN indexes for search-heavy tables
- universal_search(title, content, description)
- decision_logs(title, description, problem_statement, decision_outcome)
- context_cards(title, content)
Note: Run per-tenant DBs or rely on Base.metadata.create_all for dev.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_fts_indexes'
down_revision = 'add_focus_blocks_table'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
    CREATE INDEX IF NOT EXISTS universal_search_fts_idx
    ON universal_search USING GIN (
        to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,'') || ' ' || coalesce(description,''))
    );
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS decision_logs_fts_idx
    ON decision_logs USING GIN (
        to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || coalesce(problem_statement,'') || ' ' || coalesce(decision_outcome,''))
    );
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS context_cards_fts_idx
    ON context_cards USING GIN (
        to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,''))
    );
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS universal_search_fts_idx;")
    op.execute("DROP INDEX IF EXISTS decision_logs_fts_idx;")
    op.execute("DROP INDEX IF EXISTS context_cards_fts_idx;")

