# Daily logical backup — User Story 1.2.2
param(
    [string]$BackupDir = ".\backups\postgres",
    [int]$RetentionDays = 35,
    [string]$PgHost = "localhost",
    [int]$PgPort = 5432,
    [string]$PgUser = "postgres",
    [string]$PgDatabase = "ai_support"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$file = Join-Path $BackupDir "ai_support_$stamp.dump"

Write-Host "Backing up $PgDatabase -> $file"
& pg_dump -h $PgHost -p $PgPort -U $PgUser -d $PgDatabase -Fc -f $file

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem $BackupDir -Filter "ai_support_*.dump" |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Force

Write-Host "Backup complete. Retention: $RetentionDays days."
