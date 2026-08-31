<#
.SYNOPSIS
    Regenerates static/vendor/ — the local copies of Font Awesome and the two
    project fonts that let the packaged app run offline.

.DESCRIPTION
    This is a manual maintenance step, NOT part of the build. Run it once when
    setting up a fresh clone, or when bumping a font/icon version. The results
    are committed to the repo (~420 KB), so a normal build needs no network.

    See static/vendor/README.md for what is downloaded and why parts are omitted.

.EXAMPLE
    .\tools\fetch_vendor.ps1
#>
[CmdletBinding()]
param(
    # Skip the Font Awesome checksum check (use when deliberately bumping the version).
    [switch]$SkipHashCheck
)

$ErrorActionPreference = 'Stop'

$FA_VERSION = '6.4.0'
$FA_SHA256 = '55A75EBA37B67ECC9F715291B2B0D121FBF41A425044590177A25F236DA9813B'

$repoRoot = Split-Path -Parent $PSScriptRoot
$vendor = Join-Path $repoRoot 'static\vendor'
$work = Join-Path ([System.IO.Path]::GetTempPath()) "dx7vendor-$(Get-Random)"

Write-Host "Repo root : $repoRoot"
Write-Host "Vendor dir: $vendor"
New-Item -ItemType Directory -Force $work | Out-Null

try {
    # ---------------------------------------------------------------- fonts --
    # google-webfonts-helper, not fonts.googleapis.com/css2: that endpoint
    # varies its response by User-Agent and hands back unversioned gstatic URLs
    # that rotate. gwfh returns a stable zip of woff2 files.
    # Note the weight 400 is spelled "regular" in the variants parameter.
    $fontJobs = @(
        @{ Slug = 'space-grotesk';  Ver = 'v22'; Out = 'space-grotesk' },
        @{ Slug = 'jetbrains-mono'; Ver = 'v24'; Out = 'jetbrains-mono' }
    )
    $weights = @(@{ Up = 'regular'; Down = '400' },
                 @{ Up = '500'; Down = '500' },
                 @{ Up = '600'; Down = '600' },
                 @{ Up = '700'; Down = '700' })

    New-Item -ItemType Directory -Force (Join-Path $vendor 'fonts') | Out-Null

    foreach ($job in $fontJobs) {
        $slug = $job.Slug
        Write-Host "Downloading $slug ..."
        $zip = Join-Path $work "$slug.zip"
        $url = "https://gwfh.mranftl.com/api/fonts/$slug" +
               "?download=zip&subsets=latin&variants=regular,500,600,700&formats=woff2"
        Invoke-WebRequest -Uri $url -OutFile $zip -TimeoutSec 120
        $ex = Join-Path $work "x-$slug"
        Expand-Archive $zip -DestinationPath $ex -Force

        # Normalise the versioned upstream filenames (…-v22-latin-regular.woff2)
        # so that a future version bump just overwrites, leaving fonts.css valid.
        foreach ($w in $weights) {
            $src = Join-Path $ex "$slug-$($job.Ver)-latin-$($w.Up).woff2"
            if (-not (Test-Path $src)) {
                throw "Expected $src. The upstream version may have changed; " +
                      "update the Ver field in this script and static/vendor/README.md."
            }
            Copy-Item $src (Join-Path $vendor "fonts\$($job.Out)-latin-$($w.Down).woff2") -Force
        }
    }

    Write-Host 'Downloading OFL license texts ...'
    Invoke-WebRequest 'https://raw.githubusercontent.com/google/fonts/main/ofl/spacegrotesk/OFL.txt' `
        -OutFile (Join-Path $vendor 'fonts\OFL-SpaceGrotesk.txt') -TimeoutSec 60
    Invoke-WebRequest 'https://raw.githubusercontent.com/google/fonts/main/ofl/jetbrainsmono/OFL.txt' `
        -OutFile (Join-Path $vendor 'fonts\OFL-JetBrainsMono.txt') -TimeoutSec 60

    # --------------------------------------------------------- font awesome --
    Write-Host "Downloading Font Awesome Free $FA_VERSION ..."
    $faZip = Join-Path $work 'fa.zip'
    Invoke-WebRequest "https://use.fontawesome.com/releases/v$FA_VERSION/fontawesome-free-$FA_VERSION-web.zip" `
        -OutFile $faZip -TimeoutSec 300

    $hash = (Get-FileHash $faZip -Algorithm SHA256).Hash
    if (-not $SkipHashCheck -and $hash -ne $FA_SHA256) {
        throw "Font Awesome checksum mismatch.`n  expected $FA_SHA256`n  got      $hash"
    }
    Write-Host "  sha256 $hash"

    Expand-Archive $faZip -DestinationPath (Join-Path $work 'x-fa') -Force
    $fa = Join-Path $work "x-fa\fontawesome-free-$FA_VERSION-web"

    # css/ and webfonts/ MUST remain siblings: all.min.css uses url(../webfonts/…).
    New-Item -ItemType Directory -Force `
        (Join-Path $vendor 'fontawesome\css'), (Join-Path $vendor 'fontawesome\webfonts') | Out-Null

    # Copied verbatim — the leading /*! Font Awesome … */ comment is the
    # required CC BY 4.0 attribution. Do not minify or reformat.
    Copy-Item (Join-Path $fa 'css\all.min.css') (Join-Path $vendor 'fontawesome\css\') -Force
    # Only the two faces the UI actually uses. See static/vendor/README.md.
    Copy-Item (Join-Path $fa 'webfonts\fa-solid-900.woff2') (Join-Path $vendor 'fontawesome\webfonts\') -Force
    Copy-Item (Join-Path $fa 'webfonts\fa-regular-400.woff2') (Join-Path $vendor 'fontawesome\webfonts\') -Force
    Copy-Item (Join-Path $fa 'LICENSE.txt') (Join-Path $vendor 'fontawesome\') -Force

    Write-Host ''
    Write-Host 'Done. static/vendor now contains:' -ForegroundColor Green
    Get-ChildItem $vendor -Recurse -File |
        Select-Object @{ n = 'Path'; e = { $_.FullName.Replace("$vendor\", '') } }, Length |
        Format-Table -AutoSize
}
finally {
    Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
