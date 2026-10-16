#!/usr/bin/env bash
# Build a small, local-files-only LGPL FFmpeg. No GPL or nonfree components.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION=8.1.3
SHA256=7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3
ARCHIVE="$ROOT/vendor/sources/ffmpeg-$VERSION.tar.xz"
mkdir -p "$ROOT/vendor/sources" "$ROOT/vendor/ffmpeg" "$ROOT/build"
if [ ! -f "$ARCHIVE" ]; then
  curl --fail --location --retry 3 "https://ffmpeg.org/releases/ffmpeg-$VERSION.tar.xz" -o "$ARCHIVE"
fi
if command -v sha256sum >/dev/null 2>&1; then
  printf '%s  %s\n' "$SHA256" "$ARCHIVE" | sha256sum --check -
else
  printf '%s  %s\n' "$SHA256" "$ARCHIVE" | shasum -a 256 --check -
fi
tar -xf "$ARCHIVE" -C "$ROOT/build"
cd "$ROOT/build/ffmpeg-$VERSION"
EXTRA=()
case "$(uname -s)" in
  MINGW*|MSYS*) EXTRA+=(--target-os=mingw32 --extra-ldflags=-static) ;;
  Darwin*) EXTRA+=(--extra-cflags=-mmacosx-version-min=12.0 --extra-ldflags=-mmacosx-version-min=12.0) ;;
esac
./configure --prefix="$ROOT/vendor/ffmpeg" \
  --disable-autodetect --disable-network --disable-doc --disable-debug \
  --disable-x86asm --disable-shared --enable-static --disable-avdevice \
  --disable-swscale --disable-programs --enable-ffmpeg --enable-ffprobe \
  --disable-everything \
  --enable-protocol=file,pipe \
  --enable-demuxer=mov,matroska,avi,asf,flv,mpegps,mpegts,ogg,wav,flac,mp3,aac,ac3,eac3,aiff \
  --enable-parser=aac,aac_latm,ac3,dca,flac,mpegaudio,opus,vorbis \
  --enable-decoder=aac,aac_fixed,aac_latm,ac3,eac3,mp3,mp3float,mp2,flac,opus,vorbis,pcm_s16le,pcm_s16be,pcm_s24le,pcm_s24be,pcm_s32le,pcm_f32le,pcm_f64le,pcm_u8,alac,dca,wmav1,wmav2 \
  --enable-encoder=pcm_s16le --enable-muxer=wav,pcm_s16le,null,matroska \
  --enable-filter=aresample,aformat,anull \
  "${EXTRA[@]}"
make -j "${CUEFLOW_BUILD_JOBS:-4}"
make install
cp COPYING.LGPLv2.1 "$ROOT/vendor/ffmpeg/"
cp ffbuild/config.log "$ROOT/vendor/ffmpeg/build-config.log"
# Executables at a stable, replaceable location; development archives stay excluded.
cp "$ROOT"/vendor/ffmpeg/bin/ffmpeg* "$ROOT/vendor/ffmpeg/"
cp "$ROOT"/vendor/ffmpeg/bin/ffprobe* "$ROOT/vendor/ffmpeg/"
