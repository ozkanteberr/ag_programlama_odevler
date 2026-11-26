"""Check Gmail SMTP, POP3, and IMAP connections from the terminal."""

import argparse
import getpass
import imaplib
import poplib
import smtplib
import ssl
from contextlib import closing


def check_smtp(email_address, password, tls):
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10, context=tls) as client:
        client.login(email_address, password)


def check_pop3(email_address, password, tls):
    with closing(poplib.POP3_SSL("pop.gmail.com", 995, timeout=10, context=tls)) as client:
        client.user(email_address)
        client.pass_(password)
        # Tekrar indirmeyi önlemek için gereken ileti kimliklerini sorgula.
        client.uidl()
        client.quit()


def check_imap(email_address, password, tls):
    with imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=10, ssl_context=tls) as client:
        client.login(email_address, password)
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise imaplib.IMAP4.error("Could not open the inbox")


CHECKS = {"smtp": check_smtp, "pop3": check_pop3, "imap": check_imap}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", choices=[*CHECKS, "all"], nargs="?", default="all")
    args = parser.parse_args()
    email_address = input("Gmail address: ").strip()
    password = "".join(getpass.getpass("Google app password (16 characters, hidden): ").split())
    if not email_address or not password:
        print("Gmail address and app password are required.")
        return 1
    if not email_address.isascii():
        print("The Gmail address contains a non-ASCII character. Check the address and try again.")
        return 1
    if not password.isascii():
        print("The app password contains a non-ASCII character. Try typing the 16 characters manually.")
        return 1

    tls = ssl.create_default_context()
    protocols = CHECKS if args.protocol == "all" else [args.protocol]
    exit_code = 0
    for protocol in protocols:
        try:
            CHECKS[protocol](email_address, password, tls)
        except (OSError, imaplib.IMAP4.error, poplib.error_proto) as error:
            print(f"{protocol.upper()} failed: {error}")
            exit_code = 1
        else:
            print(f"{protocol.upper()} succeeded.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
