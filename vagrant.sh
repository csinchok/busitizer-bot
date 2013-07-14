#!/usr/bin/env bash

sudo apt-get update
sudo apt-get install -y libjpeg-dev libpng12-dev build-essential cmake python-dev python-pip
sudo pip install -r /var/busitizer/requirements.txt

sudo apt-get install -y libcv2.3 libcvaux2.3 libhighgui2.3 python-opencv opencv-doc libcv-dev libcvaux-dev libhighgui-dev