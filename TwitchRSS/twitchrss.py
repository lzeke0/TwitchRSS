#
# Copyright 2017, 2016 Laszlo Zeke
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
from app_id import TWITCH_CLIENT_ID


VODCACHE_PREFIX = 'vodcache'
USERIDCACHE_PREFIX = 'userid'
VOD_URL_TEMPLATE = 'https://api.twitch.tv/kraken/channels/%s/videos?broadcast_type=archive,highlight,upload'
USERID_URL_TEMPLATE = 'https://api.twitch.tv/kraken/users?login=%s'
VODCACHE_LIFETIME = 120
USERIDCACHE_LIFETIME = 0  # No expire


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
        userid_json = self.fetch_userid(channel)
        (channel_display_name, channel_id) = self.extract_userid(json.loads(userid_json))
        channel_json = self.fetch_vods(channel_id)
        decoded_json = json.loads(channel_json)
        rss_data = self.construct_rss(channel, decoded_json, channel_display_name)
        self.response.headers['Content-Type'] = 'application/rss+xml'
        self.response.write(rss_data)

    def head(self,channel):
        self.get(channel)

    def fetch_userid(self, channel_name):
        return self.fetch_or_cache_object(channel_name, USERIDCACHE_PREFIX, USERID_URL_TEMPLATE, USERIDCACHE_LIFETIME)

    def fetch_vods(self, channel_id):
        return self.fetch_or_cache_object(channel_id, VODCACHE_PREFIX, VOD_URL_TEMPLATE, VODCACHE_LIFETIME)

    def fetch_or_cache_object(self, channel, key_prefix, url_template, cache_time):
        json_data = self.lookup_cache(channel, key_prefix)
        if json_data == '':
            json_data = self.fetch_json(channel, url_template)
            if json_data == '':
                self.abort(404)
            else:
                self.store_cache(channel, json_data, key_prefix, cache_time)
        return json_data

    @staticmethod
    def lookup_cache(channel_name, key_prefix):
        cached_data = memcache.get('%s:v5:%s' % (key_prefix, channel_name))
        if cached_data is not None:
            logging.debug('Cache hit for %s' % channel_name)
            return cached_data
        else:
            logging.debug('Cache miss for %s' % channel_name)
            return ''

    @staticmethod
    def store_cache(channel_name, data, key_prefix, cache_lifetime):
        try:
            logging.debug('Cached data for %s' % channel_name)
            memcache.set('%s:v5:%s' % (key_prefix, channel_name), data, cache_lifetime)
        except BaseException as e:
            logging.warning('Memcache exception: %s' % e)
            return

    @staticmethod
    def fetch_json(id, url_template):
        url = url_template % id
        headers = {
            'Accept': 'application/vnd.twitchtv.v5+json',
            'Client-ID': TWITCH_CLIENT_ID
        }
        request = urllib2.Request(url, headers=headers)
        retries = 0
        while retries < 3:
            try:
                result = urllib2.urlopen(request, timeout=3)
                logging.debug('Fetch from twitch for %s with code %s' % (id, result.getcode()))
                return result.read()
            except BaseException as e:
                logging.warning("Fetch exception caught: %s" % e)
                retries += 1
        return ''

    def extract_userid(self, user_info):
        userlist = user_info.get('users')
        if userlist is None or len(userlist) < 1:
            logging.info('No such user found.')
            self.abort(404)
        # Get the first id in the list
        userid = userlist[0].get('_id')
        username = userlist[0].get('display_name')
        if username and userid:
            return username, userid
        else:
            logging.warning('Userid is not found in %s' % user_info)
            self.abort(404)

    def construct_rss(self, channel_name, vods_info, display_name):
        feed = Feed()

        # Set the feed/channel level properties
        feed.feed["title"] = "%s's Twitch video RSS" % display_name
        feed.feed["link"] = "https://twitchrss.appspot.com/"
        feed.feed["author"] = "Twitch RSS Gen"
        feed.feed["description"] = "The RSS Feed of %s's videos on Twitch" % display_name
        feed.feed["ttl"] = '10'

        # Create an item
        try:
            if vods_info['videos'] is not None:
                for vod in vods_info['videos']:
                    item = {}
                    if vod["status"] == "recording":
                        link = "http://www.twitch.tv/%s" % channel_name
                        item["title"] = "%s - LIVE" % vod['title']
                        item["category"] = "live"
                    else:
                        link = vod['url']
                        item["title"] = vod['title']
                        item["category"] = vod['broadcast_type']
                    item["link"] = link
                    item["description"] = "<a href=\"%s\"><img src=\"%s\" /></a>" % (link, vod['preview']['large'])
                    if vod.get('description_html'):
                        item["description"] += "<br/>" + vod['description_html']
                    d = datetime.datetime.strptime(vod['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    item["pubDate"] = d.timetuple()
                    item["guid"] = vod['_id']
                    if vod["status"] == "recording":  # To show a different news item when recording is over
                        item["guid"] += "_live"
                    feed.items.append(item)
        except KeyError as e:
            logging.warning('Issue with json: %s\nException: %s' % (vods_info, e))
            self.abort(404)

        return feed.format_rss2_string()

app = webapp2.WSGIApplication([
    Route('/', MainPage),
    Route('/vod/<channel:[a-zA-Z0-9_]{4,25}>', RSSVoDServer)
], debug=False)