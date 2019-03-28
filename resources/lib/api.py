import hashlib
import time
import re
from collections import OrderedDict

from matthuisman import userdata, inputstream, plugin
from matthuisman.session import Session
from matthuisman.log import log
from matthuisman.exceptions import Error

from .constants import HEADERS, AUTH_URL, RENEW_URL, CHANNELS_URL, TOKEN_URL, DEVICE_IP, CONTENT_URL, PLAY_URL, WIDEVINE_URL, PASSWORD_KEY
from .language import _

class APIError(Error):
    pass

def sorted_nicely(l, key):
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda x: [convert(c) for c in re.split('([0-9]+)', x[key].replace(' ', '').strip().lower())]
    return sorted(l, key = alphanum_key)

class API(object):
    def new_session(self):
        self.logged_in = False
        self._session = Session(HEADERS)
        self._set_authentication()

    def _set_authentication(self):
        token = userdata.get('access_token')
        if not token:
            return

        self._session.headers.update({'sky-x-access-token': token})
        self.logged_in = True

    def content(self):
        content = OrderedDict()

        rows = self._session.get(CONTENT_URL).json()['data']
        for row in sorted_nicely(rows, 'title'):
            content[row['id']] = row

        return content

    def channels(self):
        channels = OrderedDict()

        data = self._session.get(CHANNELS_URL).json()

        for row in sorted_nicely(data['entries'], 'title'):
            image = row['media$thumbnails'][0]['plfile$url'] if row['media$thumbnails'] else None
            data = {'title': row['title'], 'description': row['description'], 'url': '', 'image': image}
            for item in row['media$content']:
                if 'SkyGoStream' in item['plfile$assetTypes']:
                    data['url'] = item['plfile$url']
                    break

            channels[row['title']] = data

        return channels
        
    def login(self, username, password):
        device_id = hashlib.md5(username).hexdigest()

        data = {
            "deviceDetails": "test",
            "deviceID": device_id,
            "deviceIP": DEVICE_IP,
            "password": password,
            "username": username
        }

        resp = self._session.post(AUTH_URL, json=data)
        data = resp.json()
        if resp.status_code != 200 or 'sessiontoken' not in data:
            raise APIError(_(_.LOGIN_ERROR, message=data.get('message')))

        userdata.set('access_token', data['sessiontoken'])
        userdata.set('device_id', device_id)

        self._set_authentication()

    def _renew_token(self):
        password = userdata.get(PASSWORD_KEY)

        if password:
            self.login(userdata.get('username'), password)
            return

        data = {
            "deviceID": userdata.get('device_id'),
            "deviceIP": DEVICE_IP,
            "sessionToken": userdata.get('access_token'),
        }

        resp = self._session.post(RENEW_URL, json=data)
        data = resp.json()

        if resp.status_code != 200 or 'sessiontoken' not in data:
            raise APIError(_(_.RENEW_TOKEN_ERROR, message=data.get('message')))

        userdata.set('access_token', data['sessiontoken'])

        self._set_authentication()

    def _get_play_token(self):
        self._renew_token()

        params = {
            'profileId':   userdata.get('device_id'),
            'deviceId':    userdata.get('device_id'),
            'partnerId':   'skygo',
            'description': 'ANDROID',
        }

        resp = self._session.get(TOKEN_URL, params=params)
        data = resp.json()

        if resp.status_code != 200 or 'token' not in data:
            raise APIError(_(_.TOKEN_ERROR, message=data.get('message')))

        return data['token']

    def play_media(self, media_id):
        token = self._get_play_token()

        params = {
            'form': 'json',
            'types': None,
            'fields': 'id,content',
            'byId': media_id,
        }

        data = self._session.get(PLAY_URL, params=params).json()

        videos = data['entries'][0]['media$content']

        chosen = videos[0]
        for video in videos:
            if video['plfile$format'] == 'MPEG-DASH':
                chosen = video
                break
 
        url = '{}&auth={}&formats=mpeg-dash&tracking=true'.format(chosen['plfile$url'], token)
        resp = self._session.get(url, allow_redirects=False)

        if resp.status_code != 302:
            data = resp.json()
            raise APIError(_(_.PLAY_ERROR, message=data.get('description')))

        url = resp.headers.get('location')
        pid = chosen['plfile$url'].split('?')[0].split('/')[-1]

        return plugin.Item(
            path = url,
            art  = False,
            inputstream = inputstream.Widevine(
                license_key  = WIDEVINE_URL.format(token=token, pid=pid, challenge='B{SSM}'),
                challenge    = '',
                content_type = '',
                response     = 'JBlicense',
            ),
        )

    def play_channel(self, channel):
        channels = self.channels()
        channel = channels.get(channel)
        if not channel:
            raise APIError(_.NO_CHANNEL)

        token = self._get_play_token()
        url = '{}&auth={}'.format(channel['url'], token)
        resp = self._session.get(url, allow_redirects=False)

        if resp.status_code != 302:
            data = resp.json()
            raise APIError(_(_.PLAY_ERROR, message=data.get('description')))

        url = resp.headers.get('location')

        if 'faxs' in url:
            raise APIError(_.ADOBE_ERROR)

        return plugin.Item(
            path = url,
            label = channel['title'],
            art   = {'thumb': channel['image']},
            info  = {'description': channel['description']},
            #inputstream = inputstream.HLS(), # not until cookie support
        )

    def logout(self):
        userdata.delete('device_id')
        userdata.delete('access_token')
        userdata.delete(PASSWORD_KEY)
        self.new_session()