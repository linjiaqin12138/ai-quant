#!/bin/bash

function help() {
    echo "Usage ./runJob.sh <JobName> [...<params>]"
    echo "Example: ./runJob.sh buy_10_sell_5 arg1 arg2"
}


function main {
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    PROJECT_DIR="$( cd "$SCRIPT_DIR/../" && pwd )"

    if [ -z "$PYTHONPATH" ]; then
        export PYTHONPATH="$PROJECT_DIR"
    else 
        export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
    fi
    
    if [ -d "$PROJECT_DIR/.venv" ]; then
        platform="$(uname)"
        if [[ $platform == MINGW64* ]]; then
            source $PROJECT_DIR/.venv/Scripts/activate
        else
            source $PROJECT_DIR/.venv/bin/activate
        fi
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

    PYTHON_EXE="python"
    if command -v python3 &> /dev/null
    then
        # "Python 3 command is available"
        PYTHON_EXE="python3"
    fi
    # echo "$http_proxy" "$PROXY" "$MYSQL_DB"
    nohup $PYTHON_EXE $job_name $@ &

    # pid=$!

    echo $!
}

main $@