: script to run Ollama on Windows
: based on template.bat from https://stackoverflow.com/questions/26551/how-can-i-pass-arguments-to-a-batch-file
@echo off
setlocal
goto :init

:usage
    echo USAGE:
    echo   %__BAT_NAME% [flags]
    echo.
    echo.  /?, --help           shows this help
    echo   -i, --ip             set OLLAMA_HOST environment variable
    echo   -o, --origins        set OLLAMA_ORIGINS environment variable
    goto :eof

:init
    set "__NAME=%~n0"
    set "__VERSION=1.0"
    set "__YEAR=2024"

    set "__BAT_FILE=%~0"
    set "__BAT_PATH=%~dp0"
    set "__BAT_NAME=%~nx0"

    set "OptHelp="

    set "OllamaIP="
    set "OllamaOrigins="

:parse
    if "%~1"=="" goto :main

    if /i "%~1"=="/?"         call :usage "%~2" & goto :end
    if /i "%~1"=="-?"         call :usage "%~2" & goto :end
    if /i "%~1"=="--help"     call :usage "%~2" & goto :end

    if /i "%~1"=="--ip"       set "OllamaIP=%~2"   & shift & shift & goto :parse
    if /i "%~1"=="-i"         set "OllamaIP=%~2"   & shift & shift & goto :parse

    if /i "%~1"=="--origins"  set "OllamaOrigins=%~2"   & shift & shift & goto :parse
    if /i "%~1"=="-o"         set "OllamaOrigins=%~2"   & shift & shift & goto :parse

    shift
    goto :parse

:main
    if defined OllamaIP (
        echo OLLAMA_HOST: "%OllamaIP%"
        set OLLAMA_HOST=%OllamaIP%
    )

    if defined OllamaOrigins (
        echo OLLAMA_ORIGINS: "%OllamaOrigins%"
        set OLLAMA_ORIGINS=%OllamaOrigins%
    )

    ollama serve

:end
    exit /B
