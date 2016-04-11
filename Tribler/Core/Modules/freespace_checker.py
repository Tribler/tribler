from twisted.internet.task import LoopingCall
from Tribler.Core.osutils import get_free_space
from Tribler.Core.simpledefs import NTFY_FREE_SPACE, NTFY_INSERT
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.dispersy.taskmanager import TaskManager


FREE_SPACE_CHECK_INTERVAL = 300


class FreeSpaceChecker(TaskManager):

    def __init__(self, session):
        super(FreeSpaceChecker, self).__init__()

        self.session = session
        self.check_path = DefaultDownloadStartupConfig.getInstance().get_dest_dir()
        self.free_space = 0

    def start(self):
        self.free_space_check_task = self.register_task("check free disk space", LoopingCall(self.check_free_space))
        self.free_space_check_task.start(FREE_SPACE_CHECK_INTERVAL)

    def stop(self):
        self.cancel_all_pending_tasks()

    def check_free_space(self):
        self.free_space = get_free_space(self.check_path)
        self.session.notifier.notify(NTFY_FREE_SPACE, NTFY_INSERT, None, self.free_space)
