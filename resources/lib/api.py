import hashlib
import time
import re
from collections import OrderedDict

from matthuisman import userdata, inputstream, plugin
from matthuisman.session import Session
from matthuisman.log import log
from matthuisman.cache import cached

from .constants import HEADERS, AUTH_URL, RENEW_URL, CHANNELS_URL, TOKEN_URL, CHANNEL_EXPIRY, DEVICE_IP, CHANNELS_CACHE_KEY, CONTENT_EXPIRY, CONTENT_CACHE_KEY, CONTENT_URL, PLAY_URL, WIDEVINE_URL
from .language import _

def sorted_nicely(l, key):
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda x: [convert(c) for c in re.split('([0-9]+)', x[key].replace(' ', '').strip().lower())]
    return sorted(l, key = alphanum_key)

class API(object):
    def new_session(self):
        self._logged_in = False
        self._session = Session(HEADERS)
        self._set_access_token(userdata.get('access_token'))

    def _set_access_token(self, token):
        if token:
            self._session.headers.update({'sky-x-access-token': token})
            self._logged_in = True

    @property
    def logged_in(self):
        return self._logged_in

    @cached(expires=CONTENT_EXPIRY, key=CONTENT_CACHE_KEY)
    def content(self):
        content = OrderedDict()

        rows = self._session.get(CONTENT_URL).json()['data']
        for row in sorted_nicely(rows, 'title'):
            content[row['id']] = row

        return content

    @cached(expires=CHANNEL_EXPIRY, key=CHANNELS_CACHE_KEY)
    def channels(self):
        channels = OrderedDict()

        data = self._session.get(CHANNELS_URL).json()
        for row in sorted_nicely(data['entries'], 'title'):
            data = {'title': row['title'], 'description': row['description'], 'url': '', 'image': row['media$thumbnails'][0]['plfile$url']}
            for item in row['media$content']:
                if 'SkyGoStream' in item['plfile$assetTypes']:
                    data['url'] = item['plfile$url']
                    break

            channels[row['title']] = data

        return channels
        
    def login(self, username, password):
        log('API: Login')

        device_id = hashlib.md5(username).hexdigest()

        data = {
            "deviceDetails": "test",
            "deviceID": device_id,
            "deviceIP": DEVICE_IP,
            "password": password,
            "username": username
        }

        data = self._session.post(AUTH_URL, json=data).json()
        access_token = data.get('sessiontoken')      
        if not access_token:
            self.logout()
            raise Error(data.get('message', ''))

        self._save_auth(device_id, access_token)

    def _renew_token(self):
        log('API: Renew Token')

        data = {
            "deviceID": userdata.get('device_id'),
            "deviceIP": DEVICE_IP,
            "sessionToken": userdata.get('access_token'),
        }

        data = self._session.post(RENEW_URL, json=data).json()
        access_token = data.get('sessiontoken')
        if not access_token:
            raise Error(data.get('message', ''))

        self._save_auth(userdata.get('device_id'), access_token)

    def _save_auth(self, device_id, access_token):
        userdata.set('device_id', device_id)
        userdata.set('access_token', access_token)
        self.new_session()

    def _get_play_token(self):
        params = {
            'profileId':   userdata.get('device_id'),
            'deviceId':    userdata.get('device_id'),
            'partnerId':   'skygo',
            'description': 'ANDROID',
        }

        resp = self._session.get(TOKEN_URL, params=params)
        if resp.status_code == 403:
            self._renew_token()
            resp = self._session.get(TOKEN_URL, params=params)

        data = resp.json()
        if 'token' not in data:
            raise Error(_.TOKEN_ERROR)

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

        url = data['entries'][0]['media$content'][0]['plfile$url']
        url = '{}&auth={}&formats=mpeg-dash&format=SMIL&tracking=true'.format(url, token)

        page = self._session.get(url).text
        if 'LicenseNotGranted' in page:
            raise Exception(_.NO_ACCESS)

        url = re.search('video src="(.*?)"', page).group(1)
        pid = re.search('pid=(.*?)\|', page).group(1)

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

    def play_url(self, url):
        token = self._get_play_token()
        url = '{}&auth={}'.format(url, token)
        resp = self._session.get(url, allow_redirects=False)
        return resp.headers.get('location')

    def logout(self):
        log('API: Logout')
        userdata.delete('device_id')
        userdata.delete('access_token')
        self.new_session()