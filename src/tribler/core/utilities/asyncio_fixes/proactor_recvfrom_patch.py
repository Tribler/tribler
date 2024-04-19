from asyncio.log import logger

try:
    import _overlapped
except ImportError:
    _overlapped = None


NULL = 0

ERROR_PORT_UNREACHABLE = 1234  # _overlapped.ERROR_PORT_UNREACHABLE, available in Python >= 3.11
ERROR_NETNAME_DELETED = 64
ERROR_OPERATION_ABORTED = 995

patch_applied = False


def apply_proactor_recvfrom_patch():  # pragma: no cover
    global patch_applied  # pylint: disable=global-statement
    if patch_applied:
        return

    from asyncio import IocpProactor  # pylint: disable=import-outside-toplevel

    IocpProactor.recvfrom = patched_recvfrom

    patch_applied = True
    logger.info("Patched IocpProactor.recvfrom to handle ERROR_PORT_UNREACHABLE")


# pylint: disable=protected-access


def patched_recvfrom(self, conn, nbytes, flags=0):
    self._register_with_iocp(conn)
    ov = _overlapped.Overlapped(NULL)
    try:
        ov.WSARecvFrom(conn.fileno(), nbytes, flags)
    except BrokenPipeError:
        return self._result((b'', None))

    def finish_recvfrom(trans, key, ov, error_class=OSError):  # pylint: disable=unused-argument
        try:
            return ov.getresult()
        except error_class as exc:
            if exc.winerror in (ERROR_NETNAME_DELETED, ERROR_OPERATION_ABORTED):
                raise ConnectionResetError(*exc.args)  # pylint: disable=raise-missing-from

            # ******************** START OF THE PATCH ********************
            # WSARecvFrom will report ERROR_PORT_UNREACHABLE when the same
            # socket was used to send to an address that is not listening.
            if exc.winerror == ERROR_PORT_UNREACHABLE:
                return b'', None  # ignore the error
            # ******************** END OF THE PATCH **********************

            raise

    return self._register(ov, conn, finish_recvfrom)
