param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

(Get-Content _version.py) `
    -replace '__version__ = "[^"]+"', "__version__ = `"$Version`"" |
    Set-Content _version.py

(Get-Content Cargo.toml) `
    -replace '^version = "[^"]+"', "version = `"$Version`"" |
    Set-Content Cargo.toml

(Get-Content installer.iss) `
    -replace '#define MyAppVersion "[^"]+"', "#define MyAppVersion `"$Version`"" |
    Set-Content installer.iss
