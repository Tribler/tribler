import yappi
from Tribler.Main.tribler import run

if __name__ == '__main__':
    yappi.start()
    run()
    yappi.stop()
    yappi.get_func_stats().print_all()

