<!--
Dosya Yolu: REPO_ROOT/docs/CRASH-DIAGNOSTICS-PLAN.md
Amac: BEAM patcher ve bagli Ragnarok client icin gelecekteki yerel crash diagnostics isini planlar
Modul - Documentation Markdown
Version: 0.1.0
Aciklama: Tanimlanmis ancak uygulanmamis hata tanilama isi; issue tracker kapaliyken PR uzerinden izlenir
Bagimli Oldugu Katman: Tool / Documentation
-->
<!-- docs-meta: owner=LevelUpGT; reviewed=2026-10-23; source=GitHub-PR -->

# Future Backlog: BEAM crash diagnostics

**Durum:** PLANNED / NOT IMPLEMENTED.
**Oncelik:** P2 (later / optional).
**Yonetim:** GitHub Issues bu repoda kapali oldugundan bu dokuman ve bagli draft PR plan kaydidir. Kod veya production davranisi degistirilmemistir.

## Referans

- Eski Ragnarok istemcisinin Gravity Error / unhandled exception analizi:
  https://nn.ai4rei.net/dev/ref/roe/
- Ilgili diger proje backlog'lari:
  - RagnarokClient: https://github.com/LevelUpGT/RagnarokClient/issues/14
  - RagnarokPacketViewer: https://github.com/LevelUpGT/RagnarokPacketViewer/issues/46
  - RagnarokUnrealClient: https://github.com/LevelUpGT/RagnarokUnrealClient/issues/9

Referans sayfasindaki eski x86 adresleri/fonksiyonlari PACKETVER 20220406
istemcisine ya da Beam'in Rust/Tauri koduna dogrudan tasinmaz.

## Amaç ve sinirlar

BEAM'in kendi Rust/Tauri panic/exception loglarini, oyunun kendi Windows
Gravity Error/WER kayitlarindan ayri tutmak; patch sonrasinda olusan
eksik GRF/BMP/resource, checksum veya EXE surum uyusmazligi gibi sorunlari
salt okunur kanitla teshis etmeyi kolaylastirmak.

Bu plan oyun EXE'sine hook/injection yapilmasini, yetkisiz dump toplamayi,
normal kullaniciya otomatik telemetry yuklemeyi veya patch yayinini kapsamaz.

## Yapilacaklar

- [ ] beam-core/verifier/rollback, beam-patcher launcher ve beam-ui logging/error
      akislarini mevcut branch/PR/CI kanitiyla birlikte incele.
- [ ] Yerel, bounded ve hassas alanlari ayiklanmis support bundle semasi tasarla:
      Beam surumu, islem sonucu, patch kimligi, manifest hash, dosya SHA-256/size,
      rollback sonucu, hata kategorisi.
- [ ] Istek uzerine Ragnarok Gravity Error, Windows Event Log/WER ve resource
      yoklugu raporlarini salt okunur inceleme imkanini degerlendir.
- [ ] Yerel panic/exception raporu icin opt-in saklama, inceleme, export ve
      otomatik silme politikasi belirle. Memory dump varsayilan toplama disinda.
- [ ] Sentetik fixture ile missing-resource, checksum mismatch, invalid report,
      patch failure ve rollback yollarini test et.
- [ ] Cargo fmt, clippy, unit/contract testleri; Windows sandbox/GUI smoke ve
      gercek client dogrulamasini birbirine karistirmadan raporla.

## Kabul kriterleri / guvenlik

- Tum diagnosik ciktilar varsayilan olarak yerel ve sinirli boyutta.
  Credentials, personal data, private path ve packet payload maskelenir.
- Aksini kullanici acikca istemedikce veri ucuncu tarafa gonderilmez.
- Kapatildiginda THOR/BEAM apply, checksum, rollback ve UI davranisi aynidir.
- Windows-only smoke testi gercek Windows testidir; Linux CI sonucu yerine gecmez.
- Test yapilmadiysa NOT RUN denir. CI artifact'i production release degildir.

Standart: BURAK DEV STANDARD v3.0.0,
https://github.com/TurkuazSoft/DevStandards/blob/main/standards/documentation-lifecycle.md

Not: Bu backlog dogrulama gorevi basladiginda mevcut repo gercegine gore
ayri implementation PR'lari ile parcalanmalidir. Bu dokuman tamamlanma iddiasi degildir.
