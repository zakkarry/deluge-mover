#!/usr/bin/env python3
import json
import random
import requests
import time
from enum import Enum
from os import path, walk, system
from urllib.parse import urlparse

### CONFIGURATION VARIABLES ###

# this webui will need to be the JSON-RPC endpoint
# this ends with '/json'
deluge_webui = "http://localhost:8112/json"
deluge_password = "deluged"

# this changes whether the actual cache drive is checked for
# applicable files to pause/move before pausing.
#
# if this is false, it will pause all torrents in the age-range
# instead of only torrents in that range that exist on the cache
check_fs = False

# if you are using the mover tuner and don't want to use it for
# this script, set this to true
#
# if you do not use mover tuner, leave this as false
use_mover_old = False

# this is the absolute host path to your cache drive's downloads
# you only need this to be changed/set if using 'check_fs = True'
cache_download_path = "/mnt/cache/torrents/completed"

# the age range of days to look for relevant torrents to move
# i dont recommend setting age_day_max to less than the schedule
# you run the script on...
#
# if you run every 7 days, this should be at least 7 to prevent
# files from being stuck on your cache forever
#
# 0 disables age_day_max
# set both age vars to 0 to move everything on your cache drive

age_day_min = 3
age_day_max = 0

### STOP EDITING HERE ###
### STOP EDITING HERE ###
### STOP EDITING HERE ###
### STOP EDITING HERE ###


# error codes we could potentially receive
class DelugeErrorCode(Enum):
    NO_AUTH = 1
    BAD_METHOD = 2
    CALL_ERR = 3
    RPC_FAIL = 4
    BAD_JSON = 5


# color codes for terminal
use_colors_codes = False

CRED = "\033[91m" if (use_colors_codes) else ""
CGREEN = "\33[32m" if (use_colors_codes) else ""
CYELLOW = "\33[33m" if (use_colors_codes) else ""
CBLUE = "\33[4;34m" if (use_colors_codes) else ""
CBOLD = "\33[1m" if (use_colors_codes) else ""
CEND = "\033[0m" if (use_colors_codes) else ""


class DelugeHandler:
    def __init__(self):
        self.deluge_cookie = None
        self.session = requests.Session()

    def call(self, method, params, retries=1):
        url = urlparse(deluge_webui).geturl()
        headers = {"Content-Type": "application/json"}
        id = random.randint(0, 0x7FFFFFFF)

        # set our cookie if we have it
        if self.deluge_cookie:
            headers["Cookie"] = self.deluge_cookie

        if method == "auth.login":
            print(
                f"[{CGREEN}init{CEND}/{CYELLOW}script{CEND}] -> {CYELLOW}Connecting to Deluge:{CEND} {CBLUE}{url}{CEND}"
            )

        # send our request to the JSON-RPC endpoint
        try:
            response = self.session.post(
                url,
                data=json.dumps({"method": method, "params": params, "id": id}),
                headers=headers,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as network_error:
            raise ConnectionError(
                f"[{CRED}json-rpc{CEND}/{CRED}error{CEND}]: Failed to connect to Deluge at {CBLUE}{url}{CEND}"
            ) from network_error

        # make sure the json response is valid
        try:
            json_response = response.json()
        except json.JSONDecodeError as json_parse_error:
            raise ValueError(
                f"[{CRED}json-rpc{CEND}/{CRED}error{CEND}]: Deluge method {method} response was {CYELLOW}non-JSON{CEND}: {json_parse_error}"
            )

        # check for authorization failures, and retry once
        if json_response.get("error", [None]) != None:
            if (
                json_response.get("error", [None]).get("code")
                == DelugeErrorCode.NO_AUTH
                and retries > 0
            ):
                self.deluge_cookie = None
                self.call("auth.login", [deluge_password], 0)

                if self.deluge_cookie:
                    return self.call(method, params)
                else:
                    raise ConnectionError(
                        f"[{CRED}json-rpc{CEND}/{CRED}error{CEND}]: Connection lost with Deluge. Reauthentication {CYELLOW}failed{CEND}."
                    )

        self.handle_cookies(response.headers)
        return json_response

    def handle_cookies(self, headers):
        deluge_cookie = headers.get("Set-Cookie")
        if deluge_cookie:
            deluge_cookie = deluge_cookie.split(";")[0]
        else:
            deluge_cookie = None


def find_file_on_cache(dir, target):
    for root, dirs, files in recursive_path_list(dir):
        if target in files or target in dirs:
            return path.join(root, target)
    return None


def recursive_path_list(dir):
    return [(root, dirs, files) for root, dirs, files in walk(dir)]


def filter_added_time(t_object):
    cached_file = False
    if (
        t_object[1].get("time_added", None) is None
        or t_object[1].get("name", None) is None
    ):
        return False
    time_elapsed = int(time.time()) - t_object[1].get("time_added", [None])
    assumed_path = path.join(cache_download_path, t_object[1].get("name", [None]))
    if time_elapsed >= (age_day_min * 60 * 60 * 24) and (
        (time_elapsed <= (age_day_max * 60 * 60 * 24)) or (age_day_max == 0)
    ):
        if check_fs:
            if path.exists(assumed_path):
                cached_file = True
            elif (
                find_file_on_cache(cache_download_path, t_object[1].get("name", [None]))
                != None
            ):
                cached_file = True
        else:
            cached_file = True
        return cached_file
    return False


def main():
    deluge_handler = DelugeHandler()

    try:
        # auth.login
        auth_response = deluge_handler.call("auth.login", [deluge_password], 0)
        webui_connected = deluge_handler.call("web.connected", [], 0)
        print(f"[json-rpc/web.connected] {webui_connected}")

        time.sleep(2)
        # get hosts list
        web_ui_daemons = deluge_handler.call("web.get_hosts", [], 0).get("result")
        # check which host is connected
        for daemon in web_ui_daemons:
            webui_connected_host = daemon[0]
            webui_connected = deluge_handler.call(
                "web.get_host_status", [webui_connected_host], 0
            ).get("result")
            if webui_connected[1] == "Connected":
                # reconnect the web daemon to the previously connected host
                web_disconnect = deluge_handler.call("web.disconnect", [], 0)
                print(f"[json-rpc/web.disconnect] {web_disconnect}")
                break

        # checks the status of webui being connected, and connects to the daemon
        webui_connected = webui_connected[1]
        if webui_connected == "Online":
            webui_connected = deluge_handler.call(
                "web.connect", [webui_connected_host], 0
            )
            time.sleep(1)
            if webui_connected.get("result") is None:
                print(
                    f"\n\n[{CRED}error{CEND}]: {CYELLOW}Your WebUI is not automatically connectable to the Deluge daemon.{CEND}\n"
                    f"{CYELLOW}\t Open the WebUI's connection manager to resolve this.{CEND}\n\n"
                )
                exit(1)
            else:
                print(f"[json-rpc/web.connect] Successfully reconnected to daemon.")
        print(
            f"[{CGREEN}json-rpc{CEND}/{CYELLOW}auth.login{CEND}]",
            auth_response,
            "\n\n",
        )
        if auth_response.get("result") is False:
            exit(1)
        # get torrent list
        torrent_list = (
            deluge_handler.call(
                "web.update_ui",
                [["name", "save_path", "progress", "time_added"], {}],
            )
            .get("result", [None])
            .get("torrents", [None])
        )

        # make sure list exists
        if torrent_list != None:
            filtered_torrents = list(
                filter(lambda kv: filter_added_time(kv), torrent_list.items())
            )

            if len(filtered_torrents) == 0:
                print(
                    f"\n\n[{CGREEN}deluge-mover{CEND}]: {CBOLD}no eligible torrents.\n\t\tscript completed.{CEND}\n\n"
                )
                exit(0)
            # loop through items in torrent list
            for hash, values in filtered_torrents:
                if check_fs:
                    save_path = path.join(
                        cache_download_path, values.get("name", [None])
                    )
                else:
                    save_path = path.join(
                        values.get("save_path", [None]), values.get("name", [None])
                    )

                print(
                    f"[{CRED}pause_torrent{CEND}]: {CBOLD}{values.get('name', [None])}{CEND}"
                    f"\n\t\t {CYELLOW}info_hash{CEND}: {hash}"
                    f"\n\t\t {CYELLOW}save_path{CEND}: {save_path}\n"
                )

                # pause relevant torrents
                deluge_handler.call("core.pause_torrent", [hash])
            print(
                f"[{CRED}pause_summary{CEND}]: paused {CYELLOW}{CBOLD}{len(filtered_torrents)}{CEND} torrents...\n"
            )

            time.sleep(10)

            # run the mover
            print(
                f"[{CGREEN}init{CEND}] -> {CYELLOW}{CBOLD}Executing unRAID Mover...{CEND}\n"
            )
            time.sleep(3)
            deluge_handler.session.close()

            if use_mover_old:
                system("/usr/local/sbin/mover.old start")
            else:
                system("/usr/local/sbin/mover start")

            time.sleep(10)
            print("\n\n")
            deluge_handler = DelugeHandler()
            auth_response = deluge_handler.call("auth.login", [deluge_password], 0)
            time.sleep(1)

            # resume all the torrents we previously paused
            for hash, values in filtered_torrents:
                deluge_handler.call("core.resume_torrent", [hash])
                print(
                    f"[{CGREEN}resume_torrent{CEND}]: {CBOLD}{values.get('name', [None])}{CEND}"
                    f"\n\t\t  {CYELLOW}info_hash{CEND}: {hash}\n"
                )

            print(
                f"[{CGREEN}resume_summary{CEND}]: resumed {CYELLOW}{CBOLD}{len(filtered_torrents)}{CEND} torrents...\n"
            )
            print(
                f"\n\n[{CGREEN}deluge-mover{CEND}]: {CBOLD}script completed.{CEND}\n\n"
            )
        else:
            print(
                f"\n\n[{CRED}error{CEND}]: {CYELLOW}Your WebUI is likely not connected to the Deluge daemon. Open the WebUI to resolve this.{CEND}\n\n"
            )
            exit(1)
    except Exception as e:
        print(f"\n\n[{CRED}error{CEND}]: {CBOLD}{e}{CEND}\n\n")

    deluge_handler.session.close()


if __name__ == "__main__":
    main()
