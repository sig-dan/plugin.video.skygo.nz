import hashlib
import time

from matthuisman import userdata
from matthuisman.session import Session
from matthuisman.log import log
from matthuisman.cache import cached

from .constants import HEADERS, AUTH_URL, RENEW_URL, CHANNELS_URL, TOKEN_URL, CHANNEL_EXPIRY, DEVICE_IP, CHANNELS_CACHE_KEY
from .language import _

class Error(Exception):
    pass

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

    @cached(expires=CHANNEL_EXPIRY, key=CHANNELS_CACHE_KEY)
    def channels(self):
        channels = {}

        data = self._session.get(CHANNELS_URL).json()
        for row in data['entries']:
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

    def play_url(self, url):
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

        token = data['token']
        url = '{}&auth={}'.format(url, token)
        resp = self._session.get(url, allow_redirects=False)
        return resp.headers.get('location')

    def logout(self):
        log('API: Logout')
        userdata.delete('device_id')
        userdata.delete('access_token')
        self.new_session()