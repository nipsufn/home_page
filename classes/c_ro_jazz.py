# c_ro_jazz.py
"""This module queries croapi.cz and provides retrieved data
"""
import logging
from classes.json_from_api import JSONFromAPI

class CRoJazz(JSONFromAPI):
    """This class queries croapi.cz and provides retrieved data
    """
    def __init__(self):
        """Class constructor
        """
        super(CRoJazz, self).__init__()
        self.logger = logging.getLogger('eink_status.CRoJazz')
        self.logger.debug('__init__')
        self.programme_title = "N/A"
        self.programme_start = "00:00"
        self.programme_stop = "00:00"
        self.track_artist = "N/A"
        self.track_title = "N/A"
        self.changed = False
        self.update()

    def update(self):
        """Update programme data
        """
        tmp_url = "https://croapi.cz/data/v2/schedule/now/1/jazz.json"
        tmp_json = self._get_json_from_url(tmp_url)
        if tmp_json is None:
            return
        if tmp_json['data'][0]['title'] != self.programme_title:
            self.programme_title = tmp_json['data'][0]['title']
            self.changed = True
        if tmp_json['data'][0]['since'][11:16] != self.programme_start:
            self.programme_start = tmp_json['data'][0]['since'][11:16]
            self.changed = True
        if tmp_json['data'][0]['till'][11:16] != self.programme_stop:
            self.programme_stop = tmp_json['data'][0]['till'][11:16]
            self.changed = True
        tmp_url = "https://croapi.cz/data/v2/playlist/now/jazz.json"
        tmp_json = self._get_json_from_url(tmp_url)
        if tmp_json is None:
            return

        tmp_string = (
            tmp_json['data']['interpret'] if 'interpret' in tmp_json['data']
            else "N\\A")
        if tmp_string != self.track_artist:
            self.track_artist = tmp_string
            self.changed = True
        tmp_string = (
            tmp_json['data']['track'] if 'track' in tmp_json['data']
            else "N\\A")
        if tmp_string != self.track_title:
            self.track_title = tmp_string
            self.changed = True
