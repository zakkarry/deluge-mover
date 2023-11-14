#!/usr/bin/env python3
import asyncio
import json
import random
import requests
import time
from enum import Enum
from os import path, walk, system
from urllib.parse import urlparse

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

# this is the absolute host path to your cache drive's downloads
# you only need this to be changed/set if using 'check_fs = True'
cache_download_path = "/mnt/cache/torrents/completed"

# the age range of days to look for relevant torrents to move
age_day_min = 2
age_day_max = 5


# error codes we could potentiall receive
class DelugeErrorCode(Enum):
    NO_AUTH = 1
    BAD_METHOD = 2
    CALL_ERR = 3
    RPC_FAIL = 4
    BAD_JSON = 5


class DelugeHandler:
    def __init__(self):
        self.deluge_cookie = None
        self.session = requests.Session()

    async def call(self, method, params, retries=1):
        url = urlparse(deluge_webui).geturl()
        headers = {"Content-Type": "application/json"}
        id = random.randint(0, 0x7FFFFFFF)

        # set our cookie if we have it
        if self.deluge_cookie:
            headers["Cookie"] = self.deluge_cookie

        if method == "auth.login":
            print(f"Connecting to Deluge: {url}")

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
                f"Failed to connect to Deluge at {url}"
            ) from network_error

        # make sure the json response is valid
        try:
            json_response = response.json()
        except json.JSONDecodeError as json_parse_error:
            raise ValueError(
                f"Deluge method {method} response was non-JSON: {json_parse_error}"
            )

        # check for authorization failures, and retry once
        if json_response.get("error", [None]) != None:
            if (
                json_response.get("error", [None]).get("code")
                == DelugeErrorCode.NO_AUTH
                and retries > 0
            ):
                self.deluge_cookie = None
                await self.call("auth.login", [deluge_password], 0)

                if self.deluge_cookie:
                    return await self.call(method, params)
                else:
                    raise ConnectionError(
                        "Connection lost with Deluge. Reauthentication failed."
                    )

        self.handle_cookies(response.headers)
        return json_response

    def handle_cookies(self, headers):
        deluge_cookie = headers.get("Set-Cookie")
        if deluge_cookie:
            deluge_cookie = deluge_cookie.split(";")[0]
        else:
            deluge_cookie = None


def find_file_on_cache(dir, file):
    for root, dirs, files in walk(dir):
        if file in files:
            return path.join(root, file)
    return None


def filter_added_time(t_object):
    cached_file = False
    time_elapsed = int(time.time()) - t_object.get("time_added", [None])
    current_path = path.join(cache_download_path, t_object.get("name", [None]))
    if time_elapsed >= (age_day_min * 60 * 60 * 24) and time_elapsed <= (
        age_day_max * 60 * 60 * 24
    ):
        if check_fs:
            if path.exists(current_path):
                cached_file = True
            elif (
                find_file_on_cache(cache_download_path, t_object.get("name", [None]))
                != None
            ):
                cached_file = True
        else:
            cached_file = True
        return cached_file
    return False


async def main():
    deluge_handler = DelugeHandler()

    try:
        # auth.login
        auth_response = await deluge_handler.call("auth.login", [deluge_password], 0)
        print("Authentication response:", auth_response)

        # get torrent list
        torrent_list = (
            (
                await deluge_handler.call(
                    "web.update_ui",
                    [["name", "save_path", "progress", "time_added"], {}],
                )
            )
            .get("result", [None])
            .get("torrents", [None])
        )

        # make sure list exists
        if torrent_list != None:
            filtered_torrents = filter(
                lambda kv: filter_added_time(kv[1]), torrent_list.items()
            )

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
                    f"{values.get('name', [None])} ({hash})"
                    f"\n\tsave_path: {save_path}\n"
                )

                # pause relevant torrents
                await deluge_handler.call("core.pause_torrent", [hash])

            time.sleep(10)

            # run the mover
            print("Starting Mover")
            system("/usr/local/sbin/mover start")

            time.sleep(10)

            # resume all the torrents we previously paused
            for hash in filtered_torrents:
                await deluge_handler.call("core.resume_torrent", [hash])

    except Exception as e:
        print(f"Error: {e}")

    deluge_handler.session.close()


async def run_main():
    await main()


if __name__ == "__main__":
    asyncio.run(run_main())
