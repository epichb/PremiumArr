def handle_sabnzbd_command(mode):
    if mode == "version":
        return sabnzbd_version()
    if mode == "get_config":
        return sabnzbd_config()


def sabnzbd_version():
    return {"version": "4.4.1"}


def sabnzbd_config():
    return {
        "config": {
            "misc": {
                "complete_dir": "/complete/dir",
                "tv_categories": ["tv", "Series"],
                "enable_tv_sorting": True,
                "movie_categories": ["Movies", "Films"],
                "enable_movie_sorting": True,
                "date_categories": ["Date1", "Date2"],
                "enable_date_sorting": False,
                "pre_check": True,
                "history_retention": "7 days",
                "history_retention_option": "days",
                "history_retention_number": 7,
            },
            "categories": [],
            "servers": [],
            "sorters": [],
        }
    }
