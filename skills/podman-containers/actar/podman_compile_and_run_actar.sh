#!/bin/bash

# ACTAR Compile and Run Script
# Unified script to compile and optionally run analysis with specified run numbers
# Updated for ubuntu user and actar container

set -e

# This script is intended to be run from the host root/ directory. The UI
# polls this file to display the last compilation result.
COMPILE_STATUS_FILE="$(pwd)/podman_compile_result.txt"
write_compile_status() {
    printf '%s %s\n' "$1" "$(date --iso-8601=seconds)" > "$COMPILE_STATUS_FILE"
}

# Usage function
usage() {
    echo "Usage: $0 [OPTIONS] [RUN_NUMBER]"
    echo ""
    echo "OPTIONS:"
    echo "  -c, --compile-only    Compile only, do not run"
    echo "  -r, --run-only       Run only (skip compilation)"
    echo "  -s, --start-event N  Set start event (default: 0)"
    echo "  -n, --num-events N   Set number of events (default: 10)"
    echo "  -x, --clean         Run 'make clean' only (standalone option)"
    echo "  -h, --help          Show this help"
    echo ""
    echo "EXAMPLES:"
    echo "  $0                   # Compile only"
    echo "  $0 277               # Compile and run with run=277, default events"
    echo "  $0 -s 100 -n 50 277  # Compile and run with run=277, start_event=100, number_of_events=50"
    echo "  $0 -r 277           # Run only (no compilation)"
    echo "  $0 -c               # Compile only (explicit)"
    echo "  $0 -x               # Run make clean only"
    echo ""
}

# Default values
COMPILE=true
RUN=false
START_EVENT=0
NUM_EVENTS=10
RUN_NUMBER=""
CLEAN=false
OTHER_ACTION=false
CONTAINER_NAME="running_actar"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--compile-only)
            OTHER_ACTION=true
            COMPILE=true
            RUN=false
            shift
            ;;
        -r|--run-only)
            OTHER_ACTION=true
            COMPILE=false
            RUN=true
            shift
            ;;
        -s|--start-event)
            OTHER_ACTION=true
            START_EVENT="$2"
            shift 2
            ;;
        -n|--num-events)
            OTHER_ACTION=true
            NUM_EVENTS="$2"
            shift 2
            ;;
        -x|--clean)
            CLEAN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "Unknown option $1"
            usage
            exit 1
            ;;
        *)
            # Assume it's a run number
            OTHER_ACTION=true
            RUN_NUMBER="$1"
            RUN=true
            shift
            ;;
    esac
done

if [ "$CLEAN" = true ] && [ "$OTHER_ACTION" = true ]; then
    echo "ERROR: -x/--clean is standalone; do not combine it with other options or a run number"
    exit 1
fi

cat <<EOF
======================================================================
ACTAR COMPILE AND RUN
All compilation and execution use the running container '${CONTAINER_NAME}'.
The compiler, ROOT, libraries, and other dependencies come from the container.
Host files are used only through the configured Podman shares.
======================================================================
EOF

# Check if main.C exists (we should be in the root/ directory on host)
if [ ! -e "main.C" ]; then
    write_compile_status FAIL
    echo "ERROR: main.C not found. Are you in the root/ directory on the host?"
    echo "Expected to be in: $(pwd)/root/ or similar directory containing main.C"
    exit 1
fi

# Check if container is running
if ! podman ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container '${CONTAINER_NAME}' is not running."
    echo "Please start it first with:"
    echo "  podman-ui-actar --start"
    exit 1
fi

echo "=== ACTAR Compile and Run ==="

if [ "$CLEAN" = true ]; then
    echo "Running make clean only..."
    podman exec -it "${CONTAINER_NAME}" bash -c "source /home/ubuntu/root/bin/thisroot.sh && cd /home/ubuntu/ACTAR/analysis_code/root_remote && make clean"
    echo "Clean completed successfully."
    exit 0
fi

# Compilation step
if [ "$COMPILE" = true ]; then
    write_compile_status RUNNING
    trap 'write_compile_status FAIL' ERR
    echo "Compiling..."
    podman exec -it "${CONTAINER_NAME}" bash -c "source /home/ubuntu/root/bin/thisroot.sh && cd /home/ubuntu/ACTAR/analysis_code/root_remote && make"
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Compilation failed"
        exit 1
    fi
    write_compile_status OK
    trap - ERR
    echo "Compilation completed successfully."
fi

# Run step
if [ "$RUN" = true ] && [ -n "$RUN_NUMBER" ]; then
    echo "Running with parameters:"
    echo "  Run number: $RUN_NUMBER"
    echo "  Start event: $START_EVENT"
    echo "  Number of events: $NUM_EVENTS"
    
    # Special case for run 277 (canonical test) - use simpler command like original script
    if [ "$RUN_NUMBER" = "277" ] && [ "$START_EVENT" = "0" ] && [ "$NUM_EVENTS" = "10" ]; then
        echo "Using canonical run 277 settings..."
        podman exec -it "${CONTAINER_NAME}" bash -c "source /home/ubuntu/root/bin/thisroot.sh && cd /home/ubuntu/ACTAR/analysis_code/root_remote && make run run=277"
    else
        podman exec -it "${CONTAINER_NAME}" bash -c "source /home/ubuntu/root/bin/thisroot.sh && cd /home/ubuntu/ACTAR/analysis_code/root_remote && make run run=${RUN_NUMBER} start_event=${START_EVENT} number_of_events=${NUM_EVENTS}"
    fi
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Run failed"
        exit 1
    fi
    echo "Run completed successfully."
    
elif [ "$RUN" = true ]; then
    echo "ERROR: Run requested but no run number provided"
    usage
    exit 1
fi

echo "=== Done ==="