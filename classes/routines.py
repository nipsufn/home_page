# routines.py
"""This module keep routines functions
"""
import asyncio
import time
import logging
import multiprocessing
import socket
from typing import List
import musicpd
from pywizlight import wizlight, PilotBuilder, exceptions

__logger = logging.getLogger(__name__)

async def __lightbulb_helper(lightbulbs: List[wizlight], brightness: int, colortemp: int) -> None:
    for lightbulb in lightbulbs:
        try:
            await lightbulb.turn_on(
                PilotBuilder(
                    brightness=brightness,
                    colortemp=colortemp))

        except exceptions.WizLightTimeOutError:
            __logger.error("bulb timed out")

def wakeup(consumer_wakeup_int: multiprocessing.connection.Connection,
        config: dict, flag_master_switch: multiprocessing.sharedctypes.SynchronizedBase,
        duration: int = 600, steps: int = 100) -> None:
    """Wakeup procedure"""
    __logger.error("Wakeup routine started")

    if not bool(flag_master_switch):
        __logger.error("Wakeup routine skipped - master switch off")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mpd_client = musicpd.MPDClient()
    mpd_client.connect()
    #eat up all old messages
    while consumer_wakeup_int.poll():
        consumer_wakeup_int.recv()
    wakeup_flag = False
    lightbulbs = [wizlight(socket.gethostbyname(ip)) for ip in config['LIGHTBULBS'].values()]
    bright_start = 0
    bright_stop = 255
    temp_start = 2700
    temp_stop = 6500
    old_volume = mpd_client.status()['volume']

    mpd_client.clear()
    mpd_client.setvol(0)
    mpd_client.add('https://rozhlas.stream/jazz_aac_128.aac')
    mpd_client.play()
    interval = duration / steps
    for i in range(steps):
        if consumer_wakeup_int.poll():
            wakeup_flag = consumer_wakeup_int.recv()
        __logger.info("StopFlag/task: %s", str(wakeup_flag))
        if wakeup_flag:
            mpd_client.setvol(old_volume)
            return
        volume=int((i*int(old_volume))/steps)
        mpd_client.setvol(volume)
        __logger.info("volume: %i", volume)
        bright=int((i * (bright_stop - bright_start) ) / steps + bright_start)
        temp=int((i * (temp_stop - temp_start) ) / steps + temp_start)
        __logger.info("brightness: %i; temperature: %i", bright, temp)
        loop.run_until_complete(
            __lightbulb_helper(lightbulbs, bright, temp)
        )
        time.sleep(interval)
    __logger.error("Wakeup routine finished")

def sunset(config: dict, flag_master_switch: multiprocessing.sharedctypes.SynchronizedBase,
        duration: int = 1200, steps: int = 100) -> None:
    """Sunset procedure"""
    __logger.error("Sunset routine started")

    if not bool(flag_master_switch):
        __logger.error("Wakeup routine skipped - master switch off")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    lightbulbs = [wizlight(socket.gethostbyname(ip)) for ip in config['LIGHTBULBS'].values()]
    bright_start = 0
    bright_stop = 255
    temp_start = 2700
    temp_stop = 2700

    interval = duration / steps
    for i in range(steps):
        bright=int((i * (bright_stop - bright_start) ) / steps + bright_start)
        temp=int((i * (temp_stop - temp_start) ) / steps + temp_start)
        __logger.info("brightness: %i; temperature: %i", bright, temp)
        loop.run_until_complete(
            __lightbulb_helper(lightbulbs, bright, temp)
        )
        time.sleep(interval)
    __logger.error("Sunset routine finished")

#process
#def bulbs_state(config: dict) -> None:
#    __lightbulb_helper(lightbulbs, bright, temp)
