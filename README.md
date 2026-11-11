# iHeartRadio Favorites for myMPD

Play live stations saved in your iHeartRadio account from the myMPD
Scripts menu. The picker also searches the public catalog for stations
by name or call sign. MPD plays the selected stream directly. Manage
your saved stations on iHeartRadio.

## Set up your account

Run the account check in a terminal with Python 3.10 or later.

```sh
python3 test-account.py --check
```

The first run saves your email and password in plaintext at
`~/.config/mympd-iheart/test-account.json` with mode `0600`. Use
`--config` to choose another location. For accounts that sign in through
a third party, this client requires an iHeartRadio email and password.

## Start the bridge

If myMPD runs on the host, run `python3 bridge.py` alongside it. For
Docker Compose, use the same UID and GID that own the config file.

```sh
export IHEART_CONFIG="$HOME/.config/mympd-iheart/test-account.json"
export IHEART_UID="$(id -u)" IHEART_GID="$(id -g)"
docker compose -f compose.yaml -f compose.host.yaml up --build -d
```

If myMPD uses a private Docker network, set `MPD_NETWORK` to that
existing network and run `docker compose up --build -d`. Use
`--service http://iheart:18767` when installing the picker. Keep the
bridge on loopback or a private network because it serves your saved
station list to clients that can reach it.

For a host-networked Dockhand stack, copy
`dockhand/docker-compose.yml`, `Dockerfile`, `.dockerignore`,
`account.py`, and `bridge.py` into the stack directory. Put your private
config at `data/test-account.json` and set `IHEART_UID` and
`IHEART_GID` if they differ from 1000.

## Install and use the picker

Enable Lua scripting in myMPD, then run:

```sh
python3 install-picker.py --mympd http://127.0.0.1:8081
```

For a PIN-protected myMPD instance, provide a valid session token through
`MYMPD_SESSION`. Use `--partition` to select another partition or
`--replace` to update the existing picker.

Open **iHeartRadio Favorites** from the Scripts menu. Select a saved
station and submit with the search field blank to play it. Enter a
station name or call sign in the search field below the saved stations
and submit to open the search results.

## Add the myMPD Home launcher

Copy [`iheart-radio-cc0.png`](assets/iheart-radio-cc0.png) into myMPD's
`pics/thumbs/` directory. After installing the picker, submit the bundled
[Home launcher JSON](dockhand/home-launcher.json) to the same myMPD
partition. For the default partition:

```sh
python3 -c 'import json, sys; print(json.dumps(json.load(sys.stdin)), end="")' \
  < dockhand/home-launcher.json |
  curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  http://127.0.0.1:8081/api/default
```

For a PIN-protected instance, add
`-H "X-myMPD-Session: $MYMPD_SESSION"`. Check that the response has a
JSON-RPC `result` and refresh the Home page. The **iHeartRadio Favorites**
tile opens the same picker as the Scripts menu.

The launcher uses an original heart-and-radio-wave icon released under
[CC0 1.0](assets/CC0-1.0.txt).

## Show station artwork and track titles

Create `pics/iheart-stations/` in myMPD's work directory and make it
writable by the bridge user. The Dockhand Compose file mounts that folder
automatically. For a native bridge, pass `--artwork-dir` with its path.

Copy `iheart-display.js` into myMPD's `pics/` directory and append
`iheart-loader.js` to `config/custom_js` once. Restart myMPD and refresh
the browser. Select the station again from the picker to attach its name
and artwork to the new queue entry.

The Home picker also searches podcasts by title or keyword. Select a
show to browse its 20 most recent episodes, then select an episode to
play it through MPD. The station picker button in the player appears
while an iHeartRadio live station is selected. It lists favorites and
searches live stations without showing podcast search. In station search
results, choose **Add to iHeartRadio favorites** to save the selected
station. Saving requires myMPD and the bridge to communicate over loopback.
## Contributing

- **Bug reports** can go in [Issues](https://github.com/bonelifer/mympd-iheart/issues).
- **Questions and feature ideas** belong in [Discussions](https://github.com/bonelifer/mympd-iheart/discussions).
- Pull requests are welcome for bug fixes and discussed features.


## Acknowledgments

- Code and documentation assisted by [Codex](https://openai.com/codex/).

## License

GNU General Public License v3.0. See [LICENSE](LICENSE). The launcher
image is available under [CC0 1.0](assets/CC0-1.0.txt).
