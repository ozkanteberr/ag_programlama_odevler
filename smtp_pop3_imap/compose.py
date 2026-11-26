import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from send_email import send_email


class ComposeWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("New message")
        self.geometry("680x610")
        self.minsize(490, 510)
        self.transient(parent.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.pending = None
        self.paths = []
        self.configure(bg="white")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        tk.Label(self, text="New message", bg="#18365a", fg="white",
                 font=("Segoe UI", 16, "bold"), anchor="w", padx=20, pady=12).grid(sticky="ew")
        form = tk.Frame(self, bg="white", padx=20, pady=12)
        form.grid(row=1, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)
        form.rowconfigure(5, weight=1)
        self.entries = []
        for row, label in enumerate(("From (Gmail)", "App password", "To (comma-separated)", "Subject")):
            tk.Label(form, text=label, bg="white", fg="#334e68", anchor="w",
                     font=("Segoe UI", 10)).grid(row=row, column=0, sticky="w", padx=(0, 12))
            entry = ttk.Entry(form, show="•" if row == 1 else "", font=("Segoe UI", 11))
            entry.grid(row=row, column=1, sticky="ew", pady=3, ipady=2)
            self.entries.append(entry)
        self.sender, self.password, self.recipients, self.subject = self.entries
        ttk.Separator(form).grid(row=4, columnspan=2, sticky="ew", pady=10)
        self.body = ScrolledText(form, height=6, width=1, wrap="word", undo=True, relief="flat",
                                 font=("Segoe UI", 11), padx=4, pady=4)
        self.body.grid(row=5, columnspan=2, sticky="nsew")
        self.files = tk.Listbox(form, height=3, relief="flat", bg="#f1f6fb",
                                exportselection=False, selectmode="extended")
        self.files.grid(row=6, columnspan=2, sticky="ew", pady=6)
        self.files.grid_remove()
        footer = ttk.Frame(form)
        footer.grid(row=7, columnspan=2, sticky="ew")
        self.attach = ttk.Button(footer, text="Attach files…", command=self.add_files)
        self.attach.pack(side="left")
        self.remove = ttk.Button(footer, text="Remove selected", command=self.remove_files)
        self.send = tk.Button(footer, text="Send", bg="#145db0", fg="white", relief="flat",
                              padx=20, pady=6, font=("Segoe UI", 11, "bold"), command=self.submit)
        self.send.pack(side="right")
        self.sender.focus_set()

    def add_files(self):
        for path in filedialog.askopenfilenames(parent=self, title="Attach files"):
            if path not in self.paths:
                self.paths.append(path)
                self.files.insert("end", Path(path).name)
        if self.paths:
            self.files.grid()
            self.remove.pack(side="left", padx=4)

    def remove_files(self):
        for index in reversed(self.files.curselection()):
            self.files.delete(index)
            self.paths.pop(index)
        if not self.paths:
            self.files.grid_remove()
            self.remove.pack_forget()

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for widget in (*self.entries, self.body, self.attach, self.remove, self.send):
            widget.configure(state=state)
        self.send.configure(text="Sending…" if busy else "Send")

    def submit(self):
        if self.pending is not None:
            return
        args = (self.sender.get().strip(), "".join(self.password.get().split()),
                self.recipients.get().strip(), self.subject.get(), self.body.get("1.0", "end-1c"),
                tuple(self.paths))
        if not all(args[:3]):
            messagebox.showerror("Missing details", "Enter your Gmail address, app password, and recipients.", parent=self)
            return
        self.set_busy(True)
        worker = ThreadPoolExecutor(max_workers=1)
        self.pending = worker.submit(send_email, *args)
        worker.shutdown(wait=False)
        self.after(100, self.check_result)

    def check_result(self):
        if not self.pending.done():
            self.after(100, self.check_result)
            return
        future, self.pending = self.pending, None
        self.set_busy(False)
        try:
            accepted, refused = future.result()
        except Exception as error:
            messagebox.showerror("Could not send message", str(error), parent=self)
            return
        if refused:
            details = "Refused: " + ", ".join(refused)
            if accepted:
                details = "Accepted: " + ", ".join(accepted) + "\n" + details
            self.recipients.delete(0, "end")
            self.recipients.insert(0, ", ".join(refused))
            messagebox.showwarning("Delivery status", details, parent=self)
        else:
            messagebox.showinfo("Message sent", "Accepted by SMTP for: " + ", ".join(accepted), parent=self)
            self.destroy()

    def close(self):
        if self.pending is None:
            self.destroy()
