#!/bin/bash

function help() {
    echo "Usage ./runJob.sh <JobName> [...<params>]"
    echo "Example: ./runJob.sh buy_10_sell_5 arg1 arg2"
}

function check_second_param() {
    if [ -z "$2" ] || [[ "$2" =~ ^-.* ]]; then
        echo "Option $1 requires an argument"
        echo ""
        usage
        exit 1
    fi
}

function main {
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    PROJECT_DIR="$( cd "$SCRIPT_DIR/../" && pwd )"
    export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
    if [ -d "$PROJECT_DIR/.venv" ]; then
        source "$PROJECT_DIR/.venv/bin/activate" 
    fi
    source "$PROJECT_DIR/.env"

    if [ $# -eq 0 ]; then
        echo "Miss job name to be run"
        help
        exit 1
    fi
    
    job_name="$SCRIPT_DIR/jobs/$1"
    if [[ "$job_name" != *.py ]]; then
        job_name="${job_name}.py"
    fi

    shift 1

    nohup python3 $job_name $@ &

    # pid=$!

    echo $!
}

main $@