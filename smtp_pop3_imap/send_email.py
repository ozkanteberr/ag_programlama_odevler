import getpass
import mimetypes
import smtplib
import ssl
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path


def parse_address(value):
    address = Address(addr_spec=value.strip())
    if not address.username or not address.domain:
        raise ValueError("Enter a complete email address.")
    return address


def send_email(sender, password, recipient, subject, body, attachment_paths=()):
    message = EmailMessage()
    message["From"] = parse_address(sender)
    addresses = [parse_address(value) for value in recipient.split(",")]
    message["To"] = addresses
    recipients = list(dict.fromkeys(address.addr_spec for address in addresses))
    if not password or not password.isascii() or not sender.isascii():
        raise ValueError("Check your Gmail address and Google app password.")
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()
    message.set_content(body)
    for file_path in attachment_paths:
        path = Path(file_path)
        content_type, encoding = mimetypes.guess_type(path.name)
        if encoding or not content_type:
            content_type = "application/octet-stream"
        maintype, subtype = content_type.split("/", 1)
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype,
                               filename=path.name)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10,
                          context=ssl.create_default_context()) as client:
        client.login(sender, password)
        try:
            refused = client.send_message(message, to_addrs=recipients)
        except smtplib.SMTPRecipientsRefused as error:
            refused = error.recipients
    return [address for address in recipients if address not in refused], refused


def main():
    sender = input("Gmail address: ").strip()
    password = "".join(getpass.getpass("Google app password (hidden): ").split())
    recipient = input("Recipient email addresses (comma-separated): ").strip()
    subject = input("Subject: ")
    body = input("Message: ")
    attachment_paths = []
    while path := input("Attachment path (Enter to finish): ").strip():
        attachment_paths.append(path.strip('"'))
    try:
        accepted, refused = send_email(sender, password, recipient, subject, body, attachment_paths)
    except (ValueError, HeaderParseError, OSError) as error:
        print(f"Could not send email: {error}")
        return 1
    for address in accepted:
        print(f"SMTP server accepted the message for {address}.")
    for address, (code, _) in refused.items():
        print(f"SMTP server refused {address} (code {code}).")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
