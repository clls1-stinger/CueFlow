{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  packages = with pkgs; [ uv ffmpeg pkg-config gcc gnumake patchelf ];
  LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath (with pkgs; [
    libglvnd libxkbcommon glib dbus fontconfig freetype nss nspr alsa-lib libdrm mesa libgbm expat libxshmfence libxkbfile stdenv.cc.cc.lib zlib zstd krb5
    xorg.libXcomposite xorg.libXdamage xorg.libXtst
    xorg.libxcb xorg.libX11 xorg.libXext xorg.libXrender xorg.libXi
    xorg.libXfixes xorg.libXcursor xorg.libXrandr xorg.libSM xorg.libICE
  ]);
}
