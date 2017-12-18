from enum import Enum
from collections import namedtuple

import pint
import louie
import numpy
import gevent

from .tmc import TMC

U = pint.UnitRegistry()
volt = U.volt
ampere = U.ampere


class DataFormat(Enum):
    """Possible values for DATa:ENCdg"""

    ASCII = 'ASCII'
    RIB = 'RIBINARY'
    RPB = 'RPBINARY'
    SRI = 'SRIBINARY'
    SRP = 'SRPBINARY'


class DataTarget(Enum):
    REFA = 'REFA'
    REFB = 'REFB'


class DataSource(Enum):

    CH1 = 'CH1'
    CH2 = 'CH2'
    CH3 = 'CH3'
    CH4 = 'CH4'
    CH5 = 'CH5'
    CH6 = 'CH6'
    CH7 = 'CH7'
    CH8 = 'CH8'
    MATH = 'MATH'
    REFA = 'REFA'
    REFB = 'REFB'
    FFT = 'FFT'


class AcquisitionMode(Enum):
    SAMPLE = 'SAMPLE'
    PEAKDETECT = 'PEAKDETECT'
    AVERAGE = 'AVERAGE'


class Coupling(Enum):
    AC = 'AC'
    DC = 'DC'
    GND = 'GND'


def apply_casts_strs(strs, *casts):
    return [cast(s) for s, cast in zip(strs, casts)]


def apply_casts(msg, *casts):
    strs = map(str.strip, msg.split(';'))
    return apply_casts_strs(strs, *casts)


def NamedTuple(name, *args):
    pars, casts = zip(*args)
    ntype = namedtuple(name, pars)
    ntype.fromstring = staticmethod(lambda msg: ntype(*apply_casts(msg,
                                                                   *casts)))
    return ntype


def Unit(u, decode=float):
    return lambda v: decode(v)*u


def OnOff(msg):
    return 'ON' == msg.strip().upper()


Data = NamedTuple('Data', ('format', DataFormat), ('target', DataTarget),
                  ('source', DataSource), ('start', int), ('stop', int),
                  ('width', int))


Acquire = NamedTuple('Acquire', ('mode', AcquisitionMode), ('nb_acq', int),
                     ('nb_avg', int), ('state', str))


VChannel = namedtuple('VChannel', 'voltage_probe_scale current_probe_scale ' \
                      'scale position_div coupling bandwith invert unit position')
def to_VChannel(msg):
    strs = map(str.strip, msg.split(';'))
    strs[-1] = strs[-1].strip('"')
    unit = U(strs[-1])
    args = apply_casts_strs(strs, Unit(volt), Unit(ampere), Unit(unit), float,
                            Coupling, OnOff, OnOff, str)
    args.append(args[2] * args[3]) # scale * position_div
    return VChannel(*args)
VChannel.fromstring = staticmethod(to_VChannel)


class Curve(object):

    def __init__(self, channel):
        self.channel = channel
        self.task = None

    def start(self):
        self.stop()
        self.task = gevent.spawn(self._update_loop)

    def stop(self):
        if self.task is not None:
            self.task.kill()

    def _update_loop(self):
        instrument = self.channel.instrument
        while True:
            louie.send('new_curve', instrument, self())

    def __call__(self):
        channel = self.channel
        channel_value = str(channel)
        instrument = channel.instrument
        data = instrument.get_data_format()._asdict()
        if data['source'] != channel_value:
            instrument['DATA:SOURCE'] = channel_value
        if data['width'] != 1:
            raise NotImplementedError
        raw_curve = instrument['CURVE']
        ylen = int(raw_curve[1])
        nb_points = int(raw_curve[2:2+ylen])
        curve = numpy.frombuffer(raw_curve, dtype=numpy.int8,
                                 count=nb_points, offset=2+ylen)
        data['nb_points'] = nb_points
        data['curve'] = self
        data['instrument'] = instrument
        data['value'] = curve
        data['channel'] = channel
        data.update(channel.get_vertical()._asdict())
        return data


class Channel(object):

    def __init__(self, instrument, channel):
        self.instrument = instrument
        self.channel = channel
        self.curve = Curve(self)

    def __int__(self):
        return self.channel

    def __str__(self):
        return 'CH{0}'.format(self.channel)

    def get_vertical(self, cache=True):
        return self.instrument.get_vertical_channel(self.channel, cache=cache)

    def get_current_curve(self):
        return self.curve()


class Tektronix:

    def __init__(self, *args, **kwargs):
        self._comm = TMC(*args, **kwargs)
        self._cache = {}
        c1 = Channel(self, channel=1)
        self.channels = {
            1: c1,
            DataSource.CH1: c1,
        }

    def __getitem__(self, names):
        if isinstance(names, (str, unicode)):
            return self._comm.write_read(names+'?').strip()
        if isinstance(names, int):
            return self.channels[names]
        return [self[name] for name in names]

    def __setitem__(self, names, values):
        single = isinstance(names, (str, unicode))
        if single:
            return self._comm.write('{0} {1}'.format(names, values))
        for name, value in zip(names, values):
            self[name] = value

    def get_curve(self, channel=1):
        return self.channels[channel].curve

    def get_current_curve(self, channel=1):
        return self.channels[channel].get_current_curve()

    def get_vertical_channel(self, channel=1, cache=True):
        channel = self.channels[channel]
        ch = str(channel)
        data = self._cache.get(ch)
        if data is None:
            self._cache[ch] = data = VChannel.fromstring(self[ch])
        return data

    def get_data_format(self, cache=True):
        data = self._cache.get('DATA')
        if data is None:
            self._cache['DATA'] = data = Data.fromstring(self['DATA'])
        return data

    def get_acquire(self, cache=True):
        acquire = self._cache.get('ACQUIRE')
        if acquire is None:
            self._cache['ACQUIRE'] = acquire = Acquire.fromstring(self['ACQUIRE'])
        return acquire


if __name__ == '__main__':
    import usbtmc
    devices = usbtmc.list_devices()
    tek = Tektronix(devices[0])
