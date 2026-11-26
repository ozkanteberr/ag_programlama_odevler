import getpass
import poplib
import sqlite3
import ssl
from contextlib import closing
from email import policy
from email.parser import BytesParser

from inbox_store import get_saved_uids, initialize_database, open_database, save_message


def read_attachments(part):
    filename = part.get_filename()
    if filename or part.get_content_disposition() == "attachment":
        content = part.get_payload(decode=True)
        if content is None:
            if part.get_content_type() == "message/rfc822" and part.is_multipart():
                content = part.get_payload(0).as_bytes(policy=policy.SMTP)
            else:
                content = part.as_bytes(policy=policy.SMTP)
        yield filename or "attachment", part.get_content_type(), content
    elif part.is_multipart():
        for child in part.iter_parts():
            yield from read_attachments(child)


def download_messages(connection, account, password):
    known = get_saved_uids(connection, account)
    downloaded = skipped = 0
    with closing(poplib.POP3_SSL("pop.gmail.com", 995, timeout=30,
                                 context=ssl.create_default_context())) as client:
        client.user(account)
        client.pass_(password)
        for entry in client.uidl()[1]:
            number, uid = entry.decode("ascii").split()
            if uid in known:
                skipped += 1
                continue
            lines = client.retr(int(number))[1]
            message = BytesParser(policy=policy.default).parsebytes(b"\r\n".join(lines) + b"\r\n")
            body_part = message.get_body(preferencelist=("plain", "html"))
            body = ""
            if body_part is not None:
                try:
                    body = body_part.get_content()
                except LookupError:
                    body = body_part.get_payload(decode=True).decode("utf-8", errors="replace")
            saved = save_message(
                connection, account=account, pop_uid=uid, subject=str(message.get("Subject", "")),
                sender=str(message.get("From", "")), recipients=", ".join(message.get_all("To", [])),
                message_date=message.get("Date"), body=body, attachments=read_attachments(message),
            )
            known.add(uid)
            if saved:
                downloaded += 1
            else:
                skipped += 1
        client.quit()
    return downloaded, skipped


def main():
    account = input("Gmail address: ").strip()
    password = "".join(getpass.getpass("Google app password (hidden): ").split())
    try:
        with closing(open_database()) as connection:
            initialize_database(connection)
            downloaded, skipped = download_messages(connection, account, password)
    except (OSError, ValueError, sqlite3.Error, poplib.error_proto) as error:
        print(f"Could not finish inbox download: {error}")
        return 1
    print(f"Downloaded: {downloaded} | Already saved: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
