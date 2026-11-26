import sys
import time

from dns_packet import A, NS, CNAME, DNSError, normalize_name, query_server
from local_data import DNSCache, read_hosts


ROOT_SERVERS = ["198.41.0.4", "170.247.170.2", "192.33.4.12"]
MAX_DEPTH = 20
MAX_STEPS = 30
MAX_QUERIES = 40
MAX_SECONDS = 30


class NameNotFound(DNSError):
    pass


class ResolutionLimit(DNSError):
    pass


class DNSResolver:
    def __init__(self):
        self.cache = DNSCache()

    def resolve(self, domain, active=None):
        domain = normalize_name(domain)
        if active is None:
            self.queries = set()
            self.deadline = time.monotonic() + MAX_SECONDS
        active = set() if active is None else active #yoksa yeni küme oluştur varsa onu kullanmaya devam ederiz.
        if domain in active or len(active) >= MAX_DEPTH:
            raise DNSError("DNS yönlendirmesinde döngü veya derinlik sınırı.")
        print(f"\nSorgulanan Domain: {domain}")
        cached = self.cache.get(domain)
        if cached is not None:
            print(f"[0] Önbellekte bulundu (kalan TTL: {cached[1]:.1f} saniye).")
            return cached   #cachede varsa onu döner
        addresses = read_hosts(domain) #yerel dosyaya bakar
        if addresses:
            print("[0] hosts dosyasında bulundu.")
            return addresses, float("inf")
        print("[0] Önbellekte ve hosts dosyasında bulunamadı.")
        addresses, ttl = self._iterate(domain, active | {domain}) #iterate fonksiyonuna bakılır.
        self.cache.put(domain, addresses, ttl)
        return addresses, ttl

    def _iterate(self, domain, active): #active mevcut elimizdeki küme
        servers = ROOT_SERVERS[:]
        zone = ""
        for step in range(1, MAX_STEPS + 1):
            failures = []
            next_servers = None
            for server in servers:
                if (domain, server) in self.queries:
                    continue
                remaining = self.deadline - time.monotonic()
                if len(self.queries) >= MAX_QUERIES or remaining <= 0:
                    raise ResolutionLimit("DNS çözümlemesi toplam sorgu veya süre sınırını aştı.")
                self.queries.add((domain, server))
                stage = "Root" if not zone else f"{zone} bölgesinin"
                print(f"[{step}] {stage} Sunucusuna Bağlanılıyor ({server})...")
                try:
                    response = query_server(domain, server, timeout=min(3, remaining))
                    if response.rcode == 3: #NXDOMAIN sorgulanan alan adımı bulunamadı.
                        if response.authoritative:
                            raise NameNotFound(f"{domain}: alan adı bulunamadı (NXDOMAIN).")
                        raise DNSError("Yetkili olmayan sunucudan NXDOMAIN yanıtı.")
                    if response.rcode:
                        raise DNSError(f"DNS sunucusu hata döndürdü (kod {response.rcode}).")
                    if response.authoritative:
                        result = self._answer(domain, response.answers, active)
                        if result is not None:
                            return result
                        raise DNSError(f"{domain}: yetkili yanıtta A kaydı bulunamadı.")
                    referral = self._referral(domain, zone, response, active)#yönlendirme kısmı
                    if referral is None:
                        raise DNSError("Yanıtta kullanılabilir yönlendirme bulunamadı.")
                    zone, next_servers = referral
                    print(f"  -> {zone} için NS IP: {', '.join(next_servers)}")
                    break
                except (NameNotFound, ResolutionLimit):
                    raise
                except DNSError as error:
                    failures.append(str(error))
                    print(f"  -> {error}")
            if next_servers is None:
                detail = " / ".join(failures) or "Aynı alan adı ve sunucu daha önce sorgulandı."
                raise DNSError("DNS çözümlemesi tamamlanamadı: " + detail)
            servers = next_servers
        raise DNSError("DNS sorgusu adım sınırını aştı.")

    def _answer(self, domain, records, active):
        current = domain
        visited = set()
        ttl = float("inf")
        while current not in visited:
            visited.add(current)
            matches = [r for r in records if r.name == current and r.kind == A]
            if matches:
                ttl = min(ttl, min(r.ttl for r in matches))
                print(f"  -> A Kaydı Bulundu! (TTL: {ttl} saniye)")
                return list(dict.fromkeys(r.value for r in matches)), ttl
            aliases = [r for r in records if r.name == current and r.kind == CNAME]
            if not aliases:
                if current == domain:
                    return None
                addresses, target_ttl = self.resolve(current, active)
                return addresses, min(ttl, target_ttl)
            alias = aliases[0]
            print(f"  -> CNAME: {current} -> {alias.value}")
            ttl = min(ttl, alias.ttl)
            current = alias.value
        raise DNSError("CNAME kayıtlarında döngü bulundu.")

    def _referral(self, domain, zone, response, active):
        records = [r for r in response.authority if r.kind == NS
                   and (domain == r.name or domain.endswith("." + r.name))
                   and (not zone or r.name.endswith("." + zone))]
        if not records:
            return None
        next_zone = max((r.name for r in records), key=len)
        names = list(dict.fromkeys(r.value for r in records if r.name == next_zone))
        # Glue adresleri yanıtı veren üst bölgenin kapsamına göre kontrol edilir.
        addresses = list(dict.fromkeys(r.value for r in response.additional
                         if r.kind == A and r.name in names
                         and (not zone or r.name == zone or r.name.endswith("." + zone))))
        if not addresses:
            for name in names:
                print(f"  -> NS adresi ayrıca çözümleniyor: {name}")
                try:
                    found, _ = self.resolve(name, active)
                    addresses.extend(ip for ip in found if ip not in addresses)
                    if addresses:
                        break
                except ResolutionLimit:
                    raise
                except DNSError as error:
                    print(f"  -> {error}")
        if not addresses:
            raise DNSError("Yönlendirilen isim sunucularının IPv4 adresi bulunamadı.")
        return next_zone, addresses


def show_result(resolver, domain):
    try:
        addresses, _ = resolver.resolve(domain)
        print("\n" + "-" * 50)
        print(f"SONUÇ: {normalize_name(domain)} -> {', '.join(addresses)}")
        return True
    except DNSError as error:
        print(f"\nHATA: {error}")
        return False


def main():
    resolver = DNSResolver()
    if len(sys.argv) > 1:
        return 0 if show_result(resolver, sys.argv[1]) else 1
    print("DNS Resolver — çıkmak için q yazın.")
    while True:
        try:
            domain = input("\nAlan adı: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if domain.lower() in ("q", "quit", "exit"):
            return 0
        show_result(resolver, domain)   #sorguyu başlatır.


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nİşlem iptal edildi.")
        sys.exit(130)
