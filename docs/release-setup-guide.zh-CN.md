# YES-BD2 发布配置指南

这份配置只需要做一次。配置完成后，推送 `v0.1.0` 这类 tag，GitHub
Actions 会自动生成 PyAppify 安装包，并同步 `YES-BD2-update` 更新仓库。

## 1. 创建 GitHub 更新仓库

在 GitHub 创建一个新仓库：

```text
nobell001/YES-BD2-update
```

建议保持空仓库，不要勾选初始化 README、`.gitignore` 或 License。发布流程会
自动把 `deploy.txt` 中列出的文件同步进去。`pyappify.yml` 的安装包从这个仓库更新。

## 2. 创建 GitHub token

在 GitHub 创建一个 Fine-grained personal access token，给它访问
`nobell001/YES-BD2-update` 的权限。

推荐权限：

```text
Repository access: Only selected repositories -> nobell001/YES-BD2-update
Contents: Read and write
Metadata: Read-only
```

生成后复制 token。这个 token 只会作为 GitHub Actions Secret 保存，不要提交到
仓库文件里。

## 3. 添加 GitHub Actions Secret

打开主仓库：

```text
https://github.com/nobell001/YES-BD2
```

进入：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

添加一个 Secret：

```text
OK_GH   = 第 2 步创建的 GitHub token
```

不用添加 `GITHUB_TOKEN`，GitHub Actions 会自动提供。

## 4. 确认仓库配置

当前项目已经配置好这些文件：

```text
pyappify.yml
deploy.txt
.update_repo_gitignore
.github/workflows/build.yml
```

如果你以后改 GitHub 用户名或仓库名，需要同步修改：

```text
pyappify.yml
.github/workflows/build.yml
src/config.py
README.md
```

## 5. 发布

提交并推送主仓库后，创建一个正式版本 tag：

```powershell
git tag v0.1.0
git push origin v0.1.0
```

发布完成后，Release 页面应出现这些文件：

```text
yes-bd2-win32-Full-setup.exe
yes-bd2-win32-online-setup.exe
```

安装 `yes-bd2-win32-Full-setup.exe` 后，本机目录会类似：

```text
C:\Users\<你>\AppData\Local\yes-bd2
```

双击 `yes-bd2.exe` 时，先出现白色 PyAppify 更新窗口；更新完成后再出现黑色
`ok-script` 主界面。
