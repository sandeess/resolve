"""row-level security

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05

Defence in depth for tenant isolation. The application keeps its owner
connection but runs each request transaction as the unprivileged role
`resolve_app` (see app/core/rls.py), with `app.user_id` / `app.is_admin` set.
Policies then limit every table to the journals the user belongs to.

Superusers and table owners bypass RLS, so this only protects sessions that
switch role; the worker and migrations stay privileged on purpose.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

ROLE = "resolve_app"

# Tables carrying a journal_id: visible when the journal is.
JOURNAL_SCOPED = ("article", "document", "chunk", "ticket")
# Child tables: visible when their parent row is (which applies the parent's policy).
CHILDREN = {
    "documentversion": ("document_id", "document"),
    "ticketmessage": ("ticket_id", "ticket"),
    "ticketresolution": ("ticket_id", "ticket"),
}
GRANTED = (
    "app_user",
    "journal",
    "journalmember",
    *JOURNAL_SCOPED,
    *CHILDREN,
)


def upgrade() -> None:
    op.execute(
        f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE}') THEN
                CREATE ROLE {ROLE} NOLOGIN;
            END IF;
        END $$;
        """
    )
    # A non-superuser owner must be a member of the role to SET ROLE to it.
    op.execute(f"GRANT {ROLE} TO CURRENT_USER")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    for table in GRANTED:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {ROLE}")
    op.execute(f"GRANT USAGE ON SEQUENCE ticket_number_seq TO {ROLE}")

    op.execute(
        """
        CREATE FUNCTION app_user_id() RETURNS uuid LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_is_admin() RETURNS boolean LANGUAGE sql STABLE AS
        $$ SELECT coalesce(nullif(current_setting('app.is_admin', true), '')::boolean, false) $$
        """
    )
    # SECURITY DEFINER so it can read `journal` / `journalmember` without being
    # filtered by the very policies it feeds (which would recurse).
    op.execute(
        """
        CREATE FUNCTION app_visible_journal_ids() RETURNS SETOF uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
        $$
            SELECT id FROM journal WHERE app_is_admin()
            UNION
            SELECT journal_id FROM journalmember WHERE user_id = app_user_id()
        $$
        """
    )

    for table in ("journal", "journalmember", *JOURNAL_SCOPED, *CHILDREN):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    visible = "(SELECT app_visible_journal_ids())"
    op.execute(f"CREATE POLICY journal_read ON journal FOR SELECT TO {ROLE} USING (id IN {visible})")
    op.execute(f"CREATE POLICY journal_admin ON journal FOR ALL TO {ROLE} USING (app_is_admin()) WITH CHECK (app_is_admin())")
    op.execute(f"CREATE POLICY journalmember_read ON journalmember FOR SELECT TO {ROLE} USING (user_id = app_user_id() OR app_is_admin())")
    op.execute(f"CREATE POLICY journalmember_admin ON journalmember FOR ALL TO {ROLE} USING (app_is_admin()) WITH CHECK (app_is_admin())")
    for table in JOURNAL_SCOPED:
        op.execute(
            f"CREATE POLICY {table}_scope ON {table} FOR ALL TO {ROLE} "
            f"USING (journal_id IN {visible}) WITH CHECK (journal_id IN {visible})"
        )
    for table, (fk, parent) in CHILDREN.items():
        op.execute(
            f"CREATE POLICY {table}_scope ON {table} FOR ALL TO {ROLE} "
            f"USING ({fk} IN (SELECT id FROM {parent})) WITH CHECK ({fk} IN (SELECT id FROM {parent}))"
        )


def downgrade() -> None:
    for table in ("journal", "journalmember", *JOURNAL_SCOPED, *CHILDREN):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in ("journal", "journalmember"):
        op.execute(f"DROP POLICY IF EXISTS {table}_read ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_admin ON {table}")
    for table in (*JOURNAL_SCOPED, *CHILDREN):
        op.execute(f"DROP POLICY IF EXISTS {table}_scope ON {table}")
    op.execute("DROP FUNCTION app_visible_journal_ids()")
    op.execute("DROP FUNCTION app_is_admin()")
    op.execute("DROP FUNCTION app_user_id()")
    op.execute(f"DROP OWNED BY {ROLE}")
    op.execute(f"DROP ROLE {ROLE}")
