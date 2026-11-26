import sqlite3
from contextlib import closing
from pathlib import Path


DATABASE_PATH = Path(__file__).with_name("inbox.sqlite3")


def open_database(path=DATABASE_PATH):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection):
    with connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                account TEXT NOT NULL COLLATE NOCASE,
                pop_uid TEXT NOT NULL,
                subject TEXT NOT NULL,
                sender TEXT NOT NULL,
                recipients TEXT NOT NULL,
                message_date TEXT,
                body TEXT NOT NULL,
                downloaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (account, pop_uid)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content BLOB NOT NULL
            )
        """)


def get_saved_uids(connection, account):
    rows = connection.execute("SELECT pop_uid FROM messages WHERE account = ?", (account,))
    return {row[0] for row in rows}


def list_messages(connection):
    return connection.execute("SELECT id, subject, sender FROM messages ORDER BY id DESC").fetchall()


def get_message(connection, message_id):
    return connection.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()


def list_attachments(connection, message_id):
    return connection.execute("""
        SELECT id, filename, content_type FROM attachments WHERE message_id = ? ORDER BY id
    """, (message_id,)).fetchall()


def export_attachment(connection, message_id, attachment_id, directory):
    row = connection.execute("""
        SELECT filename, content FROM attachments WHERE message_id = ? AND id = ?
    """, (message_id, attachment_id)).fetchone()
    if row is None:
        raise ValueError("Attachment not found in this message.")
    filename = Path(row["filename"].replace("\\", "/")).name
    if (not filename or filename.endswith((".", " ")) or Path(filename).is_reserved()
            or any(c in '<>:"|?*' or ord(c) < 32 for c in filename)):
        filename = f"attachment-{attachment_id}.bin"
    original = Path(directory) / filename
    target = original
    number = 1
    while True:
        try:
            output = target.open("xb")
            break
        except FileExistsError:
            target = original.with_name(f"{original.stem} ({number}){original.suffix}")
            number += 1
    with output:
        output.write(row["content"])
    return target


def save_message(connection, *, account, pop_uid, subject, sender, recipients,
                 message_date, body, attachments=()):
    # Eklerden biri kaydedilemezse ileti kaydı da geri alınır.
    with connection:
        result = connection.execute("""
            INSERT INTO messages (account, pop_uid, subject, sender, recipients, message_date, body)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (account, pop_uid) DO NOTHING
        """, (account, pop_uid, subject, sender, recipients, message_date, body))
        if result.rowcount == 0:
            return False
        connection.executemany("""
            INSERT INTO attachments (message_id, filename, content_type, content)
            VALUES (?, ?, ?, ?)
        """, ((result.lastrowid, filename, content_type, content)
              for filename, content_type, content in attachments))
    return True


if __name__ == "__main__":
    with closing(open_database()) as connection:
        initialize_database(connection)
    print(f"Inbox database ready: {DATABASE_PATH}")
