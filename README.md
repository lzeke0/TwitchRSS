## Twitch RSS Webapp for Google App Engine
This project is a very small web application for serving RSS feed for broadcasts
in Twitch. It fetches data from [Twitch API](https://dev.twitch.tv/docs) and caches in Memcache.
The engine is webapp2.

A running version can be tried out at:
https://twitchrss.appspot.com/vod/twitch

There is also a VOD only endpoint if you don't want to see ongoing streams which are known to break some readers:
https://twitchrss.appspot.com/vodonly/twitch

### Caching requests
This service caches requests from twitch for 10 minutes meaning that you will only get new answers once in
10 minutes. Please keep this in mind when polling the service.

### Deployment
First you should set your own Twitch API client ID in the app.yaml.
See how to deploy on [Google App Engine](https://cloud.google.com/appengine/docs/standard/python3).

### Other things
The project uses a slightly modified [Feedformatter](https://code.google.com/p/feedformatter/) to support
more tags and time zone in pubDate tag.

### About
The project has been developed by László Zeke.
