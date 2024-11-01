#!/bin/sh

# This script need to be launch after the gui is fully loaded
set -ex

# Mount external disk
sudo mkdir -p /mnt/nvme0n1
#sudo mount /dev/nvme0n1 /mnt/nvme0n1
sudo mount /dev/nvme0n1p1 /mnt/nvme0n1
sudo chown -R user /mnt/nvme0n1

# Deleting videos older than 7 days
cd /mnt/nvme0n1
sudo find -type f -mtime +7 -exec rm -rf {} \;

# Move into the repository SIR-Lightboard
cd /home/user/SIR-Lightboard

# Copy obs global config
mkdir -p /home/user/.config/obs-studio/
cp /home/user/SIR-Lightboard/obs/obs-global-config.ini /home/user/.config/obs-studio/global.ini
chmod +777 /home/user/.config/obs-studio/global.ini

# Copy obs profile
mkdir -p /home/user/.config/obs-studio/basic/profiles/MyProfile
cp /home/user/SIR-Lightboard/obs/obs-profile-config.ini /home/user/.config/obs-studio/basic/profiles/MyProfile/basic.ini
chmod +777 /home/user/.config/obs-studio/basic/profiles/MyProfile/basic.ini

# Copy obs scene
mkdir -p /home/user/.config/obs-studio/basic/scenes
cp /home/user/SIR-Lightboard/obs/obs-scene-config.json /home/user/.config/obs-studio/basic/scenes/MyScene.json
chmod +777 /home/user/.config/obs-studio/basic/scenes/MyScene.json

# Install all of the packets write in the requirements.txt
sudo pip install -r requirements.txt --break-system-packages

# Launch obs
obs &

# Get the log into the error.txt file
sudo /usr/bin/python3 /home/user/SIR-Lightboard/main.py 2> /home/user/error.txt &
