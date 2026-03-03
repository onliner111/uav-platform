param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("first-build", "up", "down")]
  [string]$Action,

  [string]$ComposeFile = "infra/docker-compose.yml",
  [string]$AppBaseUrl = "http://app:8000",
  [string]$TenantName = "default-demo",

  [string]$AdminUsername = "admin",
  [string]$AdminPassword = "Admin@12345",
  [string]$DispatcherUsername = "dispatcher1",
  [string]$DispatcherPassword = "Dispatcher@12345",
  [string]$InspectorUsername = "inspector1",
  [string]$InspectorPassword = "Inspector@12345",
  [string]$IncidentUsername = "incident1",
  [string]$IncidentPassword = "Incident@12345",
  [string]$AuditorUsername = "auditor1",
  [string]$AuditorPassword = "Auditor@12345",

  [string]$AccountsOutput = "logs/default_accounts.json",

  [switch]$SkipValidation,
  [switch]$PurgeData
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Compose {
  param([string[]]$Args)
  Write-Host ">> docker compose -f $ComposeFile $($Args -join ' ')" -ForegroundColor Cyan
  & docker compose -f $ComposeFile @Args
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose failed with exit code $LASTEXITCODE"
  }
}

function Ensure-EnvFile {
  if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example" -ForegroundColor Yellow
  }
}

function Run-FirstBuild {
  Ensure-EnvFile

  Invoke-Compose @("up", "-d", "--build", "app", "app-tools", "db", "redis")
  Invoke-Compose @("run", "--rm", "--build", "app", "alembic", "upgrade", "head")

  if (-not $SkipValidation) {
    Invoke-Compose @("run", "--rm", "--build", "-e", "APP_BASE_URL=$AppBaseUrl", "app-tools", "python", "infra/scripts/verify_smoke.py")
  }

  Invoke-Compose @(
    "run", "--rm", "--build",
    "-e", "APP_BASE_URL=$AppBaseUrl",
    "-e", "DEFAULT_TENANT_NAME=$TenantName",
    "-e", "DEFAULT_ADMIN_USERNAME=$AdminUsername",
    "-e", "DEFAULT_ADMIN_PASSWORD=$AdminPassword",
    "-e", "DEFAULT_DISPATCHER_USERNAME=$DispatcherUsername",
    "-e", "DEFAULT_DISPATCHER_PASSWORD=$DispatcherPassword",
    "-e", "DEFAULT_INSPECTOR_USERNAME=$InspectorUsername",
    "-e", "DEFAULT_INSPECTOR_PASSWORD=$InspectorPassword",
    "-e", "DEFAULT_INCIDENT_USERNAME=$IncidentUsername",
    "-e", "DEFAULT_INCIDENT_PASSWORD=$IncidentPassword",
    "-e", "DEFAULT_AUDITOR_USERNAME=$AuditorUsername",
    "-e", "DEFAULT_AUDITOR_PASSWORD=$AuditorPassword",
    "-e", "DEFAULT_ACCOUNTS_OUTPUT=$AccountsOutput",
    "app-tools", "python", "infra/scripts/bootstrap_default_accounts.py"
  )

  Write-Host ""
  Write-Host "First build completed." -ForegroundColor Green
  Write-Host "Open UI login: $AppBaseUrl/ui/login" -ForegroundColor Green
  Write-Host "Default credentials file: $AccountsOutput" -ForegroundColor Green
}

function Run-Up {
  Ensure-EnvFile
  Invoke-Compose @("up", "-d", "app", "app-tools", "db", "redis")
  Write-Host "System is up." -ForegroundColor Green
}

function Run-Down {
  if ($PurgeData) {
    Invoke-Compose @("down", "-v", "--remove-orphans")
    Write-Host "System is down. Volumes removed." -ForegroundColor Yellow
    return
  }
  Invoke-Compose @("down", "--remove-orphans")
  Write-Host "System is down. Data volumes preserved." -ForegroundColor Yellow
}

switch ($Action) {
  "first-build" { Run-FirstBuild }
  "up" { Run-Up }
  "down" { Run-Down }
  default { throw "Unsupported action: $Action" }
}
