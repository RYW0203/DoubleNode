#!/bin/bash

OMP_NUM_THREADS=1 taskset -c 0 python3 main.py -myPort 9994 -peerPort 9993 -name w0 &
OMP_NUM_THREADS=1 taskset -c 1 python3 main.py -myPort 9993 -peerPort 9994 -name w1 &

