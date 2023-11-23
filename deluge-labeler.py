#!/usr/bin/env python3
import asyncio
import json
import random
import requests
from enum import Enum
from urllib.parse import urlparse
from functools import partial

### CONFIGURATION VARIABLES ###

# this webui will need to be the JSON-RPC endpoint
# this ends with '/json'
deluge_webui = "http://127.0.0.1:8112/json"
deluge_password = "deluged"

# runs without labeling changes
dryrun = True

# remove extra labels after
remove_labels = [
    "sonarr.cross-seed",
    "radarr.cross-seed",
    "non-imported.cross-seed",
    "not-met.cross-seed",
    "imported.cross-seed",
    "cross-seed.cross-seed",
    "limiter.cross-seed",
]

# list of valuable trackers (matches announce url)
valuable_trackers = ["valueable-tracker-domain"]

# list of terms (case-insensitive) to send to
# seeding requirements not-met label
notmet_filter = [
    "daily.show",
    "colbert",
    "bill.maher",
    "ethel",
    "edith",
    "syncopy",
    "cbfm",
    "eleanor",
    "accomplishedyak",
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
    return list(filter(lambda i: i in trackers, valuable_trackers))


def notmet_release(release):
    lowern = release.lower()
    return any(i in lowern for i in notmet_filter)


def limited_tracker(t_object, limited=False):
    trackers = t_object[1].get("tracker", None)
    name = t_object[1].get("name", [None])
    label = t_object[1].get("label", [None])

    if not trackers:
        return False
    if limited is True and label == "limiter":
        return False  # correct label already set
    if label == "sonarr" or label == "radarr":
        return False  # always ignore *arr-managed torrents
    if limited == 3:
        # add 'not-met' label only for specific torrents whose label is not of {not-met,non-imported}:
        return notmet_release(name) and label != "not-met" and label != "non-imported"

    # from here on, only input value of limited = {True,False} values are processed:
    if valued_trackers(trackers):
        if limited is True:
            return False  # we don't want to set 'limiter' label if torrent is of valuable tracker because full BW should be allowed for them
        else:
            # we don't want to set 'imported' label for some specific torrents OR if their label is of {not-met,imported,non-imported}
            return not (
                notmet_release(name)
                or (
                    label == "not-met" or label == "imported" or label == "non-imported"
                )
            )

    # from here on we process limited = {True,False} of _non-valued_ trackers;
    # we're deciding over setting either 'imported' OR 'limiter' labels:
    if label != "limiter" or label != "non-imported" or label != "not-met":
        if "cross-seed" in label or label == "imported":
            return limited


async def main():
    async def filter_and_label(filter_fun, label):
        filtered_torrents = [kv for kv in torrent_list.items() if filter_fun(kv)]
        if not filtered_torrents:
            print(
                f"\n\n[{CGREEN}deluge-labeler{CEND}]: {CBOLD}no eligible '{label}' torrents.{CEND}\n\n"
            )
        else:
            print(
                f"\n\n[{CGREEN}deluge-labeler{CEND}]: {CBOLD}found {len(filtered_torrents)} eligible '{label}' torrents.{CEND}\n\n"
            )
            # loop through items in torrent list
            for hash, torrent in filtered_torrents:
                print(
                    f"[{CRED}label.set_torrent{CEND}]: {CBOLD}{torrent.get('name', [None])}{CEND}"
                    f"\n\t\t\t {CYELLOW}label_activity{CEND}: {torrent.get('label', [None])} -> {label}"
                    f"\n\t\t\t {CYELLOW}infohash{CEND}: {hash}"
                    f"\n\t\t\t {CYELLOW}tracker{CEND}: {urlparse(torrent.get('tracker', [None])).hostname}\n"
                )
                # label relevant torrents
                if not dryrun:
                    await deluge_handler.call("label.set_torrent", [hash, label])

    deluge_handler = DelugeHandler()

    try:
        # auth.login
        auth_response = await deluge_handler.call("auth.login", [deluge_password], 0)

        # checks the status of webui being connected, and connects to the daemon
        webui_connected = (await deluge_handler.call("web.connected", [], 0)).get(
            "result"
        )
        if not webui_connected:
            web_ui_daemons = await deluge_handler.call("web.get_hosts", [], 0)
            webui_connected = await deluge_handler.call(
                "web.connect", [web_ui_daemons.get("result")[0][0]], 0
            )
            if not webui_connected:
                print(
                    f"\n\n[{CRED}error{CEND}]: {CYELLOW}Your WebUI is not automatically connectable to the Deluge daemon.{CEND}\n"
                    f"{CYELLOW}\t Open the WebUI's connection manager to resolve this.{CEND}\n\n"
                )
                exit(1)
        print(
            f"[{CGREEN}json-rpc{CEND}/{CYELLOW}auth.login{CEND}]",
            auth_response,
        )
        if not auth_response.get("result"):
            exit(1)
        # get torrent list
        torrent_list = (
            (
                await deluge_handler.call(
                    "web.update_ui",
                    [["name", "tracker", "label"], {}],
                )
            )
            # why default to a list here?:
            # .get("result", [None])
            # .get("torrents", [None])
            .get("result", {}).get("torrents", {})
        )

        # make sure list exists
        if torrent_list:
            await filter_and_label(partial(limited_tracker, limited=True), "limiter")
            await filter_and_label(partial(limited_tracker, limited=3), "not-met")
            await filter_and_label(partial(limited_tracker, limited=False), "imported")

            if not dryrun:
                for item in remove_labels:
                    await deluge_handler.call("label.remove", [item])
        else:
            print(
                f"\n\n[{CRED}error{CEND}]: {CYELLOW}Your WebUI is likely not connected to the Deluge daemon. Open the WebUI to resolve this.{CEND}\n\n"
            )
            exit(1)
    except Exception as e:
        print(f"\n\n[{CRED}error{CEND}]: {CBOLD}{e}{CEND}\n\n")
    finally:
        deluge_handler.session.close()


async def run_main():
    await main()


if __name__ == "__main__":
    asyncio.run(run_main())
