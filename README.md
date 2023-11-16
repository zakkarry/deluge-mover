# `deluge-mover`

`deluge-mover` is a Python script to pause torrents on a cache drive, run unRAID's mover script, and resume them after the move has been completed.

## Introduction

`deluge-mover` is very simple. You only need to edit the `deluge-mover.py` file with your JSON-RPC URL (this is your Deluge WebUI with /json at the end), your WebUI password, and unRAID's cache drive's absolute path. This is the path where the torrent data resides, not the mount for the drive itself. (e.g. `/mnt/cache/torrents/complete`)

Read the notes in the script's configuration section and set them accordingly.

The concept for how this script operates was taken from [Bobokun](https://github.com/bobokun) and his mover script for qBittorrent.

Special thanks to [TRaSH](https://github.com/TRaSH-Guides) for the motivation to do this.

## Uses

Using a cache drive for your downloads in unRAID normally requires you to manually pause torrents, or shut down your torrent-client container, to move the files to permanent storage on your array. This script will automatically pause torrents residing on your cache drive, run the mover script, and resume them after.

This can be set on a timer so it periodically runs, keeping your cache drive ready for more.

## Installation

### Detailed Walkthrough

You can find a detailed walkthrough at [TRaSH's Deluge Mover Script Guide](https://trash-guides.info/Downloaders/Deluge/Tips/Unraid-Mover/) I've put together for this script.

### Brief Walkthrough (Advanced Users)

- You will need the NerdTools and User Scripts plugins installed on your unRAID server.
- Install `python-pip` `python-setuptools` and `python3` inside NerdTools
- Run `pip3 install requests` from the terminal in unRAID and set up a User Script to run this command when the array starts **OR** set up a venv for the script with `requests` installed.
- Edit `deluge-mover.py` with your WebUI URL, password, and preferred torrent age. (age is from time added to Deluge)
- Create a new User Script to execute `deluge-mover.py` on your schedule.
