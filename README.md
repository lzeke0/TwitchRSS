## Twitch RSS Webapp for Google App Engine
This project is a very small web application for serving RSS feed for broadcasts
in Twitch. It fetches data from [Twitch API](https://github.com/justintv/twitch-api) and caches in Memcache.
The engine is webapp2.

A running version can be tried out at: 
https://twitchrss.appspot.com/vod/twitch

### Deployment
See how to deploy on [Google App Engine](https://cloud.google.com/appengine/docs/python/gettingstartedpython27/introduction).

### Other things
The project uses a slightly modified [Feedformatter](https://code.google.com/p/feedformatter/) to support
more tags and time zone in pubDate tag.

### About
The project has been developed by László Zeke.
