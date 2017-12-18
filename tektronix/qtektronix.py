from functools import partial

import louie
import gevent

from . import qt
from .tektronix import DataSource

from pyqtgraph import GraphicsWindow


class QTektronix(qt.QObject):

    signals = qt.Signal(object, object)

    def __init__(self, instrument, parent=None):
        super(QTektronix, self).__init__(parent)
        self.instrument = instrument
        louie.connect(self._on_instrument_event, sender=instrument)

    def _on_instrument_event(self, value, signal):
        self.signals.emit(signal, value)


@qt.ui_loadable
class QOscilloscope(qt.QWidget):

    def __init__(self, instrument, parent=None):
        super(QOscilloscope, self).__init__(parent)
        self.instrument = instrument
        self.qinstrument = QTektronix(instrument)
        self.load_ui()
        ui = self.ui
        ui.plot_window = GraphicsWindow(title='Curve')
        ui.plot_placeholder.layout().addWidget(ui.plot_window)
        ui.plot_widget = ui.plot_window.addPlot()

        self.curves = {}
        for button, channel, data_source in ((ui.CH1, 1, DataSource.CH1),):
            curve = ui.plot_widget.plot(pen='y')
            self.curves[channel] = curve
            self.curves[data_source] = curve
            button.toggled.connect(partial(self._on_update_curve, data_source))

        self.qinstrument.signals.connect(self._on_instrument_event)

    def _on_instrument_event(self, event, value):
        if event == 'new_curve':
            qcurve = self.curves[value['source']]
            qcurve.setData(value['value'])

    def _on_update_curve(self, source, update):
        curve = self.instrument.channels[source].curve
        qcurve = self.curves[source]
        if update:
            curve.start()
        else:
            curve.stop()
            qcurve.setData(())


def main():
    import usbtmc
    from .tektronix import Tektronix

    devices = usbtmc.list_devices()
    tek = Tektronix(devices[0])

    app = qt.QApplication([])
    win = QOscilloscope(tek)
    win.resize(1600,600)
    win.setWindowTitle('Tektronix TDS 2014C')
    win.show()
    def update():
        gevent.sleep(0.01)
    timer = qt.QTimer()
    timer.timeout.connect(update)
    timer.start(10)
    app.exec_()


if __name__ == '__main__':
    main()
