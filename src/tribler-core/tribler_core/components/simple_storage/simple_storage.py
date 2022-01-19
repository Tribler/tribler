import asyncio
import logging

from pydantic import BaseModel

from tribler_core.utilities.path_util import Path

DEFAULT_SAVE_INTERVAL = 5 * 60  # force Storage to save data every 5 minutes


class StorageData(BaseModel):
    last_processed_torrent_id: int = 0


class SimpleStorage:
    """ SimpleStorage is object storage that stores data in JSON format and uses
    `pydantic` `BaseModel` for defining models.

    It stores data on a shutdown and every 5 minutes.

    limitations:
     *   No transactions: last five-minute changes can be lost on Tribler crash, so the
            application code should be tolerable to this and be ready, for example, to
            process the same torrents again after the Tribler restart.
     *   If two instances of the application try to use the same storage simultaneously,
            they will not see the changes made by another instance.
    """

    def __init__(self, path: Path, save_interval: float = DEFAULT_SAVE_INTERVAL):
        """
        Args:
            path: path to the file with storage. Could be a path to a non existent file.
            save_interval: interval in seconds in which the storage will store a data to a disk.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.data = StorageData()

        self.path = path
        self.save_interval = save_interval

        self._loop = asyncio.get_event_loop()
        self._task: asyncio.TimerHandle = self._loop.call_later(self.save_interval, self._save_and_schedule_next)

    def load(self) -> bool:
        """ Load data from `self.path`. In case the file doesn't exist, the function
        will create the data with defaults values.
        """
        self.logger.info(f'Loading storage from {self.path}')
        loaded = False

        try:
            self.data = StorageData.parse_file(self.path)
        except FileNotFoundError:
            self.logger.info('The storage file does not exist.')
        except Exception as e:  # pylint: disable=broad-except
            self.logger.exception(e)
        else:
            loaded = True
            self.logger.info(f'Loaded storage: {self.data}')

        if not loaded:
            self.logger.info('Create a new storage.')
            self.data = StorageData()

        return loaded

    def save(self):
        """ Save data to the `self.path`.
        """
        self.logger.info(f'Saving storage to: {self.path}.\nStorage {self.data}')
        self.path.write_text(self.data.json())

    def _save_and_schedule_next(self):
        """ Save data and schedule the next call of save function after `self.save_interval`
        """
        self.save()
        self._task = self._loop.call_later(self.save_interval, self._save_and_schedule_next)

    def shutdown(self):
        self._task.cancel()
        self.save()
