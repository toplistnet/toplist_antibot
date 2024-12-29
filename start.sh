#!/bin/bash
while :
do
    hypercorn app.app:app -b 0.0.0.0:8099 \
        --workers 10 \
        --log-config logging.conf \
        --backlog 9200 \
        --graceful-timeout 2 \
        --access-logfile access.log \
        --error-logfile error.log \
        --keep-alive 10

        # --max-requests 1800 \
        # --max-requests-jitter 400 \
    sleep 1
done
