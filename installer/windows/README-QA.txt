Turkuaz Ragnarok Online QA - TEST ONLY
========================================

This installer contains only the Beam launcher/patcher and a safe configuration.
It does NOT contain game files, a licensed Ragnarok client, live update URLs,
any GRF content or an approved 2022 patch channel.

1. Make a new, isolated test directory. Never select the real game directory.
2. Launch Beam QA, select the isolated directory when prompted.
3. Current default manual patch target: levelup-qa.grf (independent QA file).
4. Settings > Appearance switches between four visual themes.
5. To apply a local test archive, use Manual Patch and select BEAM, THOR,
   GPF or RGZ. Do not use unknown archives or files from third parties.
6. The remote patch list deliberately points to 127.0.0.1:9/disabled.
   No patch will download automatically in this installed QA profile.
7. Changing to a live feed, game EXE, client GRF or production patch target
   requires separate verified 20220406 identity, GRF loader/readback,
   backup/rollback and a signed/approved patch manifest.

This package is an installable TEST ARTIFACT, NOT A RELEASE.
It is not code-signed. Windows may warn when running unsigned installers.

Uninstall does not erase your customized config.yml, test GRFs or external
game files. Delete test files only after manually confirming their location.
