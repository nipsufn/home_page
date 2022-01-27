# wizbulb.py
"""This module wraps WIZ lightbulb helper functions
"""
import asyncio
import sys
import logging
from pywizlight import wizlight, PilotBuilder, exceptions

__logger = logging.getLogger(__name__)
__log_handler = logging.StreamHandler()
__log_handler.setFormatter(
    logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )
    )
__logger.addHandler(__log_handler)

def get_rgb_tuple(rgb_hex_string: str) -> tuple:
    """take hex string `aabbcc` and split out to decimal R, G, B tuple"""
    return tuple(int(rgb_hex_string[i:i+2], 16) for i in (0, 2, 4))

def set_bulb(bulb_request: dict, config: dict) -> None:
    """handle bulb-related requests"""
    for bulb_ip in bulb_request.args.getlist('bulb'):
        lightbulb = wizlight(config['LIGHTBULBS'][bulb_ip])
        if bulb_request.args['op'] == 'off':
            asyncio.run(lightbulb.turn_off())

        if bulb_request.args['op'] == 'on' \
            and 'brightness' in bulb_request.args:
            if 'temperature' in bulb_request.args:
                asyncio.run(
                    lightbulb.turn_on(
                        PilotBuilder(
                            brightness=int(bulb_request.args['brightness']),
                            colortemp=int(bulb_request.args['temperature']))))
            if 'rgb' in bulb_request.args:
                asyncio.run(
                    lightbulb.turn_on(
                        PilotBuilder(
                            brightness=int(bulb_request.args['brightness']),
                            rgb=get_rgb_tuple(bulb_request.args['rgb'])
                            )))
            if 'colour' in bulb_request.args:
                colour = (0,0,0)
                if bulb_request.args['colour'] == 'red':
                    colour = (255,0,0)
                asyncio.run(
                    lightbulb.turn_on(
                        PilotBuilder(
                            brightness=int(bulb_request.args['brightness']),
                            rgb=colour)))
def get_bulb(config: dict) -> dict:
    """get information about bulb"""
    out = {}
    for bulb in config['LIGHTBULBS']:
        lightbulb = wizlight(config['LIGHTBULBS'][bulb])
        try:
            asyncio.run(lightbulb.updateState())
            out[bulb]={
                'ip': config['LIGHTBULBS'][bulb],
                'brightness': lightbulb.state.get_brightness(),
                'temperature': lightbulb.state.get_colortemp()
                }
        except exceptions.WizLightConnectionError:
            exc_type, value, _ = sys.exc_info()
            __logger.warning("%s: %s -  %s", exc_type.__name__, value, bulb)
    return out
