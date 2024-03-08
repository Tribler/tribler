import socket
import struct
from asyncio import exceptions, tasks, trsock
from asyncio.log import logger

try:
    import _overlapped
except ImportError:
    _overlapped = None


NULL = 0
patch_applied = False


def apply_finish_accept_patch():  # pragma: no cover
    """
    The patch fixes the following issue with the IocpProactor._accept() method on Windows:

    OSError: [WinError 64] The specified network name is no longer available
      File "asyncio\windows_events.py", line 571, in accept_coro
        await future
      File "asyncio\windows_events.py", line 817, in _poll
        value = callback(transferred, key, ov)
      File "asyncio\windows_events.py", line 560, in finish_accept
        ov.getresult()
    OSError: [WinError 64] The specified network name is no longer available.

    See:
    * https://github.com/Tribler/tribler/issues/7759
    * https://github.com/python/cpython/issues/93821
    """

    global patch_applied
    if patch_applied:
        return

    from asyncio.proactor_events import BaseProactorEventLoop
    from asyncio.windows_events import IocpProactor

    BaseProactorEventLoop._start_serving = patched_proactor_event_loop_start_serving
    IocpProactor.accept = patched_iocp_proacor_accept

    patch_applied = True
    logger.info("Patched asyncio to fix accept() issues on Windows")


def patched_iocp_proacor_accept(self, listener, *, _overlapped=_overlapped):
    self._register_with_iocp(listener)
    conn = self._get_accept_socket(listener.family)
    ov = _overlapped.Overlapped(NULL)
    ov.AcceptEx(listener.fileno(), conn.fileno())

    def finish_accept(trans, key, ov):
        # ov.getresult()
        # start of the patched code
        try:
            ov.getresult()
        except OSError as exc:
            if exc.winerror in (_overlapped.ERROR_NETNAME_DELETED,
                                _overlapped.ERROR_OPERATION_ABORTED):
                logger.debug("Connection reset error occurred, continuing to accept connections")
                conn.close()
                raise ConnectionResetError(*exc.args)
            raise
        # end of the patched code

        # Use SO_UPDATE_ACCEPT_CONTEXT so getsockname() etc work.
        buf = struct.pack('@P', listener.fileno())
        conn.setsockopt(socket.SOL_SOCKET,
                        _overlapped.SO_UPDATE_ACCEPT_CONTEXT, buf)
        conn.settimeout(listener.gettimeout())
        return conn, conn.getpeername()

    async def accept_coro(future, conn):
        # Coroutine closing the accept socket if the future is cancelled
        try:
            await future
        except exceptions.CancelledError:
            conn.close()
            raise

    future = self._register(ov, listener, finish_accept)
    coro = accept_coro(future, conn)
    tasks.ensure_future(coro, loop=self._loop)
    return future


def patched_proactor_event_loop_start_serving(self, protocol_factory, sock,
                                              sslcontext=None, server=None, backlog=100,
                                              ssl_handshake_timeout=None,
                                              ssl_shutdown_timeout=None):  # pragma: no cover

    def loop(f=None):
        try:
            if f is not None:
                conn, addr = f.result()
                if self._debug:
                    logger.debug("%r got a new connection from %r: %r",
                                 server, addr, conn)
                protocol = protocol_factory()
                if sslcontext is not None:
                    self._make_ssl_transport(
                        conn, protocol, sslcontext, server_side=True,
                        extra={'peername': addr}, server=server,
                        ssl_handshake_timeout=ssl_handshake_timeout,
                        ssl_shutdown_timeout=ssl_shutdown_timeout)
                else:
                    self._make_socket_transport(
                        conn, protocol,
                        extra={'peername': addr}, server=server)
            if self.is_closed():
                return
            f = self._proactor.accept(sock)

        # start of the patched code
        except ConnectionResetError:
            logger.debug("Connection reset error occurred, continuing to accept connections")
            self.call_soon(loop)
        # end of the patched code

        except OSError as exc:
            if sock.fileno() != -1:
                self.call_exception_handler({
                    'message': 'Accept failed on a socket',
                    'exception': exc,
                    'socket': trsock.TransportSocket(sock),
                })
                sock.close()
            elif self._debug:
                logger.debug("Accept failed on socket %r",
                             sock, exc_info=True)
        except exceptions.CancelledError:
            sock.close()
        else:
            self._accept_futures[sock.fileno()] = f
            f.add_done_callback(loop)

    self.call_soon(loop)
