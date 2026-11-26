import sqlite3
from contextlib import closing

from inbox_store import (export_attachment, get_message, initialize_database, list_attachments,
                         list_messages, open_database)


def browse(connection):
    messages = list_messages(connection)
    if not messages:
        print("Local inbox is empty.")
        return
    for row in messages:
        print(f"#{row['id']}  {row['subject']}  |  {row['sender']}")
    selection = input("Message ID (Enter to exit): ").strip()
    if not selection:
        return
    message = get_message(connection, selection)
    if message is None:
        raise ValueError("Message not found.")
    print(f"Subject: {message['subject']}\nFrom: {message['sender']}\nTo: {message['recipients']}")
    print(f"Date: {message['message_date'] or '(unknown)'}\n\n{message['body']}")
    attachments = list_attachments(connection, message["id"])
    if not attachments:
        print("No attachments.")
        return
    for item in attachments:
        print(f"Attachment #{item['id']}  {item['filename']}  ({item['content_type']})")
    selection = input("Attachment ID to export (Enter to exit): ").strip()
    if selection:
        directory = input("Destination folder (Enter for current folder): ").strip().strip('"') or "."
        target = export_attachment(connection, message["id"], selection, directory)
        print(f"Saved: {target.resolve()}")


def main():
    try:
        with closing(open_database()) as connection:
            initialize_database(connection)
            browse(connection)
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"Could not open message or save attachment: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
