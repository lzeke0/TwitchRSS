#
# Copyright 2020 Laszlo Zeke
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

from cachetools import cached, TTLCache, LRUCache
from feedformatter import Feed
from flask import abort, Flask, request
from io import BytesIO
from os import environ
import datetime
import gzip
import time
import json
import logging
import re
import urllib


VOD_URL_TEMPLATE = 'https://api.twitch.tv/helix/videos?user_id=%s&type=all'
USERID_URL_TEMPLATE = 'https://api.twitch.tv/helix/users?login=%s'
AUTH_URL = 'https://id.twitch.tv/oauth2/token'
VODCACHE_LIFETIME = 10 * 60
USERIDCACHE_LIFETIME = 24 * 60 * 60
CHANNEL_FILTER = re.compile("^[a-zA-Z0-9_]{2,25}$")
TWITCH_CLIENT_ID = environ.get("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = environ.get("TWITCH_CLIENT_SECRET")
logging.basicConfig(level=logging.DEBUG if environ.get('DEBUG') else logging.INFO)

if not TWITCH_CLIENT_ID:
    raise Exception("Twitch API client id env variable not set.")
if not TWITCH_CLIENT_SECRET:
    raise Exception("Twitch API secret env variable not set.")

oauth = {'token': '', 'epoch': 0}
app = Flask(__name__, static_folder='')

def authorize():
    # return if token has not expired
    if (oauth['epoch'] >= round(time.time())):
        return oauth['token']

    logging.debug("requesting a new oauth token")
    data = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'client_credentials',
    }
    request = urllib.request.Request(AUTH_URL, data=urllib.parse.urlencode(data).encode("utf-8"), method='POST')
    retries = 0
    while retries < 3:
        try:
            result = urllib.request.urlopen(request, timeout=3)
            r = json.loads(result.read().decode("utf-8"))
            oauth['token'] = r['access_token']
            oauth['epoch'] = int(r['expires_in']) + round(time.time()) - 1
            logging.debug("oauth token aquired")
            return oauth['token']
        except Exception as e:
            logging.warning("Fetch exception caught: %s" % e)
            retries += 1
    abort(503)
    
@app.route('/', methods=['GET'])
def index():
    return app.send_static_file('index.html')


@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return app.send_static_file('favicon.ico')


@app.route('/vod/<string:channel>', methods=['GET', 'HEAD'])
def vod(channel):
    if CHANNEL_FILTER.match(channel):
        return get_inner(channel)
    else:
        abort(404)


@app.route('/vodonly/<string:channel>', methods=['GET', 'HEAD'])
def vodonly(channel):
    if CHANNEL_FILTER.match(channel):
        return get_inner(channel, add_live=False)
    else:
        abort(404)


def get_inner(channel, add_live=True):
    userid_json = fetch_user(channel)
    if not userid_json:
        abort(404)

    (channel_display_name, channel_id) = extract_userid(userid_json)
    logging.debug("Start fetching vods")
    channel_json = fetch_vods(channel_id)
    if not channel_json:
        abort(404)
    logging.debug("Finish fetching vods")
    decoded_json = json.loads(channel_json)['data']
    rss_data = construct_rss(channel, decoded_json, channel_display_name, add_live)
    headers = {'Content-Type': 'application/rss+xml'}

    if 'gzip' in request.headers.get("Accept-Encoding", ''):
        headers['Content-Encoding'] = 'gzip'
        rss_data = gzip.compress(rss_data)

    return rss_data, headers


@cached(cache=TTLCache(maxsize=3000, ttl=USERIDCACHE_LIFETIME))
def fetch_user(channel_name):
    return fetch_json(channel_name, USERID_URL_TEMPLATE)


@cached(cache=TTLCache(maxsize=500, ttl=VODCACHE_LIFETIME))
def fetch_vods(channel_id):
    return fetch_json(channel_id, VOD_URL_TEMPLATE)


def fetch_json(id, url_template):
    #update the oauth token
    token = authorize()

    url = url_template % id
    headers = {
        'Authorization': 'Bearer ' + token,
        'Client-Id': TWITCH_CLIENT_ID,
        'Accept-Encoding': 'gzip'
    }
    request = urllib.request.Request(url, headers=headers)
    retries = 0
    while retries < 3:
        try:
            result = urllib.request.urlopen(request, timeout=3)
            logging.debug('Fetch from twitch for %s with code %s' % (id, result.getcode()))
            if result.info().get('Content-Encoding') == 'gzip':
                logging.debug('Fetched gzip content')
                return gzip.decompress(result.read())
            return result.read()
        except Exception as e:
            logging.warning("Fetch exception caught: %s" % e)
            retries += 1
    abort(503)


def extract_userid(user_info):
    extracted_data = json.loads(user_info)['data']
    # Get the first id in the list
    if extracted_data:
        return extracted_data[0]['display_name'], extracted_data[0]['id']
    else:
        logging.debug('Userid is not found in %s' % user_info)
        abort(404)


def construct_rss(channel_name, vods_info, display_name, add_live=True):
    feed = Feed()

    # Set the feed/channel level properties
    feed.feed["title"] = "%s's Twitch video RSS" % display_name
    feed.feed["link"] = "https://twitchrss.appspot.com/"
    feed.feed["author"] = "Twitch RSS Generated"
    feed.feed["description"] = "The RSS Feed of %s's videos on Twitch" % display_name
    feed.feed["ttl"] = '10'

    # Create an item
    try:
        if vods_info:
            for vod in vods_info:
                item = {}

                # It seems if the thumbnail is empty then we are live?
                # Tempted to go in and fix it for them since the source is leaked..
                if vod["thumbnail_url"] == "https://vod-secure.twitch.tv/_404/404_processing_%{width}x%{height}.png":
                    if not add_live:
                        continue
                    link = "https://www.twitch.tv/%s" % channel_name
                    item["title"] = "%s - LIVE" % vod['title']
                    item["category"] = "live"
                    item["description"] = "<a href=\"%s\">LIVE LINK</a>" % link
                else:
                    link = vod['url']
                    item["title"] = vod['title']
                    item["category"] = vod['type']
                    item["description"] = "<a href=\"%s\"><img src=\"%s\" /></a>" % (link, vod['thumbnail_url'].replace("%{width}", "512").replace("%{height}","288"))
                item["link"] = link

                #@madiele: for some reason the new API does not have the game field anymore...
                #if vod.get('game'):
                #    item["description"] += "<br/>" + vod['game']

                if vod.get('description'):
                    item["description"] += "<br/>" + vod['description']
                d = datetime.datetime.strptime(vod['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                item["pubDate"] = d.timetuple()
                item["guid"] = vod['id']
                if item["category"] == "live":  # To show a different news item when recording is over
                    item["guid"] += "_live"
                feed.items.append(item)
    except KeyError as e:
        logging.warning('Issue with json: %s\nException: %s' % (vods_info, e))
        abort(404)

    return feed.format_rss2_string()


# For debug
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=8080, debug=True)
