import logging
import shutil

from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR


class MigrationKnowledgeToTriblerDB:
    def __init__(self, state_dir: Path):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.state_dir = state_dir

        self.knowledge_db_path = self.state_dir / STATEDIR_DB_DIR / 'knowledge.db'
        self.tribler_db_path = self.state_dir / STATEDIR_DB_DIR / 'tribler.db'

        self.logger.info(f'Knowledge DB path: {self.knowledge_db_path}')
        self.logger.info(f'Tribler DB path: {self.tribler_db_path}')

    def run(self) -> bool:
        if not self.knowledge_db_path.exists():
            self.logger.info("Knowledge DB doesn't exist. Stop procedure.")
            return False

        try:
            # move self.knowledge_db_path to self.tribler_db_path
            shutil.move(str(self.knowledge_db_path), str(self.tribler_db_path))
        except OSError as e:
            self.logger.error(f"Failed to move the file: {e}")
            return False

        self.logger.info("File moved successfully.")
        return True
