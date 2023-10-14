#!/bin/bash

while true; do
    # Start the scripts in the background
    python publisher.py &
    pid1=$!
    python3.10 subscriber.py &
    pid2=$!

    # Let them run for 30 minutes (1800 seconds)
    sleep 1800

    # Kill the processes
    kill $pid1 $pid2
done
