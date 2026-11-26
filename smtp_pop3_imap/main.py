import connection_check
import download_inbox
import imap_inbox
import local_inbox
import send_email


def main():
    actions = {
        "1": ("Send email (SMTP)", send_email.main),
        "2": ("List server inbox (IMAP)", imap_inbox.main),
        "3": ("Download new messages (POP3)", download_inbox.main),
        "4": ("Open local inbox (SQLite)", local_inbox.main),
        "5": ("Check server connections", connection_check.main),
    }
    while True:
        print("\nEmail client")
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")
        print("0. Exit")
        try:
            choice = input("Select an option: ").strip()
            if choice == "0":
                return 0
            if choice not in actions:
                print("Enter a number from 0 to 5.")
                continue
            _, run = actions[choice]
            run()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting email client.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
