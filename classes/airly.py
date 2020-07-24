# airly.py
"""This module queries Airly.eu and provides retrieved data
"""
import logging
import inspect

from classes.json_from_api import JSONFromAPI

class Airly(JSONFromAPI):
    """This class queries Airly.eu and provides retrieved data
    """
    def __init__(self, location_list, token):
        """Class constructor
        Args:
            location (:list:`str`): forecast location, 'City,xx', xx = country code
            token (str): API token
        """
        super(Airly, self).__init__()
        self.logger = logging.getLogger('eink_status.Airly')
        self.logger.debug('__init__')
        self.__location_list = location_list
        self.__token = token
        self.pm100 = 0.0
        self.pm025 = 0.0
        self.pm001 = 0.0
        self.pm100_limit = 0.0
        self.pm025_limit = 0.0
        self.temp = 20.0
        self.update()

    def update(self):
        """Update smog data
        """
        tmp_const_url = (
            "https://airapi.airly.eu/v2/measurements/installation"
            + "?apikey="
            + self.__token
            + "&installationId="
            )
        for location in self.__location_list:
            tmp_url = tmp_const_url + location
            tmp_json = self._get_json_from_url(tmp_url)
            if tmp_json is None:
                continue
            if tmp_json['current']['indexes'][0]['value'] is None:
                continue
            self.pm100 = tmp_json['current']['values'][2]['value']
            self.pm025 = tmp_json['current']['values'][1]['value']
            self.pm001 = tmp_json['current']['values'][0]['value']
            self.pm100_limit = tmp_json['current']['standards'][1]['limit']
            self.pm025_limit = tmp_json['current']['standards'][0]['limit']
            self.temp = tmp_json['current']['values'][5]['value']

    def is_air_ok(self):
        """Check if smog is within EU norms
        Returns:
            bool: True if smog is within norms, False otherwise
        """
        status = True
        if self.pm100 > self.pm100_limit:
            self.logger.debug("%s: PM10 > PM10_norm",
                              str(inspect.currentframe().f_back.f_lineno))
            status = False
        if self.pm025 > self.pm025_limit:
            self.logger.debug("%s: PM2.5 > PM2.5_norm",
                              str(inspect.currentframe().f_back.f_lineno))
            status = False
        return status
