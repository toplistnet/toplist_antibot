#!/bin/bash
while ! python3 main.py antibot-server; do
    echo "restarting.."
done