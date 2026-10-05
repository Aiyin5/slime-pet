# 打包与分发说明

## Windows（.exe）—— 已构建完成

- 产物：`dist/SlimePet.exe`（单文件，已内置 Python 运行环境与全部依赖）
- 分发：**直接把这一个 `SlimePet.exe` 发给朋友即可**，对方双击运行，无需安装 Python 或任何环境。
- 首次启动为单文件解压，需等待几秒；之后常驻右下角。
- 任务数据保存在 **exe 同级的 `data/` 文件夹**，首次运行自动创建；删除该文件夹即清空任务。
- 管理页面：右键史莱姆 → 打开管理页面（`http://127.0.0.1:17821/`）。
- 重新打包（在装好依赖的环境）：
  ```powershell
  powershell -ExecutionPolicy Bypass -File build_windows.ps1
  ```

## macOS（.dmg）—— 无法在 Windows 上生成

PyInstaller 不能跨平台打包，`.dmg` 只能在 macOS 上制作。以下两种方式任选：

### 方式一：你有 Mac
1. 把整个项目源码拷到 Mac；
2. 打开“终端”，进入项目目录，执行 `bash build_mac.sh`；
3. 完成后在 `dist/` 得到 `SlimePet-mac.dmg`。
   （首次打开若提示“无法验证开发者”，到 系统设置 → 隐私与安全性 → 仍要打开。）

### 方式二：没有 Mac，用 GitHub 云端构建（推荐）
项目已内置 `.github/workflows/build.yml`，代码推送到 GitHub 后会自动构建 exe 与 dmg：
1. 仓库地址：https://github.com/Aiyin5/slime-pet
2. 打开仓库的 **Actions** 标签页，查看 “Build SlimePet” 运行状态；
3. 约 5～10 分钟后，点进该次运行，在页面底部 **Artifacts** 下载：
   - `SlimePet-windows-exe`（Windows 用）
   - `SlimePet-mac-dmg`（macOS 用）
4. 也可在 Actions 页面手动点 “Run workflow” 触发。
