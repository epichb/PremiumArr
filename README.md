# PremiumArr

Currently it supports basically all of the Sonarr, Radarr and Lidarr, ... but only in form of a blackhole folder.
In the future I will add support for the API of Sonarr, Radarr, Lidarr, ... so it can mark downloads as failed (-> next release).

Also not yet included is any from of persistence of the state, so if the container is restarted, it will forget all downloads that are currently in progress.

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


## Environment Variables

| Name                           | Description                                            | Default Value | Required |
| ------------------------------ | ------------------------------------------------------ | ------------- | -------- |
| API_KEY                        | The API key for the Premiumize.me API                  |               | Yes      |
| BLACKHOLE_PATH                 | The path to the blackhole folder                       | /blackhole    | No       |
| CONFIG_PATH                    | The path to the config folder                          | /config       | No       |
| DOWNLOAD_PATH                  | The path to the downloads folder                       | /downloads    | No       |
| DONE_PATH                      | The path to the done folder                            | /done         | No       |
| RECHECK_PREMIUMIZE_CLOUD_DELAY | The delay in seconds to recheck the Premiumize Cloud   | 60            | No       |
| DL_SPEED_LIMIT_KB              | The download speed limit in KB/s                       | -1            | No       |
| DL_THREADS                     | The number of download threads                         | 2             | No       |
| PREMIUMIZE_CLOUD_ROOT_DIR_NAME | The name of the root directory in the Premiumize Cloud | premiumarr    | No       |



## To build the docker image locally

Run the following command:
```bash
docker buildx build -t premiumarr .
# or the older command
docker build -t premiumarr .
```


## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.