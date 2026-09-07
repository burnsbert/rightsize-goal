[CmdletBinding()]
param(
    [ValidateSet('symlink', 'copy')]
    [string]$Method = 'copy',
    [string]$ClaudeDirectory = $(if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE '.claude' }),
    [switch]$Force,
    [switch]$Verify
)

$ErrorActionPreference = 'Stop'
$arguments = @(
    (Join-Path $PSScriptRoot 'install.py'),
    '--method', $Method,
    '--claude-dir', $ClaudeDirectory
)
if ($Force) { $arguments += '--force' }
if ($Verify) { $arguments += '--verify' }
python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Rightsize Goal installation failed; see the message above.' }
