[CmdletBinding()]
param(
    [ValidateSet('symlink', 'copy')]
    [string]$Method = 'copy',
    [string]$CodexDirectory = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }),
    [string]$SkillsDirectory = (Join-Path $env:USERPROFILE '.agents\skills'),
    [switch]$Force,
    [switch]$Verify,
    [switch]$LegacyConfig
)

$ErrorActionPreference = 'Stop'
$arguments = @(
    (Join-Path $PSScriptRoot 'install.py'),
    '--method', $Method,
    '--codex-dir', $CodexDirectory,
    '--skills-dir', $SkillsDirectory
)
if ($Force) { $arguments += '--force' }
if ($Verify) { $arguments += '--verify' }
if ($LegacyConfig) { $arguments += '--legacy-config' }
python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Rightsize Goal installation failed; see the message above.' }
