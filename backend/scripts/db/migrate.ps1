# Alembic migration helper — User Story 1.2.2
param(
    [ValidateSet("upgrade", "downgrade", "current", "history")]
    [string]$Command = "upgrade",
    [string]$Target = "head"
)

Set-Location (Join-Path $PSScriptRoot "..\..")

switch ($Command) {
    "upgrade"   { python -m alembic upgrade $Target }
    "downgrade" { python -m alembic downgrade $Target }
    "current"   { python -m alembic current }
    "history"   { python -m alembic history --verbose }
}
