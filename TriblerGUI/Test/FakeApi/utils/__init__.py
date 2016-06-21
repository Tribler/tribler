import random


def get_random_hex_string(len):
   return ''.join([random.choice('0123456789abcdef') for x in range(len)])
