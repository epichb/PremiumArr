# PremiumArr

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
    image: HoroTW/premiumarr:latest
    container_name: premiumarr
    restart: unless-stopped
    environment:
      - API_KEY=your_API_key
      - RECHECK_PREMIUMIZE_CLOUD_DELAY=120
    volumes:
      - /path/to/blackhole:/blackhole # The same as the blackhole folder you use in e.g. sonarr
      - /path/to/downloads:/downloads # Temporary download folder for the files while downloading
      - /path/to/done:/done # The folder where the files are moved to after downloading (e.g. the same as the one in sonarr)
      - /path/to/config:/config # The config folder for the app to persist the state
```


## Environment Variables

| Name                           | Description                                          | Default Value | Required |
| ------------------------------ | ---------------------------------------------------- | ------------- | -------- |
| API_KEY                        | The API key for the Premiumize.me API                |               | Yes      |
| BLACKHOLE_PATH                 | The path to the blackhole folder                     | /blackhole    | No       |
| DOWNLOAD_PATH                  | The path to the downloads folder                     | /downloads    | No       |
| DONE_PATH                      | The path to the done folder                          | /done         | No       |
| RECHECK_PREMIUMIZE_CLOUD_DELAY | The delay in seconds to recheck the Premiumize Cloud | 60            | No       |
| DL_SPEED_LIMIT_KB              | The download speed limit in KB/s                     | -1            | No       |
| DL_THREADS                     | The number of download threads                       | 2             | No       |



## To build the docker image locally

Run the following command:
```bash
docker buildx build -t premiumarr .
# or the older command
docker build -t premiumarr .
```


## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.