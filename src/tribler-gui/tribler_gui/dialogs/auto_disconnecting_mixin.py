import logging
from collections import defaultdict
from threading import RLock

from PyQt5.QtCore import pyqtBoundSignal

from tribler_gui.utilities import connect, disconnect

lock = RLock()
logger = logging.getLogger('QAutoDisconnectingMixin')


class QAutoDisconnectingMixin:
    enabled = False

    def lazy_init(self):
        if not QAutoDisconnectingMixin.enabled:
            return

        with lock:
            # abbreviation "adm" here is the attempt to avoid naming conflicts
            if hasattr(self, 'adm_inited'):
                return

            self.adm_inited = True
            self.adm_destroyed_callback_connected = False
            self.adm_connected_signals = {}
            self.adm_connected_callbacks = defaultdict(set)

            if hasattr(self, 'destroyed') and isinstance(self.destroyed, pyqtBoundSignal):
                connect(self.destroyed, self.on_adm_destroy)

                self.adm_destroyed_callback_connected = True

                logger.info(f'Initialized: {self.__class__.__name__}')

    def connect_signal(self, signal, callback):
        if not callback:
            return

        if not QAutoDisconnectingMixin.enabled:
            connect(signal, callback)
            return

        self.lazy_init()

        with lock:
            signal_id = id(signal)

            # prevent double connect for a signal-callback pair
            if callback not in self.adm_connected_callbacks[signal_id]:
                connect(signal, callback)

            if self.adm_destroyed_callback_connected:
                self.adm_connected_signals[signal_id] = signal
                self.adm_connected_callbacks[signal_id].add(callback)

            logger.info(f'Connected: {self.__class__.__name__}-{signal_id}')

    def on_adm_destroy(self, *args):
        if not QAutoDisconnectingMixin.enabled:
            return

        with lock:
            if not self.adm_connected_signals:
                return

            for signal_id, signal in self.adm_connected_signals.items():
                for callback in self.adm_connected_callbacks[signal_id]:
                    try:
                        disconnect(signal, callback)

                        logger.info(f'Disconnected: {self.__class__.__name__}-{signal_id}')
                    except Exception as e:
                        logger.error(f'Error while disconnect {self.__class__.__name__}-{signal_id}: {e}')

            self.adm_connected_signals = None
            self.adm_connected_callbacks = None
