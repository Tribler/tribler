import yappi
from Tribler.Main.tribler import run

if __name__ == '__main__':
    yappi.start(builtins=True)
    run()
    yappi.stop()
    # yappi.get_func_stats().sort("tsub").print_all()

    filename = 'callgrind.yappi'
    yappi.get_func_stats().save(filename, type='callgrind')