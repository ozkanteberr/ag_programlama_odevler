import getpass
import imaplib
import ssl
from email import policy
from email.parser import BytesHeaderParser


def fetch_inbox_metadata(email_address, password):
    parser = BytesHeaderParser(policy=policy.default)
    with imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=10,
                          ssl_context=ssl.create_default_context()) as client:
        client.login(email_address, password)
        status, counts = client.select("INBOX", readonly=True)
        if status != "OK":
            raise imaplib.IMAP4.error("Could not open the inbox.")
        total = int(counts[0])
        if total == 0:
            return 0, []

        first = max(1, total - 9)
        status, records = client.fetch(f"{first}:{total}",
                                       "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if status != "OK":
            raise imaplib.IMAP4.error("Could not read message headers.")

        messages = []
        for record in records:
            if isinstance(record, tuple):
                sequence = int(record[0].split()[0])
                headers = parser.parsebytes(record[1])
                messages.append((sequence, headers.get("From", "(unknown sender)"),
                                 headers.get("Subject", "(no subject)"),
                                 headers.get("Date", "(unknown date)")))
        return total, sorted(messages, key=lambda item: item[0], reverse=True)


def main():
    address = input("Gmail address: ").strip()
    password = "".join(getpass.getpass("Google app password (hidden): ").split())
    try:
        total, messages = fetch_inbox_metadata(address, password)
    except (OSError, ValueError, imaplib.IMAP4.error) as error:
        print(f"Could not read inbox: {error}")
        return 1
    print(f"Total messages in INBOX: {total}")
    for sequence, sender, subject, date in messages:
        print(f"\n#{sequence}  {subject}\nFrom: {sender}\nDate: {date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
