from app.database import get_connection, init_db
from app.migrations import apply_pending


def test_apply_pending_runs_migration_once():
    conn = get_connection(":memory:")
    migrations = [("0001_test_table", "CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT)")]

    applied_first = apply_pending(conn, migrations)
    applied_second = apply_pending(conn, migrations)

    assert applied_first == ["0001_test_table"]
    assert applied_second == []

    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == 1
    conn.close()


def test_apply_pending_runs_only_new_migrations_incrementally():
    conn = get_connection(":memory:")
    first_batch = [("0001_a", "CREATE TABLE a_table (id INTEGER PRIMARY KEY)")]
    apply_pending(conn, first_batch)

    second_batch = first_batch + [("0002_b", "CREATE TABLE b_table (id INTEGER PRIMARY KEY)")]
    applied = apply_pending(conn, second_batch)

    assert applied == ["0002_b"]
    tables = {
        row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"a_table", "b_table"}.issubset(tables)
    conn.close()


def test_init_db_is_idempotent_on_file_and_memory():
    conn1 = init_db(":memory:")
    conn1.close()
    conn2 = init_db(":memory:")
    conn2.close()


def test_init_db_idempotent_on_existing_file_db(tmp_path):
    db_path = str(tmp_path / "test.sqlite3")
    conn1 = init_db(db_path)
    conn1.close()
    conn2 = init_db(db_path)
    conn2.close()


def test_get_connection_sets_busy_timeout():
    conn = get_connection(":memory:")
    timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout == 5000
    conn.close()
