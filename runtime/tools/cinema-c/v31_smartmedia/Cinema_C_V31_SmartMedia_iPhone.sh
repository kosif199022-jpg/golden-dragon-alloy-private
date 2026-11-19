#!/bin/sh
# Cinema C V31.0 — Smart Media — iPhone / a-Shell
# Evolves V30.1 LoginGate: smart Instagram posts, photos/carousels, gallery-dl,
# explicit dependency updates, diagnostics, and relative cookies path fix.
# Recovery release based on historically proven behavior:
# - V17 UX: c -> URL -> quality -> Photos/Files -> exact downloaded file
# - V11/Cinema_Photos output discovery: unique work directory, no --print-to-file
# - Manual Photos: create a separate Photos-safe MP4, then open it
#
# Photos SAFE normalization:
# - H.264 video
# - AAC audio
# - yuv420p pixel format
# - MP4 +faststart
# - original download preserved
# - no ffprobe dependency

set -u

APP='Cinema C'
VERSION='31.0-SmartMedia-iPhone'

HOME_DIR=${HOME:-.}
BIN_DIR="$HOME_DIR/Documents/bin"
DOWNLOAD_DIR=${CINEMA_DOWNLOAD_DIR:-"$HOME_DIR/Documents/Cinema_Downloads"}
STATE_DIR="$HOME_DIR/Documents/.cinema"

CONNECTIONS=${CINEMA_CONNECTIONS:-8}
INPUT=''
INSTALL=0
COOKIES=''
YTDLP=''
SAVE_MODE='ask'   # ask | photos | files
OUTPUT_FILE=''
PHOTOS_SAFE_FILE=''
WORK_DIR=''

# Facebook profile batch state (isolated from the proven single-video path)
FB_PROFILE_ID=''
FB_BATCH_DIR=''
FB_LINKS_FILE=''
FB_ARCHIVE_FILE=''
FB_SCAN_DIR=''
FB_SOCKET_TIMEOUT=${CINEMA_FB_SOCKET_TIMEOUT:-6}
FB_HARD_TIMEOUT=${CINEMA_FB_HARD_TIMEOUT:-10}
FB_IMPERSONATE=''
FB_LOGIN_REQUIRED=0
FB_DOCTOR=0
DOCTOR=0
SETUP=0
SMART_MODE=''   # '' | smart | gallery
GALLERY=''
GALLERY_MODE=''
YTDLP_MODE='binary'
GALLERY_OUTPUT_DIR=''
GALLERY_COUNT=0
GALLERY_IMAGES=0
GALLERY_VIDEOS=0

say() { printf '%s\n' "$*"; }
err() { printf 'ERROR: %s\n' "$*" >&2; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

usage() {
  say 'Cinema C V31 — Smart Media — iPhone / a-Shell'
  say ''
  say 'Quick start:'
  say '  c                                 # paste URL, choose a mode'
  say '  c --smart "INSTAGRAM_POST_URL"      # photos/videos/carousels'
  say '  c --gallery "INSTAGRAM_POST_URL"    # fetch with gallery-dl'
  say '  c --files --smart "URL"             # save in Files'
  say ''
  say 'Install/update:'
  say '  sh Cinema_C_V31_SmartMedia_iPhone.sh --install'
  say '  c --setup     # explicitly install/update yt-dlp + gallery-dl via pip'
  say '  c --doctor    # dependency check, no network needed'
  say ''
  say 'Other options: --photos, --files, --cookies PATH, --output DIR,'
  say '               -N 1..16, --fb-doctor, --version, --help'
  say ''
  say 'Facebook numeric-ID profile URL: best-effort public reels/videos scan.'
  say 'Instagram photo or carousel: gallery-dl required; yt-dlp is video-only.'
  say 'Respect permissions and platform access; private posts need authorized access.'
}

cleanup() {
  status=$?
  if [ -n "${WORK_DIR:-}" ] && [ -d "$WORK_DIR" ]; then
    rm -rf "$WORK_DIR" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

find_ytdlp() {
  if have yt-dlp && yt-dlp --version >/dev/null 2>&1; then
    YTDLP='yt-dlp'
    YTDLP_MODE='binary'
    return 0
  fi
  if have yt_dlp && yt_dlp --version >/dev/null 2>&1; then
    YTDLP='yt_dlp'
    YTDLP_MODE='binary'
    return 0
  fi
  if have python3 && python3 -m yt_dlp --version >/dev/null 2>&1; then
    YTDLP='python3'
    YTDLP_MODE='module'
    return 0
  fi
  return 1
}

run_ytdlp() {
  if [ "$YTDLP_MODE" = 'module' ]; then
    "$YTDLP" -m yt_dlp "$@"
  else
    "$YTDLP" "$@"
  fi
}

find_gallery() {
  GALLERY=''
  GALLERY_MODE=''
  if have gallery-dl && gallery-dl --version >/dev/null 2>&1; then
    GALLERY='gallery-dl'
    GALLERY_MODE='binary'
    return 0
  fi
  if have python3 && python3 -m gallery_dl --version >/dev/null 2>&1; then
    GALLERY='python3'
    GALLERY_MODE='module'
    return 0
  fi
  return 1
}

run_gallery() {
  if [ "$GALLERY_MODE" = 'module' ]; then
    "$GALLERY" -m gallery_dl "$@"
  else
    "$GALLERY" "$@"
  fi
}

install_or_update_deps() {
  if ! have python3; then
    err 'Python3 is missing. a-Shell needs Python to install these packages.'
    return 1
  fi
  say '[C] Installing/updating yt-dlp and gallery-dl (explicit request)...'
  if python3 -m pip install --user --upgrade yt-dlp gallery-dl; then
    say '[C] Packages updated. Run: c --doctor'
    return 0
  fi
  err 'pip installation failed; check a-Shell Python/pip and network access.'
  return 1
}

show_doctor() {
  say 'Cinema C V31 — Doctor'
  say '-----------------------'
  if find_ytdlp; then
    v=$(run_ytdlp --version 2>/dev/null || printf '?')
    say "yt-dlp: $v ($YTDLP_MODE)"
  else
    say 'yt-dlp: MISSING'
  fi
  if find_gallery; then
    v=$(run_gallery --version 2>/dev/null || printf '?')
    say "gallery-dl: $v ($GALLERY_MODE)"
  else
    say 'gallery-dl: MISSING (required for Instagram photos/carousels)'
  fi
  if have ffmpeg; then say 'ffmpeg: available'; else say 'ffmpeg: MISSING (required for Photos SAFE and MP3)'; fi
  if have python3; then say 'python3: available'; else say 'python3: missing'; fi
  if have open; then say 'iOS open helper: available'; elif have view; then say 'view helper: available'; else say 'automatic Photos share: unavailable'; fi
  say "Files folder: $DOWNLOAD_DIR"
  say 'To add missing packages run: c --setup'
}

validate_connections() {
  case "$CONNECTIONS" in
    ''|*[!0-9]*)
      err '-N must be a whole number from 1 to 16.'
      exit 1
      ;;
  esac
  [ "$CONNECTIONS" -ge 1 ] && [ "$CONNECTIONS" -le 16 ] || {
    err '-N must be from 1 to 16.'
    exit 1
  }

  case "$FB_SOCKET_TIMEOUT" in
    ''|*[!0-9]*)
      err 'CINEMA_FB_SOCKET_TIMEOUT must be a whole number.'
      exit 1
      ;;
  esac
  [ "$FB_SOCKET_TIMEOUT" -ge 3 ] && [ "$FB_SOCKET_TIMEOUT" -le 15 ] || {
    err 'CINEMA_FB_SOCKET_TIMEOUT must be from 3 to 15 seconds.'
    exit 1
  }

  case "$FB_HARD_TIMEOUT" in
    ''|*[!0-9]*)
      err 'CINEMA_FB_HARD_TIMEOUT must be a whole number.'
      exit 1
      ;;
  esac
  [ "$FB_HARD_TIMEOUT" -ge 2 ] && [ "$FB_HARD_TIMEOUT" -le 30 ] || {
    err 'CINEMA_FB_HARD_TIMEOUT must be from 2 to 30 seconds.'
    exit 1
  }

}

validate_cookie_file() {
  [ -z "$COOKIES" ] && return 0

  # Facebook scans change directory. Always use an absolute path to cookies.
  case "$COOKIES" in
    /*) ;;
    *) COOKIES="$(pwd)/$COOKIES" ;;
  esac

  [ -f "$COOKIES" ] || {
    err "Cookies file not found: $COOKIES"
    return 1
  }

  first_line=$(sed -n '1p' "$COOKIES" 2>/dev/null || true)
  case "$first_line" in
    '# Netscape HTTP Cookie File'|'# HTTP Cookie File')
      return 0
      ;;
  esac

  warn 'Cookies file does not start with a Netscape/Mozilla cookie header.'
  say 'Expected first line: # Netscape HTTP Cookie File'
  return 1
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --install)
        INSTALL=1
        shift
        ;;
      --setup|--update)
        SETUP=1
        shift
        ;;
      --doctor)
        DOCTOR=1
        shift
        ;;
      --smart)
        SMART_MODE='smart'
        shift
        ;;
      --gallery)
        SMART_MODE='gallery'
        shift
        ;;
      --photos)
        SAVE_MODE='photos'
        shift
        ;;
      --files)
        SAVE_MODE='files'
        shift
        ;;
      -N)
        [ "$#" -ge 2 ] || { err '-N needs a number'; exit 1; }
        CONNECTIONS=$2
        shift 2
        ;;
      --cookies)
        [ "$#" -ge 2 ] || { err '--cookies needs a file'; exit 1; }
        COOKIES=$2
        shift 2
        ;;
      --output)
        [ "$#" -ge 2 ] || { err '--output needs a folder'; exit 1; }
        DOWNLOAD_DIR=$2
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      --fb-doctor)
        FB_DOCTOR=1
        shift
        ;;
      --version)
        say "$APP $VERSION"
        exit 0
        ;;
      -*)
        err "Unknown option: $1"
        exit 1
        ;;
      *)
        [ -z "$INPUT" ] && INPUT=$1
        shift
        ;;
    esac
  done
  validate_connections
  validate_cookie_file || exit 1
  case "$DOWNLOAD_DIR" in
    /*) ;;
    *) DOWNLOAD_DIR="$(pwd)/$DOWNLOAD_DIR" ;;
  esac
}

install_self() {
  mkdir -p "$BIN_DIR" || { err "Cannot create $BIN_DIR"; exit 1; }
  cp "$0" "$BIN_DIR/c" || { err 'Install failed'; exit 1; }
  chmod +x "$BIN_DIR/c" 2>/dev/null || true
  have rehash && rehash >/dev/null 2>&1 || true
  say "OK: $APP $VERSION installed."
  say 'From now on type: c'
  say 'Photos SAFE needs no Shortcut; ffmpeg builds a compatibility MP4 first.'
  say 'Instagram photos/carousels use gallery-dl; run c --setup if it is missing.'
  say 'Facebook profile mode is best-effort; login redirects are detected before bulk scanning.'
  say 'If profile discovery fails, run: c --fb-doctor'
}

prompt_url() {
  if [ -z "$INPUT" ]; then
    say ''
    printf 'Paste video URL: '
    IFS= read -r INPUT || INPUT=''
  fi

  INPUT=$(printf '%s' "$INPUT" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
  case "$INPUT" in
    http://*|https://*) ;;
    *)
      err 'Invalid URL'
      exit 1
      ;;
  esac
}



is_instagram_post() {
  case "$INPUT" in
    https://instagram.com/p/*|https://www.instagram.com/p/*|https://m.instagram.com/p/*|http://instagram.com/p/*|http://www.instagram.com/p/*)
      return 0 ;;
  esac
  return 1
}

instagram_post_slug() {
  slug=$(printf '%s\n' "$INPUT" | sed -n 's#^.*/p/\([^/?][^/?]*\).*#\1#p' | tr -cd 'A-Za-z0-9_-')
  [ -n "$slug" ] || slug='post'
  printf '%s' "$slug"
}

choose_gallery_destination() {
  [ "$SAVE_MODE" = 'ask' ] || return 0
  say ''
  say 'Gallery destination:'
  say ' 1) Photos — open media for iOS Share -> Save Image/Video'
  say ' 2) Files — save entire album (default)'
  printf 'Number [2]: '
  IFS= read -r dest_choice || dest_choice=''
  case "$dest_choice" in
    1) SAVE_MODE='photos' ;;
    2|'') SAVE_MODE='files' ;;
    *) err 'Wrong destination choice.'; return 1 ;;
  esac
}

# The gallery downloader supports multiple assets. A dedicated work directory
# makes it possible to count and move exactly the downloaded media (no guessing).
run_gallery_download() {
  if ! find_gallery; then
    err 'Instagram image/carousel support requires gallery-dl.'
    say 'Install it from a-Shell using: c --setup'
    say 'Or: python3 -m pip install --user --upgrade gallery-dl'
    return 1
  fi

  [ -n "$WORK_DIR" ] || new_work_dir
  gallery_work="$WORK_DIR/gallery"
  mkdir -p "$gallery_work" || return 1
  say ''
  say '[C] Gallery mode: downloading images, videos, and carousel assets...'

  set -- --no-input -D "$gallery_work" --no-mtime --retries 3
  [ -z "$COOKIES" ] || set -- "$@" --cookies "$COOKIES"
  set -- "$@" "$INPUT"
  # An extractor may exit nonzero after downloading some gallery items.
  # Never claim success unless at least one completed media asset is present.
  gallery_rc=0
  run_gallery "$@" || gallery_rc=$?
  if ! move_gallery_results "$gallery_work"; then
    err 'gallery-dl did not produce any complete media files.'
    if [ -z "$COOKIES" ]; then
      say 'If the post requires login, provide a Netscape cookies file:'
      say '  c --cookies cookies.txt --smart "POST_URL"'
    fi
    return 1
  fi
  if [ "$gallery_rc" -ne 0 ]; then
    warn 'gallery-dl reported some errors; saved the assets it could retrieve.'
  fi
  return 0
}

move_gallery_results() {
  gallery_work=$1
  count=0
  imgs=0
  vids=0
  for f in "$gallery_work"/*; do
    [ -f "$f" ] || continue
    case "$f" in
      *.jpg|*.JPG|*.jpeg|*.JPEG|*.png|*.PNG|*.webp|*.WEBP|*.gif|*.GIF|*.heic|*.HEIC|*.avif|*.AVIF|*.mp4|*.MP4|*.mov|*.MOV|*.m4v|*.M4V|*.webm|*.WEBM|*.mkv|*.MKV)
        count=$((count + 1))
        case "$f" in
          *.mp4|*.MP4|*.mov|*.MOV|*.m4v|*.M4V|*.webm|*.WEBM|*.mkv|*.MKV) vids=$((vids + 1)) ;;
          *) imgs=$((imgs + 1)) ;;
        esac
        ;;
    esac
  done
  [ "$count" -gt 0 ] || return 1

  stamp=$(date '+%Y%m%d_%H%M%S' 2>/dev/null || printf 'job')
  if is_instagram_post; then
    tag="Instagram_$(instagram_post_slug)"
  else
    tag='Cinema_Gallery'
  fi
  GALLERY_OUTPUT_DIR="$DOWNLOAD_DIR/${tag}_${stamp}_$$"
  mkdir -p "$GALLERY_OUTPUT_DIR" || return 1

  moved=0
  for f in "$gallery_work"/*; do
    [ -f "$f" ] || continue
    case "$f" in
      *.jpg|*.JPG|*.jpeg|*.JPEG|*.png|*.PNG|*.webp|*.WEBP|*.gif|*.GIF|*.heic|*.HEIC|*.avif|*.AVIF|*.mp4|*.MP4|*.mov|*.MOV|*.m4v|*.M4V|*.webm|*.WEBM|*.mkv|*.MKV)
        mv "$f" "$GALLERY_OUTPUT_DIR/" && moved=$((moved + 1)) || warn "Could not move: ${f##*/}"
        ;;
    esac
  done
  [ "$moved" -gt 0 ] || return 1
  GALLERY_COUNT=$moved
  GALLERY_IMAGES=$imgs
  GALLERY_VIDEOS=$vids
  say ''
  say "[C] Saved $GALLERY_COUNT media assets ($GALLERY_IMAGES image(s), $GALLERY_VIDEOS video(s))."
  say "[C] Folder: $GALLERY_OUTPUT_DIR"
  finish_gallery
  return 0
}

finish_gallery() {
  case "$SAVE_MODE" in
    ask)
      say 'Saved in Files. Open the folder and Share -> Save Image/Save Video.'
      ;;
    files)
      say 'Saved in Files (selected).'
      ;;
    photos)
      # iOS sharing is explicitly user-confirmed in the system share sheet.
      if [ "$GALLERY_COUNT" -eq 1 ]; then
        for asset in "$GALLERY_OUTPUT_DIR"/*; do
          [ -f "$asset" ] || continue
          case "$asset" in
            *.mp4|*.MP4|*.mov|*.MOV|*.m4v|*.M4V|*.webm|*.WEBM|*.mkv|*.MKV)
              if have ffmpeg; then
                OUTPUT_FILE=$asset
                if make_photos_safe_copy; then
                  open_exact_video_for_photos && return 0
                  say "Photos-safe MP4 ready in Files: $PHOTOS_SAFE_FILE"
                  return 0
                fi
                warn 'Could not convert gallery video for Photos; keeping original.'
              fi
              ;;
          esac
          say '[C] Opening media to share to Photos (choose Save Image/Video).'
          if have open; then
            open "$asset" >/dev/null 2>&1 && return 0
          fi
          if have view; then
            view "$asset" >/dev/null 2>&1 && return 0
          fi
        done
      fi
      say 'For a multi-file album, use Files to select the photos/videos and Share.'
      say "$GALLERY_OUTPUT_DIR"
      ;;
  esac
}

smart_download() {
  # Instagram feed posts may hold pictures *and* videos. gallery-dl first
  # preserves the whole carousel, while yt-dlp alone can only save videos.
  choose_gallery_destination || return 1
  if is_instagram_post && find_gallery; then
    run_gallery_download && return 0
    warn 'Gallery extractor failed. Trying yt-dlp for possible videos...'
  fi
  [ -n "$YTDLP" ] || { err 'yt-dlp missing. Run: c --setup'; return 1; }
  choose_destination video
  sel=$(best_selector)
  run_download "$sel" merge && { finish; return 0; }
  return 1
}

is_facebook_profile_url() {
  case "$INPUT" in
    *facebook.com/profile.php\?*id=[0-9]*|*facebook.com/profile.php\?id=[0-9]*)
      return 0
      ;;
  esac
  return 1
}

extract_facebook_profile_id() {
  FB_PROFILE_ID=$(printf '%s\n' "$INPUT" | sed -n 's/.*[?&]id=\([0-9][0-9]*\).*/\1/p' | sed -n '1p')
  [ -n "$FB_PROFILE_ID" ]
}

fb_profile_paths() {
  FB_BATCH_DIR="$DOWNLOAD_DIR/Facebook_Profile_$FB_PROFILE_ID"
  FB_LINKS_FILE="$STATE_DIR/facebook_profile_${FB_PROFILE_ID}_links.txt"
  FB_ARCHIVE_FILE="$STATE_DIR/facebook_profile_${FB_PROFILE_ID}_archive.txt"
  FB_SCAN_DIR="$STATE_DIR/facebook_scan_${FB_PROFILE_ID}_last"

  # Keep the most recent scan artifacts only. They are useful for diagnosis,
  # but old scans should not accumulate forever.
  rm -rf "$FB_SCAN_DIR" 2>/dev/null || true
  mkdir -p "$FB_BATCH_DIR" "$FB_SCAN_DIR" "$STATE_DIR" || return 1
}

detect_fb_impersonation() {
  FB_IMPERSONATE=''

  targets=$(run_ytdlp --list-impersonate-targets 2>/dev/null || true)

  # Jev Q012 favored Safari before Chrome. More importantly, V30 never
  # impersonates on the first attempt; this target is fallback-only.
  if printf '%s\n' "$targets" | grep -E '^Safari([[:space:]-]|$)' | grep -Evi 'unavailable|not available' >/dev/null 2>&1; then
    FB_IMPERSONATE='safari'
    return 0
  fi

  if printf '%s\n' "$targets" | grep -E '^Chrome([[:space:]-]|$)' | grep -Evi 'unavailable|not available' >/dev/null 2>&1; then
    FB_IMPERSONATE='chrome'
    return 0
  fi

  return 1
}

facebook_doctor() {
  say 'Cinema Facebook Doctor'
  say '----------------------'
  say "Cinema: $VERSION"

  if ! find_ytdlp; then
    say 'yt-dlp: NOT FOUND'
    return 1
  fi

  ver=$(run_ytdlp --version 2>/dev/null || printf 'unknown')
  say "yt-dlp: $ver"
  say "socket timeout: ${FB_SOCKET_TIMEOUT}s"
  if have timeout; then
    say "hard timeout helper: timeout (${FB_HARD_TIMEOUT}s)"
  elif have gtimeout; then
    say "hard timeout helper: gtimeout (${FB_HARD_TIMEOUT}s)"
  else
    say 'hard timeout helper: unavailable; yt-dlp socket/retry bounds only'
  fi

  if detect_fb_impersonation; then
    say "browser impersonation: available ($FB_IMPERSONATE)"
  else
    say 'browser impersonation: unavailable (not fatal)'
  fi

  if have ffmpeg; then
    say 'ffmpeg: available'
  else
    say 'ffmpeg: unavailable'
  fi

  say ''
  say 'For profile-wide Facebook discovery, a login wall may require:'
  say '  c --cookies cookies.txt "PROFILE_URL"'
  say 'The cookies file must be Netscape/Mozilla format.'
  return 0
}

count_lines_file() {
  f=$1
  if [ -f "$f" ]; then
    wc -l < "$f" 2>/dev/null | tr -d ' '
  else
    printf '0'
  fi
}

parse_facebook_dump_shell() {
  page=$1
  normalized="$FB_SCAN_DIR/normalized_$$.txt"
  : > "$normalized"

  # No Python and no executable heredoc: both were removed from this release.
  # Normalize common JSON/HTML escaping before extracting candidate IDs.
  sed 's#\\/#/#g; s#\\u0026#\&#g; s#&amp;#\&#g' "$page" > "$normalized" 2>/dev/null || {
    rm -f "$normalized" 2>/dev/null || true
    return 1
  }

  # /reel/123...
  grep -Eo '/reel/[0-9]{6,}' "$normalized" 2>/dev/null | \
    sed -n 's#^/reel/\([0-9][0-9]*\)$#https://www.facebook.com/reel/\1#p' \
    >> "$FB_LINKS_FILE" || true

  # /watch/?...v=123... and /video.php?...v=123...
  grep -Eo '(/watch/\?[^" <]*v=[0-9]{6,}|/video\.php\?[^" <]*v=[0-9]{6,})' "$normalized" 2>/dev/null | \
    sed -n 's/.*[?&]v=\([0-9][0-9]*\).*/https:\/\/www.facebook.com\/watch\/?v=\1/p' \
    >> "$FB_LINKS_FILE" || true

  # Facebook JSON payloads often expose video_id/videoId even when a direct
  # permalink is absent in the server-rendered HTML.
  grep -Eo '"(video_id|videoId)"[[:space:]]*:[[:space:]]*"[0-9]{6,}"' "$normalized" 2>/dev/null | \
    sed -n 's/.*"\([0-9][0-9]*\)"$/https:\/\/www.facebook.com\/watch\/?v=\1/p' \
    >> "$FB_LINKS_FILE" || true

  # Common permalink path: /name/videos/.../123456
  grep -Eo '/[^" <]+/videos/([^/" <]+/)?[0-9]{6,}' "$normalized" 2>/dev/null | \
    sed -n 's#.*/\([0-9][0-9]*\)$#https://www.facebook.com/watch/?v=\1#p' \
    >> "$FB_LINKS_FILE" || true

  rm -f "$normalized" 2>/dev/null || true
  return 0
}

dedupe_fb_links() {
  [ -s "$FB_LINKS_FILE" ] || return 1

  tmp="$FB_LINKS_FILE.tmp"
  seen="$FB_SCAN_DIR/seen_ids.txt"
  : > "$tmp"
  : > "$seen"

  while IFS= read -r u || [ -n "$u" ]; do
    [ -n "$u" ] || continue
    vid=''

    case "$u" in
      *facebook.com/reel/*)
        vid=$(printf '%s\n' "$u" | sed -n 's#.*facebook\.com/reel/\([0-9][0-9]*\).*#\1#p')
        ;;
      *\?v=[0-9]*|*\&v=[0-9]*)
        vid=$(printf '%s\n' "$u" | sed -n 's/.*[?&]v=\([0-9][0-9]*\).*/\1/p')
        ;;
    esac

    [ -n "$vid" ] || continue

    if ! grep -qx "$vid" "$seen" 2>/dev/null; then
      printf '%s\n' "$vid" >> "$seen"
      printf '%s\n' "$u" >> "$tmp"
    fi
  done < "$FB_LINKS_FILE"

  mv "$tmp" "$FB_LINKS_FILE"
  [ -s "$FB_LINKS_FILE" ]
}


run_bounded_command() {
  limit=$1
  marker=$2
  shift 2

  rm -f "$marker" 2>/dev/null || true

  # a-Shell target evidence showed that background PID capture ($!) is not
  # reliable in this path. Never use shell job-control PIDs here.
  if have timeout; then
    timeout "${limit}s" "$@"
    rc=$?
    [ "$rc" -eq 124 ] && : > "$marker"
    return "$rc"
  fi

  if have gtimeout; then
    gtimeout "${limit}s" "$@"
    rc=$?
    [ "$rc" -eq 124 ] && : > "$marker"
    return "$rc"
  fi

  # Portable fallback: yt-dlp itself still has socket/retry bounds.
  "$@"
  return $?
}

fetch_fb_page_dump() {
  index=$1
  total=$2
  url=$3
  page_dir="$FB_SCAN_DIR/fetch_$index"

  rm -rf "$page_dir" 2>/dev/null || true
  mkdir -p "$page_dir" || return 1

  say "[C][scan] $index/$total fetch..."

  attempt=1
  while [ "$attempt" -le 2 ]; do
    timeout_marker="$page_dir/.timeout_$attempt"
    log_file="$page_dir/fetch_$attempt.log"

    (
      cd "$page_dir" || exit 1

      set -- --ignore-errors --skip-download --write-pages \
        --socket-timeout "$FB_SOCKET_TIMEOUT" \
        --retries 1 --extractor-retries 1 --fragment-retries 0 \
        --no-playlist \
        --add-header 'Accept-Language:en-US,en;q=0.8'

      [ -z "$COOKIES" ] || set -- "$@" --cookies "$COOKIES"

      if [ "$attempt" -eq 2 ] && [ -n "$FB_IMPERSONATE" ]; then
        set -- "$@" --impersonate "$FB_IMPERSONATE"
      fi

      set -- "$@" "$url"
      if [ "$YTDLP_MODE" = 'module' ]; then
        run_bounded_command "$FB_HARD_TIMEOUT" "$timeout_marker" "$YTDLP" -m yt_dlp "$@" >"$log_file" 2>&1
      else
        run_bounded_command "$FB_HARD_TIMEOUT" "$timeout_marker" "$YTDLP" "$@" >"$log_file" 2>&1
      fi
      exit $?
    )
    rc=$?

    if [ -f "$timeout_marker" ] || [ "$rc" -eq 124 ]; then
      say "[C][scan] hard timeout after ${FB_HARD_TIMEOUT}s."
    fi

    # The user's real device showed this exact redirect. Treat it as an
    # authentication result, not as a parser/network failure.
    if grep -Eqi 'facebook\.com/login/|Unsupported URL: https://(www\.)?facebook\.com/login/' "$log_file" 2>/dev/null; then
      FB_LOGIN_REQUIRED=1
      say '[C][auth] Facebook redirected this profile scan to LOGIN.'
      return 2
    fi

    dump_count=0
    before=$(count_lines_file "$FB_LINKS_FILE")

    for page in "$page_dir"/*.dump; do
      [ -f "$page" ] || continue
      dump_count=$((dump_count + 1))
      parse_facebook_dump_shell "$page" || true
    done

    dedupe_fb_links >/dev/null 2>&1 || true
    after=$(count_lines_file "$FB_LINKS_FILE")

    if [ "$dump_count" -gt 0 ]; then
      if [ "$after" -gt "$before" ] 2>/dev/null; then
        say "[C][scan] +$((after - before)) candidates (total $after)"
      else
        say '[C][scan] page saved; +0 candidates'
      fi
      return 0
    fi

    if [ "$attempt" -eq 1 ] && [ -n "$FB_IMPERSONATE" ]; then
      say "[C][scan] no page dump; retry once with $FB_IMPERSONATE..."
      attempt=2
      continue
    fi

    say '[C][scan] no page dump.'
    return 0
  done

  return 0
}

scan_facebook_profile() {
  : > "$FB_LINKS_FILE"
  FB_LOGIN_REQUIRED=0
  detect_fb_impersonation >/dev/null 2>&1 || true

  if [ -n "$FB_IMPERSONATE" ]; then
    say "[C][scan] fallback impersonation available: $FB_IMPERSONATE"
  else
    say '[C][scan] browser impersonation unavailable; plain yt-dlp fetch only.'
  fi

  fetch_fb_page_dump 1 3 "$INPUT"
  rc=$?
  [ "$rc" -eq 2 ] && return 2

  fetch_fb_page_dump 2 3 "https://www.facebook.com/profile.php?id=$FB_PROFILE_ID&sk=reels_tab"
  rc=$?
  [ "$rc" -eq 2 ] && return 2

  discovered=$(count_lines_file "$FB_LINKS_FILE")
  if [ "$discovered" -eq 0 ] 2>/dev/null; then
    fetch_fb_page_dump 3 3 "https://m.facebook.com/profile.php?id=$FB_PROFILE_ID&sk=reels_tab"
    rc=$?
    [ "$rc" -eq 2 ] && return 2
  else
    say '[C][scan] candidates found; skipping unnecessary mobile fallback.'
  fi

  dedupe_fb_links
}

run_fb_bulk_video() {
  video_url=$1
  selector=$2
  tpl="$FB_BATCH_DIR/%(title).100B [%(id)s].%(ext)s"

  bulk_connections=$CONNECTIONS
  [ "$bulk_connections" -le 4 ] || bulk_connections=4

  set -- --no-playlist --continue --newline --no-part \
    --concurrent-fragments "$bulk_connections" \
    --retries 10 --fragment-retries 10 --extractor-retries 3 \
    --socket-timeout 30 \
    --download-archive "$FB_ARCHIVE_FILE" \
    -f "$selector" -o "$tpl"

  [ -z "$COOKIES" ] || set -- "$@" --cookies "$COOKIES"

  if have ffmpeg; then
    set -- "$@" --merge-output-format mp4
  fi

  set -- "$@" "$video_url"
  run_ytdlp "$@"
}

facebook_profile_flow() {
  extract_facebook_profile_id || {
    err 'Could not read the Facebook profile numeric ID.'
    return 1
  }

  fb_profile_paths || {
    err 'Could not create Facebook batch folders.'
    return 1
  }

  say ''
  say "[C] Facebook profile detected: $FB_PROFILE_ID"
  say '[C] Best-effort mode: Facebook does not expose a stable public bulk-video API to yt-dlp.'
  say ''
  say 'Profile quality:'
  say ' 1) BEST available'
  say ' 2) 1080p or lower'
  say ' 3) 720p or lower'
  say ' 0) Cancel'
  printf 'Number: '
  IFS= read -r q || q=''

  case "$q" in
    0) return 0 ;;
    1) selector=$(best_selector) ;;
    2) selector=$(selector_for_height 1080) ;;
    3) selector=$(selector_for_height 720) ;;
    *) err 'Wrong number.'; return 1 ;;
  esac

  say ''
  say '[C] Profile discovery: bounded yt-dlp page fetches.'
  say "[C] Socket timeout: ${FB_SOCKET_TIMEOUT}s."
  if have timeout || have gtimeout; then
    say "[C] Hard wall helper enabled: ${FB_HARD_TIMEOUT}s."
  else
    say '[C] Hard wall helper unavailable on this shell; no background PID trick is used.'
  fi

  scan_facebook_profile
  scan_rc=$?

  if [ "$scan_rc" -eq 2 ] || [ "$FB_LOGIN_REQUIRED" -eq 1 ]; then
    say ''
    say '[C] Facebook requires a logged-in session for this profile scan.'
    if [ -z "$COOKIES" ]; then
      say 'Use a fresh Netscape/Mozilla cookies.txt file, then run:'
      say "  c --cookies cookies.txt \"$INPUT\""
      say ''
      say 'The cookies file must begin with:'
      say '  # Netscape HTTP Cookie File'
    else
      say 'A cookies file was supplied, but Facebook still redirected to login.'
      say 'Export a fresh logged-in Facebook cookies.txt and retry.'
    fi
    say ''
    say 'Single Facebook reel/video URLs remain supported.'
    return 0
  fi

  if [ "$scan_rc" -ne 0 ]; then
    err 'No candidate Facebook video/reel links were exposed to Cinema.'
    say 'This does NOT mean the profile has no videos.'
    say ''
    if [ -z "$COOKIES" ]; then
      say 'Retry with a fresh Netscape-format cookies file:'
      say "  c --cookies cookies.txt \"$INPUT\""
    else
      say 'Cookies were supplied, but Facebook still did not expose a bulk list.'
    fi
    say ''
    say 'Single Facebook reel/video URLs remain supported.'
    return 1
  fi

  discovered=$(count_lines_file "$FB_LINKS_FILE")
  say ''
  say "[C] Candidate links discovered: $discovered"
  say '[C] This count is NOT a guarantee that every profile video was exposed.'
  say "[C] Batch folder: $FB_BATCH_DIR"
  printf 'Download these candidates now? [y/N]: '
  IFS= read -r yn || yn=''

  case "$yn" in
    y|Y|yes|YES) ;;
    *) say 'Cancelled.'; return 0 ;;
  esac

  if [ "$discovered" -gt 50 ] 2>/dev/null; then
    say "[C] Large batch: $discovered candidates."
    printf 'Confirm large download again? [y/N]: '
    IFS= read -r yn2 || yn2=''
    case "$yn2" in
      y|Y|yes|YES) ;;
      *) say 'Cancelled.'; return 0 ;;
    esac
  fi

  attempted=0
  downloaded=0
  skipped=0
  failed=0

  while IFS= read -r video_url || [ -n "$video_url" ]; do
    [ -n "$video_url" ] || continue

    attempted=$((attempted + 1))
    before=$(count_lines_file "$FB_ARCHIVE_FILE")

    say ''
    say "[$attempted/$discovered] $video_url"

    if run_fb_bulk_video "$video_url" "$selector"; then
      after=$(count_lines_file "$FB_ARCHIVE_FILE")
      if [ "$after" -gt "$before" ] 2>/dev/null; then
        downloaded=$((downloaded + 1))
      else
        skipped=$((skipped + 1))
      fi
    else
      failed=$((failed + 1))
      warn "Failed: $video_url"
    fi
  done < "$FB_LINKS_FILE"

  say ''
  say '========================================'
  say '[C] Facebook profile batch finished.'
  say "[C] Discovered: $discovered"
  say "[C] New downloads: $downloaded"
  say "[C] Already downloaded/skipped: $skipped"
  say "[C] Failed: $failed"
  say "[C] Folder: $FB_BATCH_DIR"
  say '========================================'

  [ "$downloaded" -gt 0 ] || [ "$skipped" -gt 0 ]
}

show_menu() {
  say ''
  say 'Choose quality:'
  say '----------------------------------------'
  say ' 1) BEST quality — automatic'
  say ' 2) 4K / 2160p or lower'
  say ' 3) 2K / 1440p or lower'
  say ' 4) Full HD / 1080p or lower'
  say ' 5) HD / 720p or lower'
  say ' 6) SD / 480p or lower'
  say ' 7) FAST MP4 — ready video+audio'
  say ' 8) AUDIO — M4A'
  say ' 9) AUDIO — MP3'
  say '10) EXACT site formats — show IDs'
  say '11) SMART — Instagram photos/videos/carousel (all media)'
  say '12) GALLERY — download all supported post media'
  say ' 0) Cancel'
  say '----------------------------------------'
}

choose_destination() {
  media_kind=$1

  if [ "$media_kind" = 'audio' ]; then
    SAVE_MODE='files'
    return 0
  fi

  [ "$SAVE_MODE" = 'ask' ] || return 0

  say ''
  say 'Save after download:'
  say ' 1) Photos SAFE   — verify by rebuilding to iPhone-safe MP4'
  say ' 2) Files only    — Cinema_Downloads'
  printf 'Number: '
  IFS= read -r dst || dst=''

  case "$dst" in
    1) SAVE_MODE='photos' ;;
    2) SAVE_MODE='files' ;;
    *)
      err 'Wrong number.'
      exit 1
      ;;
  esac
}

selector_for_height() {
  h=$1
  if have ffmpeg; then
    printf '%s' "bv*[height<=$h][ext=mp4][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=$h][ext=mp4]+ba/b[height<=$h][ext=mp4]/b[height<=$h]"
  else
    printf '%s' "b[height<=$h][ext=mp4]/b[height<=$h]"
  fi
}

best_selector() {
  if have ffmpeg; then
    printf '%s' 'bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/bv*[ext=mp4]+ba/b[ext=mp4]/best'
  else
    printf '%s' 'b[ext=mp4]/best'
  fi
}

new_work_dir() {
  mkdir -p "$STATE_DIR" "$DOWNLOAD_DIR" || {
    err 'Cannot create working folders.'
    exit 1
  }

  stamp=$(date '+%Y%m%d_%H%M%S' 2>/dev/null || printf 'job')
  WORK_DIR="$STATE_DIR/job_${stamp}_$$"
  mkdir -p "$WORK_DIR" || {
    err 'Cannot create unique download job folder.'
    exit 1
  }
}

discover_completed_output() {
  found=''
  count=0

  # Historical method: inspect the unique job folder only after yt-dlp exits.
  # Ignore known temporary/metadata files.
  for f in "$WORK_DIR"/*; do
    [ -f "$f" ] || continue
    case "$f" in
      *.part|*.ytdl|*.temp|*.tmp|*.json|*.description|*.jpg|*.jpeg|*.png|*.webp)
        continue
        ;;
    esac

    case "$f" in
      *.mp4|*.MP4|*.m4v|*.M4V|*.mov|*.MOV|*.mkv|*.MKV|*.webm|*.WEBM|*.m4a|*.M4A|*.mp3|*.MP3|*.aac|*.AAC|*.opus|*.OPUS)
        found=$f
        count=$((count + 1))
        ;;
    esac
  done

  [ "$count" -eq 1 ] || {
    if [ "$count" -eq 0 ]; then
      err 'yt-dlp finished but no completed media file was found.'
    else
      err 'More than one completed media file was found; refusing to guess.'
    fi
    return 1
  }

  OUTPUT_FILE=$found
  return 0
}

move_to_downloads() {
  [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ] || return 1

  base=${OUTPUT_FILE##*/}
  dest="$DOWNLOAD_DIR/$base"

  if [ -e "$dest" ]; then
    stamp=$(date '+%Y%m%d_%H%M%S' 2>/dev/null || printf '%s' "$$")
    dest="$DOWNLOAD_DIR/Cinema_${stamp}_$base"
  fi

  mv "$OUTPUT_FILE" "$dest" || {
    err 'Could not move the completed file into Cinema_Downloads.'
    return 1
  }

  OUTPUT_FILE=$dest
  return 0
}

run_download() {
  selector=$1
  action=$2

  new_work_dir
  tpl="$WORK_DIR/%(title).120B [%(id)s].%(ext)s"

  # Deliberately no --print-to-file and no last_output.txt.
  set -- --no-playlist --continue --newline --no-part \
    --concurrent-fragments "$CONNECTIONS" \
    --retries 10 --fragment-retries 10 --extractor-retries 3 \
    --socket-timeout 30 \
    -f "$selector" -o "$tpl"

  [ -z "$COOKIES" ] || set -- "$@" --cookies "$COOKIES"

  case "$action" in
    merge)
      if have ffmpeg; then
        set -- "$@" --merge-output-format mp4
      fi
      ;;
    m4a)
      if have ffmpeg; then
        set -- "$@" -x --audio-format m4a
      fi
      ;;
    mp3)
      if ! have ffmpeg; then
        err 'MP3 needs ffmpeg. Choose M4A instead.'
        return 1
      fi
      set -- "$@" -x --audio-format mp3 --audio-quality 0
      ;;
    none)
      ;;
    *)
      err "Internal action error: $action"
      return 1
      ;;
  esac

  set -- "$@" "$INPUT"

  ytdlp_ok=1
  run_ytdlp "$@" || ytdlp_ok=0

  if [ "$ytdlp_ok" -eq 1 ] && discover_completed_output; then
    move_to_downloads || return 1
  else
    # The exact iPhone error "There is no video in this post" is expected
    # for Instagram image-only posts. Do not mistake it for an update issue.
    if is_instagram_post && [ "$action" != 'm4a' ] && [ "$action" != 'mp3' ]; then
      warn 'No downloadable video found. Checking Instagram photos/carousel...'
      if run_gallery_download; then
        OUTPUT_FILE=''
        return 0
      fi
    fi
    err 'yt-dlp download failed or no completed video/audio file was found.'
    if is_instagram_post && ! find_gallery; then
      say 'For Instagram images, first run: c --setup'
    fi
    return 1
  fi

  say ''
  say "DONE: $OUTPUT_FILE"
  return 0
}

show_exact_formats() {
  say ''
  say '[C] Actual formats reported by the site:'
  say '----------------------------------------'

  set -- -F --no-playlist --socket-timeout 30 --retries 3
  [ -z "$COOKIES" ] || set -- "$@" --cookies "$COOKIES"
  set -- "$@" "$INPUT"

  run_ytdlp "$@" || return 1

  say '----------------------------------------'
  printf 'Type format ID (example 18 or 137+140): '
  IFS= read -r fid || fid=''
  [ -n "$fid" ] || {
    err 'Empty format ID'
    return 1
  }

  choose_destination video
  say "[C] Downloading format: $fid"
  run_download "$fid" merge
}


make_photos_safe_copy() {
  [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ] || {
    err 'No downloaded video was found for Photos preparation.'
    return 1
  }

  have ffmpeg || {
    err 'Photos SAFE needs ffmpeg in a-Shell.'
    return 1
  }

  base=${OUTPUT_FILE##*/}
  stem=${base%.*}
  PHOTOS_SAFE_FILE="$DOWNLOAD_DIR/PhotosSafe_${stem}.mp4"

  if [ -e "$PHOTOS_SAFE_FILE" ]; then
    stamp=$(date '+%Y%m%d_%H%M%S' 2>/dev/null || printf '%s' "$$")
    PHOTOS_SAFE_FILE="$DOWNLOAD_DIR/PhotosSafe_${stamp}_${stem}.mp4"
  fi

  tmp="$PHOTOS_SAFE_FILE.tmp.mp4"
  rm -f "$tmp" 2>/dev/null || true

  say ''
  say '[C] Checking export compatibility before Photos...'
  say '[C] Building Photos-safe MP4: H.264 + AAC + yuv420p + faststart'
  say '[C] Original downloaded file will be kept.'

  # First try iPhone hardware H.264. If the a-Shell build does not expose it,
  # fall back to libx264. No ffprobe is used in this path.
  if ffmpeg -y -hide_banner -loglevel error \
      -i "$OUTPUT_FILE" \
      -map 0:v:0 -map 0:a:0? \
      -sn -dn \
      -c:v h264_videotoolbox -pix_fmt yuv420p -b:v 6000k \
      -c:a aac -b:a 192k \
      -movflags +faststart \
      "$tmp"
  then
    :
  else
    rm -f "$tmp" 2>/dev/null || true
    say '[C] Hardware H.264 unavailable/failed; trying software H.264...'

    if ! ffmpeg -y -hide_banner -loglevel error \
        -i "$OUTPUT_FILE" \
        -map 0:v:0 -map 0:a:0? \
        -sn -dn \
        -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p \
        -c:a aac -b:a 192k \
        -movflags +faststart \
        "$tmp"
    then
      rm -f "$tmp" 2>/dev/null || true
      err 'Could not build a Photos-safe MP4.'
      return 1
    fi
  fi

  [ -s "$tmp" ] || {
    rm -f "$tmp" 2>/dev/null || true
    err 'Photos-safe output is empty.'
    return 1
  }

  # Independent sanity check: decode one video frame using ffmpeg.
  # We deliberately avoid ffprobe because that path stalled on-device before.
  if ! ffmpeg -hide_banner -loglevel error \
      -i "$tmp" \
      -map 0:v:0 -frames:v 1 \
      -f null /dev/null
  then
    rm -f "$tmp" 2>/dev/null || true
    err 'Photos-safe MP4 failed the decode sanity check.'
    return 1
  fi

  mv "$tmp" "$PHOTOS_SAFE_FILE" || {
    rm -f "$tmp" 2>/dev/null || true
    err 'Could not finalize the Photos-safe MP4.'
    return 1
  }

  say "[C] Photos-safe MP4 ready: $PHOTOS_SAFE_FILE"
  return 0
}

open_exact_video_for_photos() {
  [ -n "$PHOTOS_SAFE_FILE" ] && [ -f "$PHOTOS_SAFE_FILE" ] || return 1

  say ''
  say '[C] Opening the Photos-safe MP4...'
  say '[C] In the iOS panel choose: Save Video.'

  if have open; then
    open "$PHOTOS_SAFE_FILE" >/dev/null 2>&1 && return 0
  fi

  if have view; then
    view "$PHOTOS_SAFE_FILE" >/dev/null 2>&1 && return 0
  fi

  err 'Could not open the Photos-safe video automatically.'
  return 1
}

finish() {
  # When an Instagram video request was converted to a gallery download,
  # finish_gallery already handled the result and there is no video path.
  [ -n "$OUTPUT_FILE" ] || return 0
  case "$SAVE_MODE" in
    photos)
      if make_photos_safe_copy; then
        open_exact_video_for_photos || {
          say 'Open this Photos-safe file manually from Files, then Share -> Save Video:'
          say "$PHOTOS_SAFE_FILE"
        }
      else
        err 'Photos SAFE preparation failed.'
        say 'Original download was preserved here:'
        say "$OUTPUT_FILE"
        return 1
      fi
      ;;
    files)
      say "Saved in Files: $OUTPUT_FILE"
      ;;
  esac
}

main() {
  parse_args "$@"

  if [ "$INSTALL" -eq 1 ]; then
    install_self
    exit 0
  fi

  if [ "$SETUP" -eq 1 ]; then
    install_or_update_deps
    exit $?
  fi

  if [ "$DOCTOR" -eq 1 ]; then
    show_doctor
    exit 0
  fi

  find_ytdlp || {
    # An explicit gallery request should work without yt-dlp installed.
    if [ "$SMART_MODE" != 'gallery' ] && [ "$SMART_MODE" != 'smart' ]; then
      err 'yt-dlp not found. Run: c --setup'
      exit 1
    fi
  }

  if [ "$FB_DOCTOR" -eq 1 ]; then
    facebook_doctor
    exit $?
  fi

  prompt_url

  if is_facebook_profile_url; then
    facebook_profile_flow
    exit $?
  fi

  if [ "$SMART_MODE" = 'gallery' ]; then
    choose_gallery_destination || exit 1
    run_gallery_download
    exit $?
  fi
  if [ "$SMART_MODE" = 'smart' ]; then
    smart_download
    exit $?
  fi

  show_menu
  printf 'Number: '
  IFS= read -r choice || choice=''

  case "$choice" in
    0)
      exit 0
      ;;
    1)
      choose_destination video
      say '[C] Downloading BEST...'
      sel=$(best_selector)
      run_download "$sel" merge || exit 1
      ;;
    2|3|4|5|6)
      case "$choice" in
        2) h=2160; label='2160p' ;;
        3) h=1440; label='1440p' ;;
        4) h=1080; label='1080p' ;;
        5) h=720;  label='720p' ;;
        6) h=480;  label='480p' ;;
      esac
      choose_destination video
      say "[C] Downloading $label or best lower quality..."
      sel=$(selector_for_height "$h")
      run_download "$sel" merge || exit 1
      ;;
    7)
      choose_destination video
      say '[C] Downloading FAST MP4...'
      run_download 'b[ext=mp4]/best' none || exit 1
      ;;
    8)
      choose_destination audio
      say '[C] Downloading AUDIO M4A...'
      if have ffmpeg; then
        run_download 'bestaudio' m4a || exit 1
      else
        run_download 'bestaudio[ext=m4a]/bestaudio' none || exit 1
      fi
      ;;
    9)
      choose_destination audio
      say '[C] Downloading AUDIO MP3...'
      run_download 'bestaudio' mp3 || exit 1
      ;;
    10)
      show_exact_formats || exit 1
      ;;
    11)
      smart_download
      exit $?
      ;;
    12)
      choose_gallery_destination || exit 1
      run_gallery_download
      exit $?
      ;;
    *)
      err 'Wrong number.'
      exit 1
      ;;
  esac

  finish
}

main "$@"
