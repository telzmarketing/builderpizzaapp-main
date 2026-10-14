# Database migrations

Production schema changes run through Alembic revisions in `versions/` using
the configured Telz release/update procedure. Standalone SQL files in this
directory are historical references, not an additional migration runner.

`0001_order_cancellation_tracking.sql` is superseded by revision
`20261014_order_cancellation_tracking`. That revision adds the nullable order
cancellation columns and partial index when absent, and preserves existing
values when the legacy SQL was already applied. Its downgrade is blocked to
preserve cancellation history.
