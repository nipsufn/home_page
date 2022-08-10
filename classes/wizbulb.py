# wizbulb.py
"""This module wraps WIZ lightbulb helper functions
"""
import sys
import logging
import socket
import asyncio
from pywizlight import wizlight, PilotBuilder, exceptions

__logger = logging.getLogger(__name__)

def get_rgb_tuple(rgb_hex_string: str) -> tuple:
    """take hex string `aabbcc` and split out to decimal R, G, B tuple"""
    return tuple(int(rgb_hex_string[i:i+2], 16) for i in (0, 2, 4))

def set_bulb_sync(bulb_request: dict, config: dict) -> None:
    """wrapper to run the function synchronously"""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(set_bulb(bulb_request, config))

async def set_bulb(bulb_request: dict, config: dict) -> None:
    """handle bulb-related requests"""
    __logger.warning("setting the goddamn bulbs")
    bulbs = []
    for bulb_ip in bulb_request.args.getlist('bulb'):
        for bulb in bulb_ip.split(','):
            bulbs.append(bulb)
    if len(bulbs) == 1 and bulbs[0] == 'all':
        bulbs = config['LIGHTBULBS'].keys()
    for bulb_ip in bulbs:
        lightbulb = wizlight(socket.gethostbyname(config['LIGHTBULBS'][bulb_ip]))
        if bulb_request.args['op'] == 'off':
            __logger.warning("op off")
            await lightbulb.turn_off()

        if bulb_request.args['op'] == 'on' \
            and 'brightness' in bulb_request.args:
            pilot = PilotBuilder()
            if 'temperature' in bulb_request.args:
                pilot = PilotBuilder(
                    brightness=int(bulb_request.args['brightness']),
                    colortemp=int(bulb_request.args['temperature']))
            if 'rgb' in bulb_request.args:
                pilot = PilotBuilder(
                    brightness=int(bulb_request.args['brightness']),
                    rgb=get_rgb_tuple(bulb_request.args['rgb']))
            if 'colour' in bulb_request.args:
                colour = (0,0,0)
                if bulb_request.args['colour'] == 'red':
                    colour = (255,0,0)
                pilot = PilotBuilder(
                    brightness=int(bulb_request.args['brightness']),
                    rgb=colour)
            attempts = 0
            while attempts < 5:
                try:
                    await lightbulb.turn_on(pilot)
                    break
                # pylint: disable-next=broad-except
                except Exception as exc:
                    attempts += 1
                    __logger.warning("couldn't set bulb %s", str(exc))

async def get_bulb(config: dict) -> dict:
    """get information about bulb"""
    out = {}
    for bulb in config['LIGHTBULBS']:
        ip_address = socket.gethostbyname(config['LIGHTBULBS'][bulb])
        lightbulb = wizlight(ip_address)
        try:
            await lightbulb.updateState()
            out[bulb]={
                'ip': ip_address,
                'hostname': config['LIGHTBULBS'][bulb],
                'brightness': lightbulb.state.get_brightness(),
                'temperature': lightbulb.state.get_colortemp()
                }
        except exceptions.WizLightConnectionError:
            exc_type, value, _ = sys.exc_info()
            __logger.warning("%s: %s -  %s", exc_type.__name__, value, bulb)
        except AttributeError:
            exc_type, value, _ = sys.exc_info()
            __logger.warning("%s: %s -  %s", exc_type.__name__, value, bulb)
    return out
