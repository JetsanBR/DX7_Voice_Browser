<#
.SYNOPSIS
    Starts the DX7 Voice Browser locally.
#>

& "$PSScriptRoot\venv\Scripts\Activate.ps1"

uvicorn app:app --reload --host 127.0.0.1 --port 8000
