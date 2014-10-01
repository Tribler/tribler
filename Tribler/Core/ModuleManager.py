import logging
from threading import RLock

from Tribler.Category.Category import Category
from Tribler.Core.Tag.Extractor import TermExtractor
from Tribler.Core.Video.VideoPlayer import VideoPlayer


class ModuleManager(object):

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._lock = RLock()

        self.session = session
        self.category = None
        self.term_extractor = None
        self.video_player = None

    def initialise(self, utility):
        with self._lock:
            self._logger.info(u"Initialising modules...")

            self._logger.info(u"Initialising Category...")
            self.category = Category(self.session.get_install_dir())
            state = utility.read_config('family_filter')
            if state in (1, 0):
                self.category.set_family_filter(state == 1)
            else:
                utility.write_config('family_filter', 1)
                utility.flush_config()

                self.category.set_family_filter(True)

            self._logger.info(u"Initialising TermExtractor...")
            self.term_extractor = TermExtractor(self.session.get_install_dir())

            self._logger.info(u"Initialising VideoPlayer...")
            if self.session.get_videoplayer():
                self.video_player = VideoPlayer(self.session)

    def finalise(self):
        with self._lock:
            self._logger.info(u"Finalising modules...")

            self.category = None
            self.term_extractor = None

            self.video_player.shutdown()
            self.video_player = None

    def get_category(self):
        with self._lock:
            return self.category

    def get_term_extractor(self):
        with self._lock:
            return self.term_extractor

    def get_video_player(self):
        with self._lock:
            return self.video_player