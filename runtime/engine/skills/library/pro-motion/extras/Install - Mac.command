#!/bin/bash
# Fares Motion installer for macOS: the After Effects panel + the skill(s), Claude Code if it is missing, and
# whisper-cpp (Homebrew) so the panel can hear the comp (captions). The ~560 MB model is NOT downloaded here: the
# panel downloads it itself the first time it has to listen.
cd "$(dirname "$0")/files" || exit 1
echo ""
echo "==  Fares Motion  =="
echo ""

# 1) the panel -> After Effects' extensions folder
EXT="$HOME/Library/Application Support/Adobe/CEP/extensions/com.farestoson.faresmotion"
if [ -L "$EXT" ]; then
  echo "1/4  البانل موجودة هنا كـ link (جهاز تطوير)، فسبتها زي ما هي."
else
  rm -rf "$EXT"
  mkdir -p "$EXT"
  cp -R panel/. "$EXT/"
  xattr -dr com.apple.quarantine "$EXT" 2>/dev/null
  echo "1/4  البانل اتسطّبت في After Effects."
fi
# After Effects only loads panels that are not signed by Adobe when this switch is on (one value per CEP version)
for v in 9 10 11 12 13 14 15 16; do defaults write "com.adobe.CSXS.$v" PlayerDebugMode 1; done

# 2) the skill(s) -> ~/Documents/Fares Motion/.claude/skills = the panel's working folder
WORK="$HOME/Documents/Fares Motion"
SK="$WORK/.claude/skills"
mkdir -p "$SK"
for s in skills/*/; do
  name="$(basename "$s")"
  dest="$SK/$name"
  if [ -d "$dest" ]; then                                  # an older copy is kept, never deleted
    bk="$WORK/.claude/skill-backups/$name-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$(dirname "$bk")"
    mv "$dest" "$bk"
    echo "     (النسخة القديمة من $name اتنقلت لـ $bk)"
  fi
  mkdir -p "$dest"
  cp -R "$s". "$dest/"
  echo "2/4  السكيل $name اتحطت في $WORK"
done
# the episode's example projects, next to the skill (an existing folder of the same name is the user's: left alone)
if [ -d projects ]; then
  for p in projects/*/; do
    name="$(basename "$p")"
    if [ ! -e "$WORK/$name" ]; then mkdir -p "$WORK/$name"; cp -R "$p". "$WORK/$name/"; fi
  done
  echo "     والأمثلة بتاعة الحلقة اتحطت جنبها."
fi

# 3) Claude Code (the panel runs it with the user's own Claude account)
if command -v claude >/dev/null 2>&1 || [ -x "$HOME/.local/bin/claude" ] || ls "$HOME/Library/Application Support/Claude/claude-code/"*/claude >/dev/null 2>&1; then
  echo "3/4  Claude Code موجود عندك."
else
  echo "3/4  Claude Code مش متسطّب، والبانل محتاجاه، فبيتسطّب دلوقتي…"
  curl -fsSL https://claude.ai/install.sh | bash || echo "     تسطيب Claude Code وقف. تقدر تسطّبه بعدين من claude.com/code"
fi

# 4) hearing the comp (captions): whisper-cpp from Homebrew (the panel can't install it; the model it downloads itself)
have_whisper() { command -v whisper-cli >/dev/null 2>&1 || [ -x /opt/homebrew/bin/whisper-cli ] || [ -x /usr/local/bin/whisper-cli ]; }
find_brew() { command -v brew 2>/dev/null || ls /opt/homebrew/bin/brew /usr/local/bin/brew 2>/dev/null | head -1; }
if ! have_whisper; then
  BREW="$(find_brew)"
  if [ -z "$BREW" ]; then
    echo "4/4  السمع (الكابشن) محتاج Homebrew، وهو مش متسطّب عندك."
    read -r -p "أسطّب Homebrew دلوقتي؟ هيطلب باسورد الماك (y/n) " a
    case "$a" in y|Y|ن*) /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" ;; esac
    BREW="$(find_brew)"
  fi
  if [ -n "$BREW" ]; then echo "4/4  بيسطّب برنامج السمع (Whisper)…"; "$BREW" install whisper-cpp; fi
fi
if have_whisper; then echo "4/4  السمع (Whisper) اتسطّب. الموديل بتاعه البانل بتنزّله أول مرة تطلب كابشن."
else echo "4/4  السمع لسه مش جاهز (الكابشن مش هيشتغل). شغّل ملف التسطيب تاني بعدين."; fi

echo ""
echo "خلاص! افتح After Effects (ولو كان مفتوح اقفله وافتحه تاني):"
echo "      Window  >  Extensions  >  Fares Motion"
echo "أول مرة بس: دوس على علامة الترس ثم «تسجيل الدخول» وسجّل بحساب Claude بتاعك."
echo ""
