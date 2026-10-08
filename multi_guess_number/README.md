# Ag Programlama - Sayi Tahmin Oyunu

Sunucu, rakamlari birbirinden farkli dort basamakli bir sayi tutar. Uc oyuncu
sirasiyla tahmin yapar ve her oyuncunun 10 hakki vardir.

- `+`: Dogru rakam, dogru konum
- `-`: Dogru rakam, yanlis konum
- Tahmini yapan oyuncu kendi tahminini gorur; diger oyuncular `****` gorur.
- Sunucunun puan cevabi butun oyuncular tarafindan gorulur.

## Puanlama sistemi

- Her oyuncu oyuna **1000 puanla** baslar.
- Her gecerli tahmin puani **50 azaltir**.
- Dogru rakam ve dogru konum (`+`): **25 puan**
- Dogru rakam fakat yanlis konum (`-`): **10 puan**
- Sayiyi bilme bonusu: **500 puan**
- Erken bitirme bonusu: kalan her hak icin **25 puan**

Her tahminden sonra guncel puan siralamasi tum oyunculara gosterilir. Bir oyuncu
ayni tahmini tekrar yapamaz. Gecersiz ve tekrarlanan tahminlerde puan azalmaz.

## Calistirma

Ayni bilgisayarda dort ayri PowerShell penceresi acin ve sirayla sunlari calistirin:

```powershell
python server.py
python client1.py
python client2.py
python client3.py
```

Farkli bilgisayarlarda calistirmak icin uc istemci dosyasindaki `SERVER_HOST`
degerini sunucuyu calistiran bilgisayarin yerel IP adresiyle degistirin. Guvenlik
duvari TCP `5000` portuna izin vermelidir.

Ornek: Tutulan sayi `4271`, tahmin `4178` ise sonuc `+2 -1` olur.
