param([Parameter(Mandatory = $true)][string]$Task)
# Run one ok-script task headless and keep its log (developer helper).
#   powershell -ExecutionPolicy Bypass -File tools\run_task.ps1 MapRouteTestTask
# Close the tool's own window first (both drive the same game).  Never add -e:
# ok.cli then exits the game after the task.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
# Decode python's UTF-8 output as UTF-8 (a cp950 console garbled the log).
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
New-Item -ItemType Directory -Force .local-dev\logs | Out-Null
# Windows PowerShell writes the redirected log as UTF-16.
$log = ".local-dev\logs\$(Get-Date -Format 'HHmmss')_$Task.log"
$start = Get-Date
.venv\Scripts\python.exe -m ok.cli run_task $Task *> $log
$secs = [int]((Get-Date) - $start).TotalSeconds
"== $Task took ${secs}s  log=$log"
Get-Content $log | Where-Object { $_ -match ' (WARNING|ERROR) ' -and $_ -notmatch 'frame_arrived_callback' } | Select-Object -Last 25
"-- key lines"
Get-Content $log | Where-Object { $_ -match 'TaskExecutor \w+:(?!info_set)' } | Select-Object -Last 25
