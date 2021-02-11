

def is_bencoded(x: bytes) -> bool:
    """
    Returns True is x appears to be valid bencoded byte string.

    For better performance does not check that strings are in valid encoding.
    """
    return default_checker.check(x)


class BencodeChecker:
    def __init__(self):
        self.check_func = {
            ord('l'): self.check_list,
            ord('i'): self.check_int,
            ord('0'): self.check_string,
            ord('1'): self.check_string,
            ord('2'): self.check_string,
            ord('3'): self.check_string,
            ord('4'): self.check_string,
            ord('5'): self.check_string,
            ord('6'): self.check_string,
            ord('7'): self.check_string,
            ord('8'): self.check_string,
            ord('9'): self.check_string,
            ord('d'): self.check_dict,
        }

    def check(self, x: bytes) -> bool:
        if not isinstance(x, bytes):
            raise ValueError('Value should be of bytes type. Got: %s'
                             % type(x).__name__)

        try:
            prefix = x[0]
            pos = self.check_func[prefix](x, 0)
        except (IndexError, KeyError, TypeError, ValueError):
            return False

        if pos != len(x):
            # truncated string or bytes after the end of bencoded string
            return False

        return True

    @staticmethod
    def check_int(x: bytes, pos: int,
                  ZERO=ord('0'), MINUS=ord('-')) -> int:
        pos += 1
        end = x.index(b'e', pos)

        if x[pos] == MINUS:
            if x[pos + 1] == ZERO:
                raise ValueError
        elif x[pos] == ZERO and end != pos + 1:
            raise ValueError

        return end + 1

    @staticmethod
    def check_string(x: bytes, pos: int,
                     ZERO=ord('0')) -> int:
        colon = x.index(b':', pos)
        if x[pos] == ZERO and colon != pos + 1:
            raise ValueError

        n = int(x[pos:colon])
        return colon + 1 + n

    def check_list(self, x: bytes, pos: int,
                   END=ord('e')) -> int:
        pos += 1

        while x[pos] != END:
            prefix = x[pos]
            pos = self.check_func[prefix](x, pos)

        return pos + 1

    def check_dict(self, x: bytes, pos: int,
                   END=ord('e')) -> int:
        pos += 1

        while x[pos] != END:
            pos = self.check_string(x, pos)
            prefix = x[pos]
            pos = self.check_func[prefix](x, pos)

        return pos + 1


default_checker = BencodeChecker()
