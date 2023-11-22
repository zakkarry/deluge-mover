#!/usr/bin/env python3
import asyncio
import json
import random
import requests
from enum import Enum
from urllib.parse import urlparse

### CONFIGURATION VARIABLES ###

# this webui will need to be the JSON-RPC endpoint
# this ends with '/json'
deluge_webui = "http://127.0.0.1:8112/json"
deluge_password = "deluged"

# remove extra labels
remove_labels = [
    "sonarr.cross-seed",
    "radarr.cross-seed",
    "non-imported.cross-seed",
    "not-met.cross-seed",
    "imported.cross-seed",
    "cross-seed.cross-seed",
    "limiter.cross-seed",
]
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

    async def call(self, method, params, retries=1):
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
                await self.call("auth.login", [deluge_password], 0)

                if self.deluge_cookie:
                    return await self.call(method, params)
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


def valued_trackers(trackers):
    if "valuable_tracker" in trackers:
        return True
    else:
        False


def notmet_release(release):
    lowern = release.lower()
    if (
        "daily.show" in lowern
        or "colbert" in lowern
        or "bill.maher" in lowern
        or "ethel" in lowern
        or "edith" in lowern
        or "syncopy" in lowern
        or "cbfm" in lowern
        or "eleanor" in lowern
        or "accomplishedyak" in lowern
    ):
        return True
    else:
        return False


def limited_tracker(t_object, limited):
    trackers = t_object[1].get("tracker", None)
    name = t_object[1].get("name", [None])
    label = t_object[1].get("label", [None])

    if len(trackers) == 0:
        return False
    if limited is True and label == "limiter":
        return False
    if label == "sonarr" or label == "radarr":
        return False
    if limited == 3:
        if notmet_release(name) and label != "not-met" and label != "non-imported":
            # print(f"{name} - {trackers} - {label}")
            return True
        else:
            return False

    if valued_trackers(trackers):
        if limited is True:
            return False
        else:
            if (notmet_release(name)) or (
                label == "not-met" or label == "imported" or label == "non-imported"
            ):
                return False
            else:
                return True

    if label != "limiter" or label != "non-imported" or label != "not-met":
        if "cross-seed" in label:
            if valued_trackers(trackers):
                if limited is True:
                    return False
                else:
                    return True
            else:
                if limited is True:
                    return True
                else:
                    return False
        elif label == "imported":
            if valued_trackers(trackers) is False:
                if limited is True:
                    return True
                else:
                    return False
            else:
                if limited is True:
                    return True
                else:
                    return False
    else:
        if limited is True and label != "limiter":
            return False
        else:
            return True


async def main():
    deluge_handler = DelugeHandler()

    try:
        # auth.login
        auth_response = await deluge_handler.call("auth.login", [deluge_password], 0)
        # checks the status of webui being connected, and connects to the daemon
        webui_connected = (await deluge_handler.call("web.connected", [], 0)).get(
            "result"
        )
        if webui_connected is False:
            web_ui_daemons = await deluge_handler.call("web.get_hosts", [], 0)
            webui_connected = await deluge_handler.call(
                "web.connect", [web_ui_daemons.get("result")[0][0]], 0
            )
            if webui_connected is False:
                print(
                    f"\n\n[{CRED}error{CEND}]: {CYELLOW}Your WebUI is not automatically connectable to the Deluge daemon.{CEND}\n"
                    f"{CYELLOW}\t Open the WebUI's connection manager to resolve this.{CEND}\n\n"
                )
                exit(1)
        print(
            f"[{CGREEN}json-rpc{CEND}/{CYELLOW}auth.login{CEND}]",
            auth_response,
            "\n\n",
        )
        if auth_response.get("result") is False:
            exit(1)
        # get torrent list
        torrent_list = (
            (
                await deluge_handler.call(
                    "web.update_ui",
                    [["name", "tracker", "label"], {}],
                )
            )
            .get("result", [None])
            .get("torrents", [None])
        )
        # make sure list exists
        if torrent_list != None:
            limited_torrents = list(
                filter(
                    lambda kv: limited_tracker(kv, True),
                    torrent_list.items(),
                )
            )

            if len(limited_torrents) == 0:
                print(
                    f"\n\n[{CGREEN}deluge-labeler{CEND}]: {CBOLD}no eligible 'limited' torrents.{CEND}\n\n"
                )
            else:
                print(
                    f"\n\n[{CGREEN}deluge-labeler{CEND}]: {CBOLD}found {len(limited_torrents)} eligible 'limited' torrents.{CEND}\n\n"
                )
                # loop through items in torrent list
                for hash, values in limited_torrents:
                    print(
                        f"[{CRED}label.set_torrent{CEND}]: {CBOLD}{values.get('name', [None])}{CEND}"
                        f"\n\t\t\t {CYELLOW}label_activity{CEND}: {values.get('label', [None])} -> limiter"
                        f"\n\t\t\t {CYELLOW}infohash{CEND}: {hash}"
                        f"\n\t\t\t {CYELLOW}tracker{CEND}: {values.get('tracker', [None])}\n"
                    )
                    # move relevant torrents
                    await deluge_handler.call("label.set_torrent", [hash, "limiter"])

            notmet_torrents = list(
                filter(
                    lambda kv: limited_tracker(kv, 3),
                    torrent_list.items(),
                )
            )
            if len(notmet_torrents) == 0:
                print(
                    f"\n\n[{CGREEN}deluge-labeler{CEND}]: {CBOLD}no eligible 'not-met' torrents.{CEND}\n\n"
                )
            else:
                print(
                    f"\n\n[{CGREEN}deluge-labeler{CEND}]: {CBOLD}found {len(notmet_torrents)} eligible 'not-met' torrents.{CEND}\n\n"
                )
                # loop through items in torrent list
                for hash, values in notmet_torrents:
                    print(
                        f"[{CRED}label.set_torrent{CEND}]: {CBOLD}{values.get('name', [None])}{CEND}"
                        f"\n\t\t\t {CYELLOW}label_activity{CEND}: {values.get('label', [None])} -> not-met"
                        f"\n\t\t\t {CYELLOW}infohash{CEND}: {hash}"
                        f"\n\t\t\t {CYELLOW}tracker{CEND}: {values.get('tracker', [None])}\n"
                    )
                    # move relevant torrents
                    await deluge_handler.call("label.set_torrent", [hash, "not-met"])

            imported_torrents = list(
                filter(
                    lambda kv: limited_tracker(kv, False),
                    torrent_list.items(),
                )
            )
            if len(imported_torrents) == 0:
                print(
                    f"\n[{CGREEN}deluge-labeler{CEND}]: {CBOLD}no eligible 'imported' torrents.{CEND}\n\n"
                )
            else:
                print(
                    f"\n[{CGREEN}deluge-labeler{CEND}]: {CBOLD}found {len(imported_torrents)} eligible 'imported' torrents.{CEND}\n\n"
                )

                # loop through items in torrent list
                for hash, values in imported_torrents:
                    print(
                        f"[{CRED}label.set_torrent{CEND}]: {CBOLD}{values.get('name', [None])}{CEND}"
                        f"\n\t\t\t {CYELLOW}label_activity{CEND}: {values.get('label', [None])} -> imported"
                        f"\n\t\t\t {CYELLOW}infohash{CEND}: {hash}"
                        f"\n\t\t\t {CYELLOW}tracker{CEND}: {values.get('tracker', [None])}\n"
                    )
                    # move relevant torrents
                    await deluge_handler.call("label.set_torrent", [hash, "imported"])

            for item in remove_labels:
                await deluge_handler.call("label.remove", [item])
        else:
            print(
                f"\n\n[{CRED}error{CEND}]: {CYELLOW}Your WebUI is likely not connected to the Deluge daemon. Open the WebUI to resolve this.{CEND}\n\n"
            )
            exit(1)
    except Exception as e:
        print(f"\n\n[{CRED}error{CEND}]: {CBOLD}{e}{CEND}\n\n")

    deluge_handler.session.close()


async def run_main():
    await main()


if __name__ == "__main__":
    asyncio.run(run_main())
