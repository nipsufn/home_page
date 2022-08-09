# wakeup.py
"""This module wraps wakeup function
"""
import asyncio
import time
import logging
import multiprocessing
import socket
import musicpd
from pywizlight import wizlight, PilotBuilder, exceptions

__logger = logging.getLogger(__name__)

def wakeup(consumer_wakeup_int: multiprocessing.connection.Connection,
        config: dict) -> None:
    """Wakeup procedure process wrapper"""
    __logger.warning("wakeup process wrapper")
    multiprocessing.log_to_stderr()
    proc = multiprocessing.Process(target=wakeup_wrapper,
        args=[consumer_wakeup_int, config])
    proc.start()

def wakeup_wrapper(consumer_wakeup_int: multiprocessing.connection.Connection,
        config: dict) -> None:
    """Wakeup procedure thread wrapper"""
    __logger.warning("wakeup asyncio wrapper")
    #asyncio.new_event_loop().create_task(wakeup_internal(consumer_wakeup_int, config))
    loop = asyncio.new_event_loop()
    loop.run_until_complete(wakeup_internal(consumer_wakeup_int, config))

async def wakeup_internal(consumer_wakeup_int: multiprocessing.connection.Connection,
        config: dict) -> None:
    """Wakeup procedure"""
    __logger.warning("wakeup internal")
    mpd_client = musicpd.MPDClient()
    mpd_client.connect()
    #eat up all old messages
    while consumer_wakeup_int.poll():
        consumer_wakeup_int.recv()
    wakeup_flag = False
    lightbulb = wizlight(socket.gethostbyname(config['LIGHTBULBS']['nightstand']))

    bright_start = 0
    bright_stop = 255
    temp_start = 2700
    temp_stop = 6500
    old_volume = mpd_client.status()['volume']

    mpd_client.clear()
    mpd_client.setvol(0)
    mpd_client.add('https://rozhlas.stream/jazz_aac_128.aac')
    mpd_client.play()
    for i in range(101):
        if consumer_wakeup_int.poll():
            wakeup_flag = consumer_wakeup_int.recv()
        __logger.info("StopFlag/task: %s", str(wakeup_flag))
        if wakeup_flag:
            mpd_client.setvol(old_volume)
            return
        volume=int((i*int(old_volume))/100)
        mpd_client.setvol(volume)
        __logger.info("volume: %i", volume)
        bright=int((i * (bright_stop - bright_start) ) / 100 + bright_start)
        temp=int((i * (temp_stop - temp_start) ) / 100 + temp_start)
        __logger.info("brightness: %i; temperature: %i", bright, temp)
        try:
            await lightbulb.turn_on(
                PilotBuilder(
                    brightness=bright,
                    colortemp=temp))
        except exceptions.WizLightTimeOutError:
            __logger.warning("bulb timed out")
        time.sleep(6)

def sunset(config: dict) -> None:
    """Wakeup procedure process wrapper"""
    __logger.warning("wakeup process wrapper")
    multiprocessing.log_to_stderr()
    proc = multiprocessing.Process(target=sunset_wrapper,
        args=[config])
    proc.start()

def sunset_wrapper(config: dict) -> None:
    """Wakeup procedure thread wrapper"""
    __logger.warning("wakeup asyncio wrapper")
    #asyncio.new_event_loop().create_task(wakeup_internal(consumer_wakeup_int, config))
    loop = asyncio.new_event_loop()
    loop.run_until_complete(sunset_internal(config))

async def sunset_internal(config: dict) -> None:
    """Sunset procedure"""
    lightbulb = wizlight(config['LIGHTBULBS']['nightstand'])

    bright_start = 0
    bright_stop = 255
    temp_start = 2700
    temp_stop = 2700

    for i in range(101):
        bright=int((i * (bright_stop - bright_start) ) / 100 + bright_start)
        temp=int((i * (temp_stop - temp_start) ) / 100 + temp_start)
        __logger.info("brightness: %i; temperature: %i", bright, temp)
        asyncio.run(
            lightbulb.turn_on(
                PilotBuilder(
                    brightness=bright,
                    colortemp=temp)))
        time.sleep(6)
