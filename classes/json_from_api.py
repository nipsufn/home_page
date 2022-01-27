# json_from_api.py
"""This module wraps requests module to return json data
"""
import json
import logging
import requests

class JSONFromAPI:
    """This class wraps requests module to return json data
    """
    def __init__(self):
        """Class constructor
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('__init__')

    def _get_json_from_url(self, url, timeout=10):
        """Protected: retrives json from URL
        Args:
            url (str): URL
            timeout (int, optional): timeout (in seconds), defaults to 10s

        Returns:
            :object:`json`: image containing the plot
        """
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as error:
            self.logger.info("HTTP connection error!")
            self.logger.debug(str(error))
            return None
        except requests.exceptions.Timeout as error:
            self.logger.info("HTTP timeout!")
            self.logger.debug(str(error))
            return None
        except requests.exceptions.HTTPError as error:
            self.logger.info("HTTP Error: %i %s", error.response.status_code,
                             error.response.reason)
            self.logger.debug(str(error))
            return None
        if response.content is None:
            self.logger.warning("Undefined error!\n")
            return None
        try:
            return json.loads(response.content)
        except json.decoder.JSONDecodeError as error:
            self.logger.info("JSON parsing error!")
            self.logger.debug(str(error))
            return None
        return None
