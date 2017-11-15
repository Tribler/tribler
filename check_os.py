import argparse
import logging
import pkgutil
import tempfile

import os

import sys
from twisted.scripts.twistd import runApp, ServerOptions
from twisted.python import usage

logger = logging.getLogger("CheckOs")

def error_and_exit(title, main_text):
    """
    Show a pop-up window and sys.exit() out of Python.

    :param title: the short error description
    :param main_text: the long error description
    """
    # NOTE: We don't want to load all of these imports normally.
    #       Otherwise we will have these unused GUI modules loaded in the main process.
    from Tkinter import Tk, Canvas, DISABLED, INSERT, Label, Text, WORD

    root = Tk()
    root.wm_title("Tribler: Critical Error!")
    root.wm_minsize(500, 300)
    root.wm_maxsize(500, 300)
    root.configure(background='#535252')

    Canvas(root, width=500, height=50, bd=0, highlightthickness=0, relief='ridge', background='#535252').pack()
    pane = Canvas(root, width=400, height=200, bd=0, highlightthickness=0, relief='ridge', background='#333333')
    Canvas(pane, width=400, height=20, bd=0, highlightthickness=0, relief='ridge', background='#333333').pack()
    Label(pane, text=title, width=40, background='#333333', foreground='#fcffff', font=("Helvetica", 11)).pack()
    Canvas(pane, width=400, height=20, bd=0, highlightthickness=0, relief='ridge', background='#333333').pack()

    main_text_label = Text(pane, width=45, height=6, bd=0, highlightthickness=0, relief='ridge', background='#333333',
                           foreground='#b5b5b5', font=("Helvetica", 11), wrap=WORD)
    main_text_label.tag_configure("center", justify='center')
    main_text_label.insert(INSERT, main_text)
    main_text_label.tag_add("center", "1.0", "end")
    main_text_label.config(state=DISABLED)
    main_text_label.pack()

    pane.pack()

    root.mainloop()


def check_read_write():
    """
    Check if we have access to file IO, or exit with an error.
    """
    try:
        tempfile.gettempdir()
    except IOError:
        error_and_exit("No write access!",
                       "Tribler does not seem to be able to have access to your filesystem. " +
                       "Please grant Tribler the proper permissions and try again.")


def check_environment():
    """
    Perform all of the pre-Tribler checks to see if we can run on this platform.
    """
    check_read_write()

class MyServerOptions(ServerOptions):
    """
    See twisted.application.app.ServerOptions.subCommands().
    Override to specify a single plugin subcommand and load the plugin
    explictly.
    """

    def __init__(self, *a, **kw):
        ServerOptions.__init__(self, *a, **kw)
        self.plugin = None
        self.loadedPlugins = {}

    def setPlugin(self, plugin):
        self.plugin = plugin

    def subCommands(self):
        self.loadedPlugins = {self.plugin.tapname: self.plugin}
        yield (self.plugin.tapname, None, lambda plugin=self.plugin: plugin.options(), self.plugin.description)

    subCommands = property(subCommands)


def parse_arguments():
    """
    Parse the command line arguments
    :return: parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-headless", "--headless", help='Run Tribler in headless mode', action="store_true",
                        required=False)
    parser.add_argument("-plugin", "--plugin", type=str, help="Run a plugin", required=False)
    parser.add_argument("-pidfile", "--pidfile", type=str, help="PID file", required=False)
    parser.add_argument("-logfile", "--logfile", type=str, help="Log file", required=False)
    parser.add_argument('args', nargs=argparse.REMAINDER)

    args, unknowns = parser.parse_known_args()
    print "unknown:", unknowns
    return args, unknowns


def load_plugin_from_arg(args, unknowns):
    """
    Loads an appropriate plugin based on the arguments passed
    :param args: parsed command line arguments
    """
    args_plugin = args.plugin
    unknowns = unknowns or []

    if '_plugin' in args_plugin:
        logger.error("No suffix '_plugin' is expected in plugin name")
        return

    # Load tribler plugin if --headless argument is specified
    if args.headless or args_plugin == 'tribler':
        import Tribler.plugins.tribler_plugin as tribler_plugin
        plugin = tribler_plugin.service_maker
        run_plugin(plugin, args, unknowns)

    # Loading the appropriate plugin based on the name
    # TODO: Load plugins dynamically based on plugin module name
    elif args_plugin == 'torrent_downloader':
        import Tribler.plugins.torrent_downloader_plugin as downloader_plugin
        plugin = downloader_plugin.service_maker
        run_plugin(plugin, args, unknowns)

    # If unknown plugin is listed, show the list of available plugins
    else:
        plugin_dir = os.path.join(os.path.dirname(__file__), "Tribler", "plugins")
        available_plugins = [name.replace("_plugin", "") for _, name, _ in pkgutil.iter_modules([plugin_dir])]
        logger.error("No such plugin ['%s']", args_plugin)
        logger.error("Available plugins:%s", available_plugins)


def run_plugin(plugin, args, unknowns):
    """
    Runs the twistd plugin
    :param plugin: Twistd plugin to run
    :param args: Parsed command line arguments
    """
    # Set pidfile and logfile for the plugin if one does not exist
    unknowns = unknowns or []
    sys.argv[1:] = ['--pidfile', args.pidfile if args.pidfile else "/tmp/%s.pid" % plugin.tapname,
                    '--logfile', args.logfile if args.logfile else "/tmp/%s.log" % plugin.tapname,
                    plugin.tapname] + unknowns + args.args
    logger.info("Executing Plugin[%s] with arguments %s", plugin.tapname, sys.argv)

    # Attach the plugin to server options config
    config = MyServerOptions()
    config.setPlugin(plugin)

    try:
        config.parseOptions()
        runApp(config)
    except usage.error as ue:
        logging.error(config)
        logging.error("%s: %s", sys.argv[0], ue)
