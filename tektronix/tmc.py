"""communication protocol: SCPI over USB-TMC"""

import logging

import gevent
import usbtmc



def gapply(func, *args, **kwargs):
    return gevent.get_hub().threadpool.apply(func, args, kwargs)


class TMC(object):

    def __init__(self, *args, **kwargs):
        self.log = logging.getLogger('USB')
        self._raw_handler = usbtmc.Instrument(*args, **kwargs)

    def write(self, msg):
        self.log.debug('Tx: %r', msg)
        return gapply(self._raw_handler.write_raw, msg)

    def read(self, size=-1):
        reply = gapply(self._raw_handler.read_raw, num=size)
        self.log.debug('Rx: %r', reply)
        return reply

    def write_read(self, msg, size=-1):
        self.log.debug('Tx: %r', msg)
        reply = gapply(self._raw_handler.ask_raw, msg, num=size)
        self.log.debug('Rx: %r', reply)
        return reply





