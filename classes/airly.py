# airly.py
"""This module queries Airly.eu and provides retrieved data
"""
import logging
import inspect
import multiprocessing

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
        self.logger = logging.getLogger(__name__)
        log_handler = logging.StreamHandler()
        log_handler.setFormatter(
            logging.Formatter(
                '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
                )
            )
        self.logger.addHandler(log_handler)
        self.logger.debug('__init__')
        self.__location_list = location_list
        self.__token = token
        self.pm100 = 0.0
        self.pm025 = 0.0
        self.pm001 = 0.0
        self.pm100_limit = 0.0
        self.pm025_limit = 0.0
        self.temp = 20.0
        self.press = 1000.0
        self.humi = 50.0
        self._updated = False
        self.__update()

    def __update(self) -> bool:
        """Update smog data"""
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
            self.logger.debug(location)
            self.pm100 = tmp_json['current']['values'][2]['value']
            self.pm025 = tmp_json['current']['values'][1]['value']
            self.pm001 = tmp_json['current']['values'][0]['value']
            self.pm100_limit = tmp_json['current']['standards'][1]['limit']
            self.pm025_limit = tmp_json['current']['standards'][0]['limit']
            self.temp = tmp_json['current']['values'][5]['value']
            self.press = tmp_json['current']['values'][3]['value']
            self.humi = tmp_json['current']['values'][4]['value']
            self._updated = True

            return True
        self.logger.warning('update not successful')
        return False

    def update(self, producer_arl: multiprocessing.connection.Connection) -> bool:
        """Update and send smog data"""
        ret = self.__update()
        if ret:
            self.logger.warning("arl: sending")
            producer_arl.send({
                'pm100': self.pm100,
                'pm025': self.pm025,
                'pm001': self.pm001,
                'pm100_limit': self.pm100_limit,
                'pm025_limit': self.pm025_limit,
                'temp': self.temp,
                'press': self.press,
                'humi': self.humi,
                'updated': self._updated,
                'is_air_ok': self.is_air_ok()
            })
            return True
        return False

    def is_air_ok(self) -> bool:
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
