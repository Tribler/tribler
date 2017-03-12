import logging.config
import multiprocessing
import os
import sys


if os.path.exists("logger.conf"):
    logging.config.fileConfig("logger.conf")

if __name__ == "__main__":
    if 'TUNNEL_SUBPROCESS' in os.environ:
        from Tribler.community.tunnel.processes.tunnel_subprocess import TunnelSubprocess
        from twisted.internet import reactor
        subprocess = TunnelSubprocess()
        subprocess.start()
        reactor.run()
        sys.exit(0)

    multiprocessing.freeze_support()

    from TriblerGUI.tribler_app import TriblerApplication
    from TriblerGUI.tribler_window import TriblerWindow

    app = TriblerApplication("triblerapp", sys.argv)

    if app.is_running():
        for arg in sys.argv[1:]:
            if os.path.exists(arg):
                app.send_message("file:%s" % arg)
            elif arg.startswith('magnet'):
                app.send_message(arg)
        sys.exit(1)

    window = TriblerWindow()
    window.setWindowTitle("Tribler")
    app.set_activation_window(window)
    app.parse_sys_args(sys.argv)
    sys.exit(app.exec_())
