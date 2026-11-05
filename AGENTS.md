<!--
Dosya Yolu: REPO_ROOT/AGENTS.md
Amac: beam-patcher projesinde merkezi DevStandards v3.0.0 uygulama ilkeleri
Modul - Documentation Markdown
Version: 3.0.0
Aciklama: Pinli standart ile mevcut oyun/runtime katmanlarini koruyan sozlesme
Bagimli Oldugu Katman: Documentation
-->

# beam-patcher - Project Agent Contract

**BURAK DEV STANDARD v3.0.0:** active, commit `72f6f642128fa29ec9a68b18881e9aa225739c9d`.
**Kaynak:** https://github.com/TurkuazSoft/DevStandards/tree/72f6f642128fa29ec9a68b18881e9aa225739c9d
**Teknoloji:** Rust patcher; profil `platforms/rust.md`.
**Roadmap:** yerel README, docs, acik issue/PR, surum ve mevcut uyumluluk kontratlari.

## Uygulama protokolu

- Ilk olarak mevcut branch, dosyalar, acik PR/issue ve son CI sonucunu kontrol et; "Devam et" son dogrulanmis adimdan ilerler.
- Calisan oyun ve istemci davranislarini koru, kapsam disi degisiklik, onaysiz release veya canli DB yazma yapma.
- Controller request/response; Service is kurallari; Repository/Model veri; Tool/Adapter dis baglanti; View arayuz; Language yerellestirme sorumlulugundadir. Native klasor yapisini bozma.
- Teknik dosyada destekleniyorsa Dosya Yolu, Amac, Modul - FileType, Version, Aciklama ve Bagimli Oldugu Katman kullan. JSON, YAML semantic, binary ya da engine assetlerini header ile bozma. Gercek olmayan mutlak yol uydurma; REPO_ROOT/goreli-yol.
- Secret, token, private key ve musteri/oyuncu verisini loglama. Magic string ve inline secret/config'i yayma.
- Gercek build, unit, contract, engine/Docker, client smoke ve gameplay kontrolunu ayri degerlendir. Islemeyen testi PASS sayma; test artifactini release sayma.
- Trusted self-hosted runner'a untrusted fork PR kodu gonderme. Baska repo kapsaminda izinsiz islem yapma.
- Merkezi repo private olabilir: dis katilimci erisemese bile bu ozet baglayicidir, okunmamis merkezi dokumana atifla gercek disi uyum iddia etme.

## Proje odak noktasi

Rust Cargo and update/checksum/security policy, rollback and patchlist parsing tests; binary packaging and release separate.

Bu dosya merkez standardi sabit commit ile pinler; yeni surumler kendiliginden gelmez, ayri PR gerekir.
