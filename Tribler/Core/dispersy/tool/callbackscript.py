from Tribler.Core.dispersy.script import ScriptBase

class DispersyCallbackScript(ScriptBase):
    def run(self):
        self.caller(self.previous_performance_profile)
        self.caller(self.register)
        self.caller(self.register_delay)
        self.caller(self.generator)

    def previous_performance_profile(self):
        """
Run on MASAQ Dell laptop 23/04/12
> python -O Tribler/Main/dispersy.py --enable-dispersy-script --script dispersy-callback --yappi

YAPPI:          1x       2.953s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/callback.py._loop:506
YAPPI:     210020x       0.964s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/callback.py.register:212
YAPPI:     520985x       0.390s /usr/lib/python2.7/threading.py.isSet:380
YAPPI:          4x       0.104s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/tool/callbackscript.py.register_delay:81
YAPPI:          3x       0.100s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/tool/callbackscript.py.register:68
YAPPI:     110000x       0.092s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/tool/callbackscript.py.generator_func:95
YAPPI:     100000x       0.083s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/tool/callbackscript.py.register_delay_func:82
YAPPI:     100000x       0.082s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/tool/callbackscript.py.register_func:69
YAPPI:        867x       0.024s /usr/lib/python2.7/threading.py.wait:235
YAPPI:          5x       0.012s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/tool/callbackscript.py.generator:94
YAPPI:        867x       0.007s /usr/lib/python2.7/threading.py.wait:400
YAPPI:        379x       0.005s /home/boudewijn/local/lib/python2.7/site-packages/yappi.py.__init__:50
YAPPI:        867x       0.003s /usr/lib/python2.7/threading.py._acquire_restore:223
YAPPI:          1x       0.003s Tribler/Main/dispersy.py.start:106
YAPPI:        891x       0.002s /usr/lib/python2.7/threading.py._is_owned:226
YAPPI:        867x       0.002s /usr/lib/python2.7/threading.py._release_save:220
YAPPI:        353x       0.002s /home/boudewijn/local/lib/python2.7/site-packages/yappi.py.func_enumerator:72
YAPPI:         48x       0.001s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/conversion.py.define_meta_message:223
YAPPI:          1x       0.001s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/timeline.py.Timeline:14
YAPPI:          8x       0.001s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/dprint.py.dprint:595
YAPPI:          1x       0.001s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/script.py.<module>:2
YAPPI:          2x       0.001s /usr/lib/python2.7/sre_parse.py._parse:379
YAPPI:          8x       0.001s /usr/lib/python2.7/traceback.py.extract_stack:280
YAPPI:         29x       0.001s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/message.py.__init__:499
YAPPI:          1x       0.001s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/BitTornado/RawServer.py.listen_forever:129
YAPPI:          1x       0.001s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/community.py.<module>:9
YAPPI:        194x       0.001s /usr/lib/python2.7/sre_parse.py.__next:182
YAPPI:          1x       0.001s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/debugcommunity.py.<module>:1
YAPPI:          1x       0.001s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/lencoder.py.<module>:3
YAPPI:          3x       0.000s /usr/lib/python2.7/sre_compile.py._compile:32
YAPPI:        191x       0.000s /usr/lib/python2.7/sre_parse.py.get:201
YAPPI:         49x       0.000s /usr/lib/python2.7/linecache.py.checkcache:43
YAPPI:        185x       0.000s /usr/lib/python2.7/sre_parse.py.append:138
YAPPI:          4x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/dispersy.py._store:1991
YAPPI:          1x       0.000s /usr/lib/python2.7/encodings/hex_codec.py.<module>:8
YAPPI:          1x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/community.py.create_community:50
YAPPI:         16x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/BitTornado/SocketHandler.py.handle_events:455
YAPPI:        109x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/database.py.execute:149
YAPPI:         49x       0.000s /usr/lib/python2.7/linecache.py.getline:13
YAPPI:          5x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/dispersy.py._on_incoming_packets:1622
YAPPI:         42x       0.000s /usr/lib/python2.7/threading.py.acquire:121
YAPPI:         57x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/BitTornado/clock.py.get_time:16
YAPPI:          1x       0.000s /usr/lib/python2.7/sre_compile.py._compile_info:361
YAPPI:         23x       0.000s /usr/lib/python2.7/threading.py.set:385
YAPPI:          1x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/NATFirewall/guessip.py.get_my_wan_ip_linux:104
YAPPI:          1x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/database.py.__init__:19
YAPPI:         42x       0.000s /usr/lib/python2.7/threading.py.release:141
YAPPI:          1x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/timeline.py.authorize:237
YAPPI:          4x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/conversion.py._decode_message:1266
YAPPI:          5x       0.000s /home/boudewijn/svn.tribler.org/abc/branches/mainbranch/Tribler/Core/dispersy/member.py.__init__:116
"""
        pass

    def register(self):
        def register_func():
            container[0] += 1

        container = [0]
        register = self._dispersy.callback.register

        for _ in xrange(100000):
            register(register_func)

        while container[0] < 100000:
            yield 1.0

    def register_delay(self):
        def register_delay_func():
            container[0] += 1

        container = [0]
        register = self._dispersy.callback.register

        for _ in xrange(100000):
            register(register_delay_func, delay=1.0)

        while container[0] < 100000:
            yield 1.0

    def generator(self):
        def generator_func():
            for _ in xrange(10):
                yield 0.1
            container[0] += 1

        container = [0]
        register = self._dispersy.callback.register

        for _ in xrange(10000):
            register(generator_func)

        while container[0] < 10000:
            yield 1.0
