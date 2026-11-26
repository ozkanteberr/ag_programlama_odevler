import ipaddress
import os
import time
from pathlib import Path


class DNSCache:
    def __init__(self):
        self.entries = {}

    def get(self, domain):
        entry = self.entries.get(domain)
        if entry is None:
            return None
        addresses, expires_at = entry
        remaining = expires_at - time.monotonic()
        if remaining <= 0:
            del self.entries[domain]
            return None
        return list(addresses), remaining

    def put(self, domain, addresses, ttl):
        if ttl > 0:
            self.entries[domain] = (tuple(addresses), time.monotonic() + ttl)


def read_hosts(domain):
    if os.name == "nt":
        path = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        path = path / "System32/drivers/etc/hosts"
    else:
        path = Path("/etc/hosts")
    addresses = []
    try:
        with path.open(encoding="utf-8-sig", errors="replace") as hosts:
            for line in hosts:
                fields = line.split("#", 1)[0].split()
                if len(fields) < 2:
                    continue
                aliases = [name.lower().rstrip(".") for name in fields[1:]]
                if domain not in aliases:
                    continue
                try:
                    address = str(ipaddress.IPv4Address(fields[0]))
                except ipaddress.AddressValueError:
                    continue
                if address not in addresses:
                    addresses.append(address)
    except OSError as error:
        print(f"  hosts dosyası okunamadı: {error}")
    return addresses
