<!--
Dosya Yolu: REPO_ROOT/docs/BEAM-WINDOWS-GUI-PREVIEW.md
Amac: BEAM Windows onizleme paketinin guvenli yerel test talimati
Modul - Markdown
Version: 0.6.0
Aciklama: Gelistiriciye ozel deney plani, kapsam sinirlari ve test kabullerini aciklar
Bagimli Oldugu Katman: View | Language
-->
# BEAM Patcher - Windows Deney Laboratuvari

**Bu paket yalnizca gelistirme ve deney amaclidir.** Son kullaniciya dagitilmayacak; oyuncu icin updater, oyun baslatici veya final yayin hatti hedeflenmeyecektir. Grafik pencere eski \`thor_smoke.exe\` konsol aracindan ayridir.

- Dosya: \`BEAM-Patcher-Preview.exe\`
- İşletim sistemi: Windows 10/11 x64 (Microsoft Edge WebView2 Runtime gerekli)
- Güvenli önizleme: oyun yükleme, güncelleme, silme, GRF birleştirme, otomatik updater ve sunucu bağlantıları **kapalı**
- İşlev: \`THOR Dosyası Seç ve Test Et\` ile yerel **loose-client THOR** paketini BEAM'in Rust doğrulayıcısı kullanarak yalnızca kendi oluşturduğu geçici klasörde uygular, sonuç dosyalarını karşılaştırır, geçici klasörü temizler. Gerçek Ragnarok dizini istenmez.
- \`Sürüm Bilgisi\` backend komutunu çağırır. \`Kapat\` pencereyi kapatır.
- Legacy 2015 GRF-merging THOR arşivleri bu testten *bilerek* geçmez; eski 2015 Thor Patcher aynen korunur.

## Çalıştırma

1. GitHub Actions \`Windows GUI Preview\` testinin PASS olduğunu doğrula.
2. İlgili çalışmanın Artifacts bölümünden \`BEAM-Patcher-Windows-GUI-Preview\` ZIP'ini indir.
3. ZIP'i aç; \`BEAM-Patcher-Preview.exe\` üzerine çift tıkla. *Ragnarok oyun klasörüne kopyalama.*
4. \`THOR Dosyası Seç ve Test Et\` düğmesine basarak \`turkuaz-2022-hybrid-8cfc3211f8eb.thor\` gibi **yerel** bir THOR seç.
5. Test dosyaları geçici dizinde işlendiğinde sonuç uygulamada gösterilir. Gerçek istemci dosyaları değişmez.

Başlatmada pencere gelmezse \`Microsoft Edge WebView2 Runtime\` kurulumu / antivirüs uyarısı ve Windows Olay Görüntüleyicisi hata kaydını kontrol et. Windows CI derlemesi **tek başına** kullanıcı bilgisayarındaki açılışı doğrulamaz; kullanıcının ekran görüntüsü ile doğrulama gerekir.

## Önceki konsol aracıyla fark

\`thor_smoke.exe\` yalnızca komut satırı test aracıdır ve çift tıkla pencere açmaz. Bu proje gerçek bir **Tauri Windows desktop GUI** oluşturur. Bu laboratuvarda OYNA/Guncelle ve oyuncuya yayin ozellikleri kalici olarak kapsam disidir; yeni test arayuzu oyuncu launcher'ina donusturulmeyecektir.

Kaynak: `beam-preview/public/index.html`, `beam-preview/src/main.rs`, `beam-preview/tauri.conf.json`. Bagimsiz crate; eski BEAM Tauri UI yuklenmez. İstemciler: 2015 Thor, yeni 2015 rPatchur, 2022 rPatchur kanalları mevcut halleriyle çalışmaya devam eder.


## GitHub branch görünürlüğü (v0.2, yalnızca okuma)

- İstemci profili: Eski 2015 / Yeni 2015 / 2022 Hybrid — yalnızca arayüz üzerinde görüntülenir, oyun klasörü veya patch geçmişi değiştirilmez.
- Kaynak kod deposu: \`LevelUpRagnarok/beam-patcher\` veya \`b1glord/ROenglishRE\`. Uygulama GitHub'ın herkese açık branches API'sini salt-okunur sorgular; en fazla 100 dal ve 12 saniye istek zaman aşımı.
- Dal seçimi: branch adı, commit SHA ve korumalı dal bilgisi gösterilir. **Git checkout, branch içeriği indirme, yerel dosya değişimi, THOR uygulaması veya kanal değiştirme yapılmaz.**
- \`LevelUpGT/RagnarokClient\` özel depodur; kişisel token depolanmadan/uygulamaya gömülmeden bu sürümde dallarını göstermez. İleride güvenli yetkili servis üzerinden sorgulanabilir.
- Branch isimleri kullanıcı girdisi olarak serbest GitHub URL'sine çevrilmez. Backend API yalnızca iki allowlist reposunu sorgular; erişim kimliği paylaşılmaz.
- Kaynak ayrimi: Istemci profili oyun surumu deneyini; Git branch kaynak kodu ve commit'i gosterir. Manifestteki stable/beta alanlari yalnizca eski test semasi metadata'sidir; oyuncu dagitim kanali olarak kullanilmaz.
- README ve grafik arayüzdeki başlık: bu özellik henüz **profil bazlı uygulama kurulum izni** vermez. SHA-256/signed manifest ve yedekli kurulum olmadan **Güncelle/OYNA kapalıdır**.


## Manifest taslagi on-kontrolu (v0.3, salt okunur)

1. Istemci profilini ve GitHub kaynak deposunu sec; ilgili dallari getir ve bir branch sec.
2. **Yerel manifest taslagi sec ve incele** ile kendi hazirladigin JSON dosyasini ac. Oyun klasorune kurulmasi gerekmez.
3. Yalnizca manifest metadata alanlarinin secili **profil, kaynak depo, branch ve tam commit SHA** ile eslestigi kontrol edilir.
4. Eslesse dahi durum `PREVIEW_ONLY_UNSIGNED` kalir; gercek paket dosyasi okunmaz/indirilmez, hash hesaplanmaz, dijital imza kontrol edilmez, **Guncelle / OYNA kapali** kalir.
5. Manifest degistirildiginde veya secim degistirildiginde onceki sonuc tekrar kullanilmaz.

Taslak sema: `levelupgt.beam.manifest-preview.v1`. JSON alanlari:
`schema`, `profile`, `project`, `repository`, `branch`, `commit_sha`, `engine`, `channel`, `package_sha256`, `package_size`.

Profil-motor sozlesmesi:
- `old-2015` -> `legacy-thor`
- `new-2015` -> `rpatchur`
- `hybrid-2022` -> `rpatchur`

`package_sha256` burada **yalnizca beyan edilen 64 karakterlik bir alan** olarak denetlenir; indirilen paket byte'lariyla karsilastirilmaz. Bu taslak hicbir sekilde imzali/saglam bir guncelleme manifesti degildir. Ozel `LevelUpGT/RagnarokClient` deposu, yetkili servis olmadan bu on-kontrole kabul edilmez. Gercek imzali manifest semasi, guven zinciri, key rotation, SHA-256 paket karsilastirmasi ve transaction rollback sonradan ayri guvenlik adimi olarak tasarlanmalidir.


## Imzali manifest zarf altyapisi (v0.4, gelistirici onizlemesi)

Yeni Rust servisi yerel JSON zarfindaki `schema`, `key_id`, `payload_b64`, `signature_b64` alanlarini inceler. Base64 acilan **ham payload JSON baytlarinin** onune `LEVELUPGT-BEAM-SIGNED-PREVIEW-V1\\0` baglam prefix'i eklenir ve imza Ed25519 verify_strict ile denetlenir. Imza kontrolu basarili olsa bile paket dosyasi ve SHA-256 asla denetlenmez; kurulum kapali kalir.

**Su an gercek yayin anahtari kayitli degildir.** `config/trusted_signers.rs` icindeki `PRODUCTION_SIGNERS` bos ve Windows komutu herhangi bir imzayi kabul etmez. Sadece Rust unit testlerine `#[cfg(test)]` ile derlenen deterministik test ozel anahtari kullanilir; bu anahtar son kullanici EXE'sinde ve yayin guven zincirinde yer almaz.

Anahtar sahibinin resmen belirlenmesi, offline imzalama, anahtar rotasyonu/iptali ve gercek paket hash/transaction kontrolu sonraki zorunlu release gate'lerdir. Ozel RagnarokClient'a GitHub uygulama kimlik bilgisi gereklidir; ChatGPT GitHub baglantisinin yetkisi BEAM masaustune aktarilmaz.


### Imzali zarf kontrolu - Windows test UI

`Imzali manifest kontrolu (test)` sadece kullanicinin yerel JSON zarfini okur. Guvenilir yayin anahtari bos oldugundan gercek uygulama her zaman **ret** verir. Unit testlerinde gecici test anahtari ile kriptografik dogrulama sinanir. Imzanin dogrulanmasi, paket SHA-256'sinin dogrulanmasi veya yukleme izninin verilmesi demek degildir.

## Gelistirici deney plani (v0.5, kurulum yok)

- `Deney planini olustur` butonu, secilen istemci profili, allowlist GitHub deposu, branch ve tam 40 karakter commit SHA uzerinden JSON plan uretir.
- Plan `levelupgt.beam.experiment-plan.v1` semasini kullanir. `audience=DEVELOPER_ONLY`, `status=PLAN_ONLY` ve `source_verification=USER_SELECTION_UNVERIFIED` olarak gelir. Plan derlenirken harici API'ye gidilmez; sectiginiz SHA bagimsiz dogrulanmis sayilmaz.
- Plan her zaman 7 adimi `NOT_RUN` seklinde listeler: branch_metadata, manifest_metadata, ed25519_signature, package_sha256, thor_sandbox, in_game_client, rollback_recovery.
- THOR sandbox veya manifest komutunu ayni oturumda ayrica basariyla calistirmis olmak, bu **plan** icindeki `NOT_RUN` durumlarini otomatik PASS yapmaz. Plan ile olculmus test sonucu birbirinden ayridir. Ayrica audit kayit sistemi gelene kadar belge test raporu sayilmaz.
- `installation_allowed=false`, `game_launch_allowed=false`, `player_distribution_allowed=false` alanlari kesin kuraldir.
- Secim degisince eski plan gorunmez; halen devam eden cevap gelse bile eski secimin sonucu tekrar kullanilmaz.
- Cikti yalnizca pencere icindeki secilebilir JSON metnidir; diske otomatik kaydedilmez, oyun dosyalari degistirilmez, Git checkout veya patch uygulanmaz.
- `old-2015` icin motor `legacy-thor`, `new-2015` ve `hybrid-2022` icin `rpatchur` olarak raporlanir. Bu uyumlulugun gercek istemcide kanitlandigi anlamina gelmez.

### Regresyon kontrolleri

Windows GUI Preview CI iki katmani dogrular:

1. Node UI testleri: profil/branch secimi, tam SHA, diger repo yanitlarini eleme, rapor gecersizlestirme ve `NOT_RUN` sunumu.
2. Rust servis testleri: allowlist depo, guvenli branch formati, tam SHA, profil/motor eslesmesi ve kurulum/oyun/dagitim izinlerinin tamamen kapali olmasi.

Yerel Windows GUI icinde GitHub API erisimi veya Ragnarok'a gercek giris testi CI basarisi ile otomatik dogrulanmis sayilmaz.


## Yerel paket SHA-256 on-kontrolu (v0.6.0)

`Yerel paket SHA-256 kontrolu` butonu once imzasiz manifest JSON dosyasini, sonra yerel paket dosyasini ister. BEAM secili profili, kaynak depoyu, branch'i ve tam commit SHA'yi manifestle karsilastirir. Sonra dosya **yalnizca okunur**, SHA-256 64 KiB bloklarla hesaplanir, gercek boyut ve hash manifestteki beyanla karsilastirilir.

**GUVENLIK SINIRI:** Bu testte manifest imzasizdir. Eslesme, imzasiz beyanin gercek dosyayla tutarli oldugunu gosterir; paketin guvenilir veya yayin icin uygun oldugu anlamina gelmez. `signature_verified=false` ve `installation_allowed=false` zorunludur. Oyuna kurulum, dosya cikartma, GRF degistirme, guncelleme veya OYNA islemi yapilmaz. Gercek imzali yayin anahtarlari yine bos kalir.

CI testleri: gercek paket ozetinin eslesmesi; ayni boydaki bozulmus paket; farkli boyut; yanlis profil; eksik/bozuk dosya; kaynak secimi degisince gecersizlesme; Windows GUI pencere acilisi. Bu test oyuncuya acik guncellemenin onayi degildir.

**Kaynak repo taşınması (2026-11-05):** GUI'nin BEAM branch API allowlist kaynağı `LevelUpRagnarok/beam-patcher` olarak güncellendi. `LevelUpGT/beam-patcher` için GitHub yönlendirmelerine güvenilmiyor; read-only HTTPS istemcisi redirect kabul etmiyor. Eski `levelupgt.*` JSON/manifest şema kimlikleri geriye dönük uyumluluk için korunur. GitHub-hosted Windows CI bu commit için ayrıca doğrulanmalıdır; gerçek istemcide ağ testi ayrıca yapılmalıdır.
