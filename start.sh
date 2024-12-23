#!/bin/bash
while ! uvicorn main_new:app; do
    echo "restarting.."
done
