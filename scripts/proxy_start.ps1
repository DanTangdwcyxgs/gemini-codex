param(
    [string]$ApiKeyFile = "$(Join-Path $PSScriptRoot '..\geminikey\geminiapikey.txt')",
    [string]$Python = "python",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path $ApiKeyFile)) {
    throw "Gemini API key file not found: $ApiKeyFile"
}

$key = (Get-Content -Raw $ApiKeyFile).Trim()
if ([string]::IsNullOrWhiteSpace($key)) {
    throw "Gemini API key file is empty: $ApiKeyFile"
}

$env:CODEX_PROXY_GEMINI_API_KEY = $key
$env:CODEX_PROXY_PORT = "$Port"
$env:PYTHONPATH = Join-Path $RepoRoot 'src'

Write-Host "Starting Gemini Codex proxy on http://127.0.0.1:$Port ..."
Write-Host "API key loaded from: $ApiKeyFile"
Write-Host "Press Ctrl+C to stop."

Push-Location $RepoRoot
try {
    & $Python -m codex_proxy.main
    if ($LASTEXITCODE -ne 0) {
        throw "Proxy exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
