<!--
Dosya Yolu: REPO_ROOT/docs/TURKUAZ-RO-BRANDING.md
Amac: Launcher gorunur marka adi ve kalici teknik kimlikleri ayristirir
Modul - Markdown documentation
Version: 1.0.0-candidate
Aciklama: Turkuaz Ragnarok Online markasi, QA migration sinirlari ve installer politikasi
Bagimli Oldugu Katman: beam-ui/public/index.html | beam-core/src/config.rs | installer/windows
-->

# Turkuaz Ragnarok Online — Brand contract

**Gorunur urun adi:** Turkuaz Ragnarok Online

- Pencere / HTML basligi / paket urun adi: `Turkuaz Ragnarok Online`.
- Windows izole test kurulumunda: `Turkuaz Ragnarok Online QA`, acik `TEST MODU` etiketi.
- Temalar (kullanicinin gordugu isimler): Turkuaz Standart, Turkuaz Nostalji,
  Turkuaz Klasik, Turkuaz Modern.
- Teknik tema anahtarlari: `default`, `ragnar-legacy`, `ragnar-classic`,
  `levelup-modern`. Bu degerler onceki config ve WebView tercihlerini bozmamak
  icin degistirilmez. CSS path ve `beam.launcher.theme.v1` de aynen kalir.
- Patcher motoru, Rust crate adlari, `beam-patcher.exe`, Tauri bundle identifier
  `com.beampatcher.app`, mevcut QA GRF `levelup-qa.grf`, QA metadata
  `levelupgt.*` ve Velopack `levelupgt.beampatcher.qa` eski kalici/protokol
  kimlikleridir. Bunlarin toplu rename islemi desteklenen bir migration olmadan
  yapilamaz; yeni marka gorunur isimlerden ayridir.
- `LevelUp Games Beam QA` eski QA app name'i izolasyon icin taninmaya devam
  eder. Yeni `Turkuaz Ragnarok Online QA` da ayni QA guard uzerinden gecer.
  Her iki ad `qa_only` kurallarindan kacamaz.
- Browser offline demo haberleri sahte canli sunucu verisi veya uydurma Turkuaz
  URL'si kullanmaz. Canli haber ve guncelleme endpoint'leri ayrica dogrulanmadan
  degistirilmez.

## Windows dagitim kurali

BURAK-INS-001 degismez: TurkuazInstaller birincil, NSIS yalnizca private
yedektir. Eski Inno dosyasi tarihsel QA taslagidir; tek basina yayinlanamaz.
Onayli imzali Turkuaz paket/Windows native ve gercek Ragnarok client smoke
olmadan production release yoktur.

## Dogrulama

`python -m unittest discover -s tools/tests -p 'test_turkuaz_branding.py' -v`
statik marka/guvenlik kontratini denetler. Basarili kaynak testi Windows
WebView2, gercek istemci uyumlulugu veya kurulabilir production kaniti degildir.
