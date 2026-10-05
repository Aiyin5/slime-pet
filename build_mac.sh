#!/bin/bash
# 在 macOS 上打包 .app 并生成可分享的 .dmg
# 用法：bash build_mac.sh
set -e
cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt pyinstaller

# 组装 macOS 的 .icns 图标
if [ ! -f assets/slime.icns ]; then
  python make_icon_png.py
  ICONSET=assets/slime.iconset
  mkdir -p $ICONSET
  sips -z 16 16     assets/slime_1024.png --out $ICONSET/icon_16x16.png
  sips -z 32 32     assets/slime_1024.png --out $ICONSET/icon_16x16@2x.png
  sips -z 32 32     assets/slime_1024.png --out $ICONSET/icon_32x32.png
  sips -z 64 64     assets/slime_1024.png --out $ICONSET/icon_32x32@2x.png
  sips -z 128 128   assets/slime_1024.png --out $ICONSET/icon_128x128.png
  sips -z 256 256   assets/slime_1024.png --out $ICONSET/icon_128x128@2x.png
  sips -z 256 256   assets/slime_1024.png --out $ICONSET/icon_256x256.png
  sips -z 512 512   assets/slime_1024.png --out $ICONSET/icon_256x256@2x.png
  sips -z 512 512   assets/slime_1024.png --out $ICONSET/icon_512x512.png
  cp assets/slime_1024.png $ICONSET/icon_512x512@2x.png
  iconutil -c icns $ICONSET -o assets/slime.icns
fi

pyinstaller --noconfirm --clean --windowed --name SlimePet `
  --icon assets/slime.icns `
  --add-data "web:web" `
  main.py

APP="dist/SlimePet.app"
DMG="dist/SlimePet-mac.dmg"
rm -f "$DMG"
hdiutil create -volname "SlimePet" -srcfolder "$APP" -ov -format UDZO "$DMG"
echo "打包完成：$DMG"
