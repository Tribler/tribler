import sys
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

    from TriblerGUI.single_application import QtSingleApplication
    from TriblerGUI.tribler_window import TriblerWindow

    app = QtSingleApplication("triblerapp2", sys.argv)

    if app.is_running():
        sys.exit(1)

    window = TriblerWindow()
    window.setWindowTitle("Tribler")
    app.set_activation_window(window)
    sys.exit(app.exec_())
