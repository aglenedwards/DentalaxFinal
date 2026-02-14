{pkgs}: {
  deps = [
    pkgs.imagemagick
    pkgs.pango
    pkgs.harfbuzz
    pkgs.glib
    pkgs.ghostscript
    pkgs.fontconfig
    pkgs.postgresql
    pkgs.openssl
  ];
}
