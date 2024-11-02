# `deluge-presume`

`deluge-presume` is a Python script to pause or resume all torrents given an action as an argument.

Note: This branch is different than the `master` branch.

## Introduction

`deluge-presume` is very simple. You only need to edit the `deluge-presume.py` file with your JSON-RPC URL (this is your Deluge WebUI with /json at the end) and your WebUI password.

Read the notes in the script's configuration section and set them accordingly.

## Usage

### Commands:

  `python deluge-presume.py pause`

  `python deluge-presume.py resume`

### Uses

If you wish to pause or resume all torrents in your client without waiting for the UI to process, this will do that very quickly.

## Installation

Needs Python and the `requests` module (`pip install requests`).

### Brief Walkthrough (Advanced Users)

- You will need the NerdTools and User Scripts plugins installed on your unRAID server.
- Install `python-pip` `python-setuptools` and `python3` inside NerdTools
- Run `pip3 install requests` from the terminal in unRAID and set up a User Script to run this command when the array starts **OR** set up a venv for the script with `requests` installed.
- Edit `deluge-presume.py` with your WebUI URL, password, and preferred torrent age. (age is from time added to Deluge)
- Create a new User Script to execute `deluge-presume.py` on your schedule.

## Support Me

https://tip.ary.dev