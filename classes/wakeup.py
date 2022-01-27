# wakeup.py
"""This module wraps wakeup function
"""
import asyncio
import time
import logging
import multiprocessing
import musicpd
from pywizlight import wizlight, PilotBuilder

__logger = logging.getLogger(__name__)
__log_handler = logging.StreamHandler()
__log_handler.setFormatter(
    logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )
    )
__logger.addHandler(__log_handler)

def wakeup(consumer_wakeup_int: multiprocessing.connection.Connection,
        config: dict) -> None:
    """Wakeup procedure"""
    mpd_client = musicpd.MPDClient()
    mpd_client.connect()
    #eat up all old messages
    while consumer_wakeup_int.poll():
        consumer_wakeup_int.recv()
    wakeup_flag = False
    lightbulb = wizlight(config['LIGHTBULBS']['nightstand'])

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
        volume=int((i*old_volume)/100)
        mpd_client.setvol(volume)
        __logger.info("volume: %i", volume)
        bright=int((i * (bright_stop - bright_start) ) / 100 + bright_start)
        temp=int((i * (temp_stop - temp_start) ) / 100 + temp_start)
        __logger.info("brightness: %i; temperature: %i", bright, temp)
        asyncio.run(
            lightbulb.turn_on(
                PilotBuilder(
                    brightness=bright,
                    colortemp=temp)))
        time.sleep(6)
