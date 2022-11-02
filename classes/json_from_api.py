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
        self.logger = logging.getLogger(type(self).__name__)
        self.logger.debug('Class initialized')

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
            self.logger.warning("HTTP connection error!")
            self.logger.info(str(error))
            return None
        except requests.exceptions.Timeout as error:
            self.logger.warning("HTTP timeout!")
            self.logger.info(str(error))
            return None
        except requests.exceptions.HTTPError as error:
            self.logger.warning("HTTP Error: %i %s", error.response.status_code,
                             error.response.reason)
            self.logger.info(str(error))
            return None
        if response.content is None:
            self.logger.error("Undefined error!\n")
            return None
        try:
            return json.loads(response.content)
        except json.decoder.JSONDecodeError as error:
            self.logger.warning("JSON parsing error!")
            self.logger.info(str(error))
            return None
        return None
