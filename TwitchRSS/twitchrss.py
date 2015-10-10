#
# Copyright 2015 Laszlo Zeke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import webapp2
from webapp2 import Route
import urllib2
import json
import datetime
import logging
from feedformatter import Feed
from google.appengine.api import memcache


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        html_resp = """
        <html>
            <head>
            <title>Twitch stream RSS generator</title>
            </head>
            <body>
                <p style="font-family: helvetica; font-size:20pt; padding: 20px;">
                    Twitch stream RSS generator
                </p>
                <p style="font-family: helvetica; font-size:12pt; padding: 20px;">
                    You can get RSS of broadcasts by subscribing to https://twitchrss.appspot.com/vod/&lt;channel name&gt;<br/>
                    For example: <a href="https://twitchrss.appspot.com/vod/riotgames">https://twitchrss.appspot.com/vod/riotgames</a><br/><br/>
                    Not endorsed by Twitch.tv, just a fun project.<br/>
                    <a href="https://github.com/lzeke0/TwitchRSS">Project home</a>
                </p>
            </body>
        </html>
        """
        self.response.write(html_resp)


class RSSVoDServer(webapp2.RequestHandler):
    def get(self, channel):
        channel_json = self.lookup_cache(channel)
        if channel_json == '':
            channel_json = self.fetch_json(channel)
            if channel_json == '':
                self.abort(404)
            else:
                self.store_cache(channel, channel_json)

        decoded_json = json.loads(channel_json)
        rss_data = self.construct_rss(channel, decoded_json)
        self.response.headers['Content-Type'] = 'application/xhtml+xml'
        self.response.write(rss_data)

    @staticmethod
    def lookup_cache(channel_name):
        cached_data = memcache.get('vodcache:%s' % channel_name)
        if cached_data is not None:
            logging.debug('Cache hit for %s' % channel_name)
            return cached_data
        else:
            logging.debug('Cache miss for %s' % channel_name)
            return ''

    @staticmethod
    def store_cache(channel_name, data):
        try:
            logging.debug('Cached data for %s' % channel_name)
            memcache.set('vodcache:%s' % channel_name, data, 120)
        except:
            return

    @staticmethod
    def fetch_json(channel):
        url = 'https://api.twitch.tv/kraken/channels/%s/videos?broadcasts=true' % channel
        request = urllib2.Request(url,headers={'Accept':'application/vnd.twitchtv.v3+json'})
        try:
            result = urllib2.urlopen(request)
            logging.debug('Fetch from twitch for %s with code %s' % (channel, result.getcode()))
            return result.read()
        except urllib2.URLError, e:
            return ''

    def construct_rss(self, channel_name, vods_info):
        feed = Feed()

        # Set the feed/channel level properties
        feed.feed["title"] = "%s's Twitch video RSS" % channel_name
        feed.feed["link"] = "https://twitchrss.appspot.com/"
        feed.feed["author"] = "Twitch RSS Gen"
        feed.feed["description"] = "The RSS Feed of %s's videos on Twitch" % channel_name

        # Create an item
        try:
            if vods_info['videos'] is not None:
                for vod in vods_info['videos']:
                    item = {}
                    link = ""
                    if vod["status"] == "recording":
                        link = "http://www.twitch.tv/%s" % channel_name
                        item["title"] = "%s - LIVE" % vod['title']
                    else:
                        link = vod['url']
                        item["title"] = vod['title']
                    item["link"] = link
                    item["description"] = "<a href=\"%s\"><img src=\"%s\" /></a>" % (link, vod['preview'])
                    d = datetime.datetime.strptime(vod['recorded_at'], '%Y-%m-%dT%H:%M:%SZ')
                    item["pubDate"] = d.timetuple()
                    item["guid"] = vod['_id']
                    if vod["status"] == "recording": # To show a different news item when live is over
                        item["guid"] += "_live"
                    item["ttl"] = '10'
                    feed.items.append(item)
        except KeyError:
            self.abort(404)

        return feed.format_rss2_string()

app = webapp2.WSGIApplication([
    Route('/', MainPage),
    Route('/vod/<channel:[a-zA-Z0-9_]{4,25}>', RSSVoDServer)
], debug=False)