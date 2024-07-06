#!/bin/bash
# Script to run Ollama on Linux

#!/bin/bash
# Script to run Ollama on Unix-like systems

function usage {
    echo "USAGE:"
    echo "  $0 [flags]"
    echo
    echo "  -h, --help           shows this help"
    echo "  -i, --ip             set OLLAMA_HOST environment variable"
    echo "  -o, --origins        set OLLAMA_ORIGINS environment variable"
}

function main {
    if [[ -n "$OllamaIP" ]]; then
        echo "OLLAMA_HOST: $OllamaIP"
        export OLLAMA_HOST="$OllamaIP"
    fi

    if [[ -n "$OllamaOrigins" ]]; then
        echo "OLLAMA_ORIGINS: $OllamaOrigins"
        export OLLAMA_ORIGINS="$OllamaOrigins"
    fi

    ollama serve
}

# Default values
OllamaIP=""
OllamaOrigins=""

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -i|--ip)
            OllamaIP="$2"
            shift
            ;;
        -o|--origins)
            OllamaOrigins="$2"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
    shift
done

main
