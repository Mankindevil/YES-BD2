param(
    [string]$StartTag = "",
    [string]$EndTag = "",
    [string]$Changelog = "",
    [Parameter(Mandatory = $true)]
    [string]$ReleaseTag,
    [string]$OutputPath = "release-notes.md"
)

$ErrorActionPreference = "Stop"

# YES-BD2 releases are tags that scripts/sync_public.py puts on the synced
# snapshot commits; each commit title is the name of one merged change.
$releaseCommit = git rev-list -n 1 $ReleaseTag 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($releaseCommit)) {
    throw "Could not resolve release tag $ReleaseTag."
}
$releaseCommit = "$releaseCommit".Trim()

function Test-PublishedRelease([string]$Tag) {
    # A tag whose build failed has no release page; players never got it.
    if (-not $env:GH_TOKEN -or -not (Get-Command gh -ErrorAction SilentlyContinue)) {
        return $true
    }
    gh release view $Tag 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

$previousTag = $StartTag.Trim()
if ($previousTag -and -not (Test-PublishedRelease $previousTag)) {
    $previousTag = ""
}
if ([string]::IsNullOrWhiteSpace($previousTag)) {
    $candidate = "$releaseCommit^"
    while ($true) {
        $tag = git describe --tags --abbrev=0 $candidate 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($tag)) {
            $previousTag = ""
            break
        }
        $tag = "$tag".Trim()
        if (Test-PublishedRelease $tag) {
            $previousTag = $tag
            break
        }
        $candidate = "$tag^"
    }
}
$global:LASTEXITCODE = 0

# sync_public.py titles a sync that changes nothing in the tool with this
# line; older syncs joined several player notes of one release with 「；」.
$maintenanceTitle = "开发和测试调整，不影响工具使用"
$entries = [System.Collections.Generic.List[string]]::new()
if ($previousTag) {
    foreach ($subject in @(git log --format=%s "$previousTag..$releaseCommit")) {
        foreach ($part in ("$subject" -split "；")) {
            $line = $part.Trim()
            if ($line -and $line -ne $maintenanceTitle -and -not $entries.Contains("- $line")) {
                $entries.Add("- $line")
            }
        }
    }
}
if ($entries.Count -eq 0) {
    foreach ($line in ($Changelog -split "`r?`n")) {
        $line = ($line -replace '^\s*[-*]\s+', '').Trim()
        if ($line) {
            $entries.Add("- $line")
        }
    }
}

$releaseNotes = @(
    "## YES-BD2 $ReleaseTag"
    ""
    if ($previousTag) {
        "### 更新内容 $previousTag -> $ReleaseTag"
        ""
        if ($entries.Count -gt 0) { $entries -join "`n" } else { "- 小修正" }
    } else {
        "第一个公开版本。"
    }
    ""
    "### 下载包说明"
    ""
    "- [yes-bd2-win32-online-setup.exe](https://github.com/nobell001/YES-BD2/releases/download/$ReleaseTag/yes-bd2-win32-online-setup.exe) 在线安装包（推荐，约 5 MB），安装时联网下载其余部分。"
    "- [yes-bd2-win32-Full-setup.exe](https://github.com/nobell001/YES-BD2/releases/download/$ReleaseTag/yes-bd2-win32-Full-setup.exe) 完整离线安装包，文件很大，安装时不能联网才用。"
    "- 两种装好后完全一样，打开工具时都会自动更新。"
    "- 不要下载 yes-bd2-win32.zip 或 Source code 压缩包。"
) -join "`n"

$workspace = (Resolve-Path -LiteralPath ".").Path
$absoluteOutput = [System.IO.Path]::GetFullPath((Join-Path $workspace $OutputPath))
$relativeOutput = [System.IO.Path]::GetRelativePath($workspace, $absoluteOutput)
if ([System.IO.Path]::IsPathRooted($relativeOutput) -or
    $relativeOutput -eq ".." -or
    $relativeOutput.StartsWith("..\") -or
    $relativeOutput.StartsWith("../")) {
    throw "Refusing to write release notes outside the workspace: $absoluteOutput"
}
Set-Content -LiteralPath $absoluteOutput -Value $releaseNotes -Encoding utf8
Get-Content -LiteralPath $absoluteOutput
