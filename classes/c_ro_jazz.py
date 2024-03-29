# c_ro_jazz.py
"""This module queries croapi.cz and provides retrieved data
"""
import logging
import multiprocessing
from classes.json_from_api import JSONFromAPI

class CRoJazz(JSONFromAPI):
    """This class queries croapi.cz and provides retrieved data
    """
    def __init__(self):
        """Class constructor
        """
        super().__init__()
        self.logger = logging.getLogger(type(self).__name__)
        self.track_artist = "N/A"
        self.track_title = "N/A"
        self._updated = False
        self.__update()
        self.logger.debug('Class initialized')

    def update(self, croj: multiprocessing.connection.Connection):
        """update"""
        self.__update()
        croj.send({
            'track_artist': self.track_artist,
            'track_title': self.track_title,
            'updated': self._updated
        })
        self.logger.info("sent data via pipe")
        return True

    def __update(self) -> bool:
        """Update programme data"""
        self._updated = False
        tmp_url = "https://croapi.cz/data/v2/playlist/now/jazz.json"
        tmp_json = self._get_json_from_url(tmp_url)
        if tmp_json is None:
            return False

        tmp_string = (
            tmp_json['data']['interpret'] if 'interpret' in tmp_json['data']
            else "N\\A")
        if tmp_string != self.track_artist:
            self.track_artist = tmp_string
            self._updated = True
        tmp_string = (
            tmp_json['data']['track'] if 'track' in tmp_json['data']
            else "N\\A")
        if tmp_string != self.track_title:
            self.track_title = tmp_string
            self._updated = True

        return self._updated
