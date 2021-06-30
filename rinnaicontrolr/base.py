"""
base.py -- client for the base Rinnai API
"""

import datetime, json, logging, time

import requests
from rinnaicontrolr.aws_srp import AWSSRP

LOGGER = logging.getLogger('rinnaicontrolr')

from rinnaicontrolr.const import (
    POOL_ID,
    CLIENT_ID,
    POOL_REGION,
    GET_DEVICES_PAYLOAD
)

class RinnaiWaterHeater(object):
    # Represents a Rinnai Water Heater, with methods for status and issuing commands

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = {}

    def validate_token(self):
        """Fetch or refresh the access token as needed"""

        now = time.time()
        if now >= self.token.get('expires_at', 0):
            if self.token.get('RefreshToken'):
                self._refresh_token()
            else:
                self._get_initial_token()
        assert now < self.token.get('expires_at', 0), self.token

    def _get_initial_token(self):
        """Authenticate and store the initial access token"""

        aws = AWSSRP(username=self.username, password=self.password, pool_id=POOL_ID,
                     client_id=CLIENT_ID, pool_region=POOL_REGION)
        self._store_token(aws.authenticate_user())

    def _store_token(self, js):
        self.token = js['AuthenticationResult']
        assert 'AccessToken' in self.token, self.token
        assert 'IdToken' in self.token, self.token
        assert 'RefreshToken' in self.token, self.token
        self.token['expires_at'] = time.time() + self.token['ExpiresIn']
        LOGGER.debug(f'received token, expires {self.token["expires_at"]}')

    def _refresh_token(self):
        # Since we've stored the password there's no reason to actually use the
        # refresh token. If we wanted to do so, we could look at renew_access_token()
        # in https://github.com/capless/warrant/blob/master/warrant/__init__.py
        # We don't do that now to avoid unnecessary code paths (and their bugs).
        self._get_initial_token()

    def getDevices(self):
        self.validate_token()

        payload = GET_DEVICES_PAYLOAD % (self.username)
        headers = {
          'x-amz-user-agent': 'aws-amplify/3.4.3 react-native',
          'x-api-key': 'da2-dm2g4rqvjbaoxcpo4eccs3k5he',
          'Content-Type': 'application/json'
        }

        r = requests.post(
            'https://s34ox7kri5dsvdr43bfgp6qh6i.appsync-api.us-east-1.amazonaws.com/graphql',
            data=payload,
            headers=headers,
        )
        r.raise_for_status()

        result = r.json()
        for items in result["data"]['getUserByEmail']['items']:
            for k,v in items['devices'].items():
                return v

    @property
    def is_connected(self):
        """Connection status of client with Rinnai Cloud service"""
        return time.time() < self.token.get('expires_at', 0)

    def start_recirculation(self, thing_name: str, user_uuid: str, duration: int, additional_params={}):
        """start recirculation on the specified device"""
        url = "https://d1coipyopavzuf.cloudfront.net/api/device_shadow/input"

        headers = {
          'User-Agent': 'okhttp/3.12.1',
          'Content-Type': 'application/x-www-form-urlencoded'
        }
        payload = "user=%s&thing=%s&attribute=set_priority_status&value=true" % (user_uuid, thing_name)

        r = requests.post(
            url,
            data=payload,
            headers=headers
        )
        r.raise_for_status()

        payload = "user=%s&thing=%s&attribute=recirculation_duration&value=%s" % (user_uuid, thing_name, duration)
        r = requests.post(
            url,
            data=payload,
            headers=headers
        )
        r.raise_for_status()

        payload = "user=%s&thing=%s&attribute=set_recirculation_enabled&value=true" % (user_uuid, thing_name)
        r = requests.post(
            url,
            data=payload,
            headers=headers
        )
        r.raise_for_status()

        return r