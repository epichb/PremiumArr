# PremiumArr

Currently it supports basically all of the Sonarr, Radarr and Lidarr, ... but only in form of a blackhole folder.
In the future I will add support for the API of Sonarr, Radarr, Lidarr, ... so it can mark downloads as failed (-> next release).

The state is preserved in a SQLite DB - so even if the container is restarted / crashed / updated the state is preserved.



It's still under heavy development, so expect bugs and missing features.


## Docker Image

The Docker Image is available on Docker Hub: [premiumarr](https://hub.docker.com/r/horotw/premiumarr)

## Docker run

To run the docker image after building it, run the following command:
```bash
docker run -e API_KEY=your_API_key \
           -e RECHECK_PREMIUMIZE_CLOUD_DELAY=120\
           -v /path/to/blackhole:/blackhole \
           -v /path/to/downloads:/downloads \
           -v /path/to/done:/done \
           -v /path/to/config:/config \
           premiumarr:latest
```

## Example for Docker Compose

```yaml
services:
  premiumarr:
    image: horotw/premiumarr:latest
    container_name: premiumarr
    restart: unless-stopped
    environment:
      - API_KEY=your_API_key
      - RECHECK_PREMIUMIZE_CLOUD_DELAY=120
      - TZ=Europe/Berlin
    volumes:
      - /path/to/blackhole:/blackhole # The same as the blackhole folder you use in e.g. sonarr
      - /path/to/downloads:/downloads # Temporary download folder for the files while downloading
      - /path/to/done:/done # The folder where the files are moved to after downloading (e.g. the same as the one in sonarr)
      - /path/to/config:/config # The config folder for the app to persist the state
```

## Web View

A web view is available to show the current state of the database. It displays all entries with a working state and some of the entries with 'done' or 'failed' state, with pagination support for more entries.
It's available at PORT 5000.

## Environment Variables

| Name                           | Description                                                                                                     | Default Value | Required |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------- | ------------- | -------- |
| API_KEY                        | The API key for the Premiumize.me API                                                                           |               | Yes      |
| BLACKHOLE_PATH                 | The path to the blackhole folder                                                                                | /blackhole    | No       |
| CONFIG_PATH                    | The path to the config folder                                                                                   | /config       | No       |
| DOWNLOAD_PATH                  | The path to the downloads folder                                                                                | /downloads    | No       |
| DONE_PATH                      | The path to the done folder                                                                                     | /done         | No       |
| RECHECK_PREMIUMIZE_CLOUD_DELAY | The delay in seconds to recheck the Premiumize Cloud                                                            | 60            | No       |
| DL_SPEED_LIMIT_KB              | The download speed limit in KB/s                                                                                | -1            | No       |
| DL_THREADS                     | The number of download threads                                                                                  | 2             | No       |
| PREMIUMIZE_CLOUD_ROOT_DIR_NAME | The name of the root directory in the Premiumize Cloud                                                          | premiumarr    | No       |
| MAX_RETRY_COUNT                | The maximum number of retries for a download (That errored in the premiumize downloader)                        | 6             | No       |
| MAX_CLOUD_DL_MOVE_RETRY_COUNT  | The maximum number of retries for a download (That got stuck on 'Moving to cloud' in the premiumize downloader) | 3             | No       |
| MAX_STATE_RETRY_COUNT          | The maximum number of retries for a download (That errored in some way in the state machine)                    | 3             | No       |
| LOG_LEVEL                      | The log level for the application                                                                               | INFO          | No       |

## To build the docker image locally

Run the following command:
```bash
docker buildx build -t premiumarr .
# or the older command
docker build -t premiumarr .
```


## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.

## Improvements to come
- [ ] Add support for Sonarr, Radarr, Lidarr, ... API to mark downloads as failed
  - [ ] Maybe fake the NZBGet API to be easy integrated in Sonarr, Radarr, Lidarr, ...
- [ ] Maybe add a WebUI to see the status
- [ ] Remove Lists and use solely the DB (where it fits)
- [ ] Refactor the code to have functions for state transitions (-> back to found state if fail in ... state)
- [ ] Think about a state machine for the Downloads so the next step per download is clear (and fallbacks in state are easy to implement)
- [ ] Add a way to pause downloads
- [ ] Add a Scheduler to download files at a specific time
- [ ] Dedicated thread for Downloading

## Latest Changes
- [X] Add real logging (with levels) (currently only print statements)
- [X] Monitor how long a DL is 'Moving to cloud' and retry if it takes too long (more than 15min)
- [X] Find downloads that are 'somehow lost' e.g. the user removed them before they got downloaded it from the cloud downloader and again upload them do the web downloader

## Why a state machine?
What does every state have?
 - Expected current state (e.g. 'Uploading')
 - Actual current state (with checker functions)
 - Expected next state (e.g. 'Moving to cloud')
 - Expected fallback state (e.g. 'Uploading' if 'Moving to cloud' fails)
