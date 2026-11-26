import sqlite3
import tkinter as tk
from contextlib import closing
from email.utils import parseaddr
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from compose import ComposeWindow
from inbox_store import (export_attachment, get_message, initialize_database,
                         list_attachments, list_messages, open_database)


class LocalInbox(ttk.Frame):
    def __init__(self, parent, connection):
        super().__init__(parent)
        self.connection = connection
        self.message_id = None
        self.attachments = []
        self.only_files = False
        self.query = tk.StringVar()
        self.rows = []
        self.with_files = set()
        navy, blue, muted = "#18365a", "#145db0", "#52677c"
        font = "Segoe UI"
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Mail.Treeview", rowheight=62, font=(font, 10), borderwidth=0,
                        foreground=navy, background="white", fieldbackground="white")
        style.map("Mail.Treeview", background=[("selected", "#dcecff")],
                  foreground=[("selected", "#103f75")])
        style.configure("Mail.TButton", padding=(12, 6), font=(font, 10),
                        background="#e9f1fa", foreground=navy, borderwidth=0)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(1, weight=1)
        bar = tk.Frame(self, bg=navy, padx=18, pady=10)
        bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        tk.Label(bar, text="✉   Mail", bg=navy, fg="white",
                 font=(font, 17, "bold")).pack(side="left", padx=(0, 40))
        tk.Label(bar, text="Search inbox", bg=navy, fg="white", font=(font, 10)).pack(side="left")
        self.search = ttk.Entry(bar, textvariable=self.query, width=30, font=(font, 11))
        self.search.pack(side="left", padx=10, ipady=4)
        ttk.Button(bar, text="Refresh", style="Mail.TButton",
                   command=self.refresh).pack(side="right")

        rail = tk.Frame(self, bg="#edf3f9", padx=10, pady=18)
        rail.grid(row=1, column=0, sticky="ns")
        tk.Button(rail, text="＋  Create", command=lambda: ComposeWindow(self),
                  bg=blue, fg="white", activebackground="#104c91", activeforeground="white",
                  relief="flat", cursor="hand2", padx=14, pady=9,
                  font=(font, 11, "bold")).pack(fill="x", pady=(0, 20))
        tk.Label(rail, text="Local mailbox", bg="#edf3f9", fg=muted,
                 font=(font, 10, "bold")).pack(anchor="w", padx=8, pady=(0, 12))
        self.folders = []
        for label, flag in (("Inbox", False), ("With attachments", True)):
            button = tk.Button(rail, text=label, anchor="w", relief="flat", bd=0,
                               padx=10, pady=8, cursor="hand2", font=(font, 10),
                               command=lambda value=flag: self.select_folder(value))
            button.pack(fill="x", pady=2)
            self.folders.append(button)

        listing = tk.Frame(self, bg="white", highlightthickness=1, highlightbackground="#d8e3ec")
        listing.grid(row=1, column=1, sticky="nsew")
        self.title = tk.Label(listing, bg="white", fg=navy, font=(font, 15, "bold"))
        self.title.pack(anchor="w", padx=14, pady=14)
        self.messages = ttk.Treeview(listing, show="tree", selectmode="browse", style="Mail.Treeview")
        self.messages.column("#0", width=255, stretch=False)
        scroll = ttk.Scrollbar(listing, command=self.messages.yview)
        scroll.pack(side="right", fill="y")
        self.messages.configure(yscrollcommand=scroll.set)
        self.messages.pack(fill="both", expand=True)
        self.messages.bind("<<TreeviewSelect>>", self.show_message)

        reader = tk.Frame(self, bg="white", padx=22, pady=16)
        reader.grid(row=1, column=2, sticky="nsew")
        reader.columnconfigure(0, weight=1)
        reader.rowconfigure(0, weight=1)
        self.body = ScrolledText(reader, wrap="word", width=1, height=1, relief="flat",
                                 borderwidth=0, font=(font, 11), fg="#23384e", bg="white",
                                 padx=4, pady=4, state="disabled")
        self.body.grid(row=0, column=0, sticky="nsew")
        self.body.tag_configure("subject", font=(font, 19, "bold"), foreground=navy, spacing3=12)
        self.body.tag_configure("sender", font=(font, 11, "bold"), foreground=blue)
        self.body.tag_configure("metadata", font=(font, 10), foreground=muted)
        self.file_bar = tk.Frame(reader, bg="#f1f6fb", padx=10, pady=10)
        self.file_bar.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.files = ttk.Combobox(self.file_bar, state="readonly", width=12)
        self.files.pack(side="left", fill="x", expand=True)
        self.save = ttk.Button(self.file_bar, text="Save attachment…", style="Mail.TButton",
                               command=self.save_attachment)
        self.save.pack(side="right", padx=(8, 0))
        self.query.trace_add("write", lambda *_: self.filter_messages())
        self.winfo_toplevel().bind("<Control-f>", lambda _: self.search.focus_set())
        self.refresh()

    def select_folder(self, only_files):
        self.only_files = only_files
        self.filter_messages()

    def refresh(self):
        self.rows = list_messages(self.connection)
        self.with_files = {row[0] for row in self.connection.execute(
            "SELECT DISTINCT message_id FROM attachments")}
        self.filter_messages()

    def filter_messages(self):
        query = self.query.get().strip().casefold()
        selected = self.message_id
        self.messages.delete(*self.messages.get_children())
        for index, button in enumerate(self.folders):
            button.configure(bg="#cfe4fa" if index == self.only_files else "#edf3f9",
                             fg="#153d67")
        for row in self.rows:
            if self.only_files and row["id"] not in self.with_files:
                continue
            if query and query not in (row["sender"] + " " + row["subject"]).casefold():
                continue
            name, address = parseaddr(row["sender"])
            self.messages.insert("", "end", iid=str(row["id"]),
                                 text=f"{name or address or row['sender']}\n{row['subject'] or '(No subject)'}")
        ids = self.messages.get_children()
        label = "With attachments" if self.only_files else "Inbox"
        self.title.configure(text=f"{label}  ·  {len(ids)}")
        if ids:
            current = selected if selected in ids else ids[0]
            self.messages.selection_set(current)
            self.messages.see(current)
        self.show_message()

    def show_message(self, event=None):
        selection = self.messages.selection()
        self.message_id = selection[0] if selection else None
        message = get_message(self.connection, self.message_id)
        self.attachments = list_attachments(self.connection, self.message_id)
        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        if message:
            self.body.insert("end", (message["subject"] or "(No subject)") + "\n", "subject")
            self.body.insert("end", message["sender"] + "\n", "sender")
            self.body.insert("end", f"To: {message['recipients']}\n{message['message_date'] or ''}\n\n", "metadata")
            self.body.insert("end", message["body"])
        else:
            self.body.insert("end", "No matching messages." if self.rows else "Your local inbox is empty.")
        self.body.configure(state="disabled")
        if self.attachments:
            self.files.configure(values=[row["filename"] for row in self.attachments])
            self.files.current(0)
            self.file_bar.grid()
        else:
            self.file_bar.grid_remove()

    def save_attachment(self):
        directory = filedialog.askdirectory(parent=self, mustexist=True)
        if not directory:
            return
        item = self.attachments[self.files.current()]
        try:
            target = export_attachment(self.connection, self.message_id, item["id"], directory)
        except (ValueError, OSError, sqlite3.Error) as error:
            messagebox.showerror("Could not save attachment", str(error), parent=self)
        else:
            messagebox.showinfo("Attachment saved", str(target), parent=self)


def main():
    root = tk.Tk()
    root.title("Email client")
    root.geometry("1100x650")
    root.minsize(760, 410)
    with closing(open_database()) as connection:
        initialize_database(connection)
        LocalInbox(root, connection).pack(fill="both", expand=True)
        root.mainloop()


if __name__ == "__main__":
    main()
