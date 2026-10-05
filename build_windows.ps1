# 一键打包 Windows 单文件 exe
# 产物：dist/SlimePet.exe（双击即用，无需安装 Python）
# 用法：在项目根目录执行  powershell -ExecutionPolicy Bypass -File build_windows.ps1

Set-Location -Path $PSScriptRoot

python make_ico.py
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name SlimePet `
  --icon assets/slime.ico `
  --add-data "web;web" `
  main.py

Write-Host "打包完成：$PSScriptRoot\dist\SlimePet.exe"
