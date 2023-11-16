# `deluge-mover`

`deluge-mover` is a Python script to pause torrents on a cache drive, run unRAID's mover script, and resume them after the move has been completed.

Note: This branch is different than the `master` branch.

## Introduction

`deluge-mover` is very simple. You only need to edit the `deluge-mover.py` file with your JSON-RPC URL (this is your Deluge WebUI with /json at the end), your WebUI password, and unRAID cache drive's absolute path. This is the path where the torrent data resides that you wish to not pause/match, not the mount for the drive itself. (e.g. `/mnt/user/torrents/complete`)

Read the notes in the script's configuration section and set them accordingly.

## Uses

If you wish to pause all torrents on your array, to spin down the drives, you can use this script to do so. Simply configure the path where the torrents on your cache would reside in the .py file and your Deluge WebUI details.

The sleep variable is a number, in hours, which the torrents will remain paused.

## Installation

### Detailed Walkthrough

You can find a detailed walkthrough at [TRaSH's Deluge Mover Script Guide](https://trash-guides.info/Downloaders/Deluge/Tips/Unraid-Mover/) I've put together for this script.

### Brief Walkthrough (Advanced Users)

- You will need the NerdTools and User Scripts plugins installed on your unRAID server.
- Install `python-pip` `python-setuptools` and `python3` inside NerdTools
- Run `pip3 install requests` from the terminal in unRAID and set up a User Script to run this command when the array starts **OR** set up a venv for the script with `requests` installed.
- Edit `deluge-mover.py` with your WebUI URL, password, and preferred torrent age. (age is from time added to Deluge)
- Create a new User Script to execute `deluge-mover.py` on your schedule.

## Support Me

https://tip.ary.dev