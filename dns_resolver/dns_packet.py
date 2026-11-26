import secrets
import socket
import struct
from dataclasses import dataclass


A, NS, CNAME = 1, 2, 5


class DNSError(Exception):
    pass


@dataclass
class Record:
    name: str
    kind: int
    ttl: int
    value: str


@dataclass
class Response:
    answers: list
    authority: list
    additional: list
    authoritative: bool
    rcode: int


def normalize_name(name):
    name = name.strip().rstrip(".")
    if not name or any(not part for part in name.split(".")):
        raise DNSError("Geçerli bir alan adı girin.")
    try:
        name = name.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise DNSError("Alan adı geçersiz.") from error
    labels = name.split(".")
    if any(len(label) > 63 for label in labels) or len(name) > 253:
        raise DNSError("Alan adı DNS uzunluk sınırını aşıyor.")
    if any(not all(c.isalnum() or c in "-_" for c in label) for label in labels):
        raise DNSError("Alan adı geçersiz karakter içeriyor.")
    return name


def encode_name(name):
    return b"".join(bytes([len(part)]) + part.encode("ascii")
                    for part in name.split(".")) + b"\x00"


def read_name(packet, offset):
    labels = []
    next_offset = None
    visited = set()
    while True:
        if offset >= len(packet) or offset in visited:
            raise DNSError("DNS yanıtında bozuk alan adı.")
        visited.add(offset)
        length = packet[offset]
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(packet):
                raise DNSError("Eksik DNS sıkıştırma işaretçisi.")
            # Sıkıştırılmış isimler paketteki başka bir konuma işaret eder.
            if next_offset is None:
                next_offset = offset + 2
            offset = ((length & 0x3F) << 8) | packet[offset + 1]
            continue
        if length & 0xC0:
            raise DNSError("Geçersiz DNS etiket uzunluğu.")
        offset += 1
        if length == 0:
            return ".".join(labels).lower(), next_offset or offset
        if offset + length > len(packet):
            raise DNSError("Eksik DNS etiketi.")
        labels.append(packet[offset:offset + length].decode("ascii"))
        offset += length


def parse_response(packet, query_id, domain):
    try:
        response_id, flags, qd, an, ns, ar = struct.unpack_from("!6H", packet)
        if response_id != query_id or not flags & 0x8000:
            raise DNSError("DNS yanıtının kimliği veya türü uyuşmuyor.")
        if flags & 0x0200:
            raise DNSError("DNS yanıtı UDP sınırı nedeniyle kesilmiş.")
        if qd != 1:
            raise DNSError("Beklenmeyen DNS soru sayısı.")
        question, offset = read_name(packet, 12)
        kind, record_class = struct.unpack_from("!HH", packet, offset)
        offset += 4
        if (question, kind, record_class) != (domain, A, 1):
            raise DNSError("DNS yanıtındaki soru uyuşmuyor.")
        sections = []
        for count in (an, ns, ar):
            records = []
            for _ in range(count):
                name, offset = read_name(packet, offset)
                kind, record_class, ttl, size = struct.unpack_from("!HHIH", packet, offset)
                offset += 10
                end = offset + size
                if end > len(packet):
                    raise DNSError("Eksik DNS kaydı.")
                value = None
                if record_class == 1:
                    if kind == A and size == 4:
                        value = socket.inet_ntoa(packet[offset:end])
                    elif kind in (NS, CNAME):
                        value, name_end = read_name(packet, offset)
                        if name_end != end:
                            raise DNSError("Geçersiz DNS kayıt uzunluğu.")
                if value is not None:
                    records.append(Record(name, kind, ttl, value))
                offset = end
            sections.append(records)
        return Response(*sections, bool(flags & 0x0400), flags & 0x000F)
    except (struct.error, UnicodeError) as error:
        raise DNSError("DNS yanıtı okunamadı: bozuk veya eksik paket.") from error


def query_server(domain, server, timeout=3):
    query_id = secrets.randbits(16)
    # RD=0: sunucudan bizim yerimize özyinelemeli çözümleme istemiyoruz.
    packet = struct.pack("!6H", query_id, 0, 1, 0, 0, 0)
    packet += encode_name(domain) + struct.pack("!HH", A, 1)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.connect((server, 53))
            sock.send(packet)
            response = sock.recv(65535)
    except socket.timeout as error:
        raise DNSError(f"{server}: zaman aşımı.") from error
    except OSError as error:
        raise DNSError(f"{server}: sunucuya ulaşılamadı ({error}).") from error
    return parse_response(response, query_id, domain)
