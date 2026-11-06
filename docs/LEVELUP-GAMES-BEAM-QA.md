<!--
Dosya Yolu: docs/LEVELUP-GAMES-BEAM-QA.md
Amac: Sac Modelleri ve LevelUp Games videosu icin Beam test akisinin sinirlarini tanimlar
Modul - Documentation Markdown
Version: 0.2.0
Aciklama: Kaynak kodundan yerel medya uretme ve offline Beam paketlerini test etme
Bagimli Oldugu Katman: Beam UI | RagnarokClient PR #17
-->

# LevelUp Games / Sac Modelleri - Beam QA

Bu dokuman **QA** amaclidir, yayinlama veya mevcut oyuncu dosyalarini
guncelleme talimati degildir. Client veya patch feed varsayilani degismez.

## 1. LevelUp Games videosunu Git kaynak kodundan uret

Bu repoda tools/render_levelup_games_intro.py bulunur.
Sistemde FFmpeg / libx264 / aac / drawtext kuruluysa:

    python ./tools/render_levelup_games_intro.py

Cikti: beam-ui/public/assets/levelup-games-intro.mp4.

MP4 dosyasi indirilmeksizin yeni bir QA videosu kaynak kodundan uretilir.
Onceden mevcut dosyanin ustune yazilmaz. Uretilen dosya, RagnarokClient'da
sabit SHA256 ile kayitli **orijinal** LevelUp Games videosundan farkli
bir yerel QA renderidir. Bu surumle EXE'ye video gomulmez.

Mevcut Beam config.yml app bolumundeki ilgili alanlar:

    app:
      video_background_enabled: true
      video_background_file: "assets/levelup-games-intro.mp4"

Yukardaki alanlar mevcut app alanina birlestirilir; tek basina gecerli
tam config degildir. Beam medya yuklemesi ve istemci davranisi gercek
Windows sisteminde ayrica smoke edilmelidir. UI background videosu,
Windows EXE splash animasyonuyla ayni sey degildir.

## 2. Repo'dan Sac Modelleri ve Beam tam QA derlemesi

Normal kaynak:
`LevelUpGT/RagnarokClient` PR #17 (QA source branch).

Windows / RagnarokClient repo root:

    .\tools\QA-BEAM-SAC-MODELLERI.ps1

**Harici ZIP, -ArchivePath veya manuel MP4 girdisi yoktur.**
Tek komut, Git'te takip edilen `assets/hair-pack/84` 336 ACT/SPR kaynaklarini
dogrular, client release planini kontrol eder, LevelUp Games videosunu
kaynak kodundan yeniden uretir, Beam Rust kaynagini sabit commit'ten
derler, sonra BEAM v1 336 dosyali QA arsivini olusturur.

On kosullar: Python 3, Git, FFmpeg, Rust/Cargo.
Beam source checkout / Cargo dependency fetch internet gerektirir, ama
hangi kaynak ZIP'inin bulunacagi operator makinesinden sorulmaz.

**Su anki engel:** Gercek 336 ACT/SPR binary + `qa-manifest.json`
henüz PR #17 Git dalina commit edilmedi. Bu nedenle repo tam derlemesi
`REPOSITORY_HAIR_ASSETS_MISSING` ile bilerek durur; sentetik dosyalar
ile gercek oyun testi iddia edilemez.

Beam v1 QA cikti yeri:
`RagnarokClient/build/beam-qa/2022/hair-pack-84.beam`.
Video yeri:
`RagnarokClient/build/beam-qa/2022/levelup-games-intro.mp4`.

**KRITIK UYUMLULUK:** Ragnarok 20220406 client Korece GRF dosya adlari
icin CP949 bekleyebilir. Mevcut Beam GRF writer `filename.as_bytes()`
ile UTF-8 yazar. CP949 oyun gorunurlugu **dogrulanmadi**.
Ayrica mevcut hairstyle.grf ile isim cakismalari bulunuyor.
hair-pack-84.beam aktif GRF veya patchlist'e otomatik uygulanmaz.

## 3. Public 2022 Beam dagitimi kapali kalir

b1glord/ragnarokclientpatch/2022/beam/channel-policy.json:
ready=false, publish_allowed=false, published_patch_count=0.
Bu QA akisi policy, patchlist, client EXE, DATA.INI veya GRF degistirmez.

Kaynak PR'ler:
- https://github.com/LevelUpGT/RagnarokClient/pull/17
- https://github.com/LevelUpGT/RagnarokServer/pull/241

Ucuncu taraf sac sprite'larinin yeniden dagitim izni netlesmeden
binary assetlerin public repoya eklenmesi ertelenmistir.
