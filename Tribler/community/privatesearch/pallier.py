from Crypto.Random.random import StrongRandom
from Crypto.Util.number import GCD, bytes_to_long, long_to_bytes, inverse
from Crypto.PublicKey import RSA

#using same variable names as implementation by Zeki
def pallier_init(rsa_key):
    key_n = rsa_key.key.n
    key_n2 = pow(key_n, 2)
    
    key_g = key_n + 1
    
    #LCM from https://github.com/kmcneelyshaw/pycrypto/commit/98c22cc691c1840db380ad04c22169721a946b50
    x = rsa_key.key.p - 1
    y = rsa_key.key.q - 1
    if y > x:
        x, y = y, x
    
    key_lambda = (x / GCD(x, y)) * y
        
    key_decryption = pow(key_g, key_lambda, key_n2)
    key_decryption = (key_decryption - 1) / key_n
    key_decryption = inverse(key_decryption, key_n)
    
    return key_n, key_n2, key_g, key_lambda, key_decryption

def pallier_encrypt(element, g, n, n2):
    assert element in [0, 1], element
    
    while True:
        r = StrongRandom().randint(1, n)
        if GCD(r, n) == 1: break
    
    #key_g < n2, so no need for modulo
    t1 = g if element else 1l
    t2 = pow(r, n, n2)
    
    t1 = t1 * t2
    cipher = t1 % n2
    return cipher

def pallier_decrypt(cipher, n, n2, key_lambda, key_decryption):
    t1 = pow(cipher, key_lambda, n2)
    t1 = (t1 - 1) / n
    
    value = t1 * key_decryption
    value = value % n
    return value

def pallier_multiply(cipher, times,  n2):
    return pow(cipher, times, n2)

def pallier_add(cipher1, cipher2, n2):
    return (cipher1 * cipher2) % n2

if __name__ == "__main__":
    #lets check if this pallier thing works
    key = RSA.generate(1024)
    key_n, key_n2, key_g, key_lambda, key_decryption = pallier_init(key)
    
    encrypted0 = pallier_encrypt(0l, key_g, key_n, key_n2)
    encrypted1 = pallier_encrypt(1l, key_g, key_n, key_n2)
    
    test = pallier_decrypt(encrypted0, key_n, key_n2, key_lambda, key_decryption)
    assert test == 0l, test
             
    test = pallier_decrypt(encrypted1, key_n, key_n2, key_lambda, key_decryption)
    assert test == 1l, test
    
    encrypted2 = pallier_add(encrypted1, encrypted1, key_n2)
    test = pallier_decrypt(encrypted2, key_n, key_n2, key_lambda, key_decryption)
    assert test == 2l, test
    
    encrypted4 = pallier_add(encrypted2, encrypted2, key_n2)
    test = pallier_decrypt(encrypted4, key_n, key_n2, key_lambda, key_decryption)
    assert test == 4l, test
    
    encrypted1_ = pallier_add(1, encrypted1, key_n2)
    test = pallier_decrypt(encrypted1_, key_n, key_n2, key_lambda, key_decryption)
    assert test == 1l, test
    
    encrypted0_ = pallier_multiply(encrypted0, 10, key_n2)
    test = pallier_decrypt(encrypted0_, key_n, key_n2, key_lambda, key_decryption)
    assert test == 0l, test
    
    encrypted10 = pallier_multiply(encrypted1, 10, key_n2)
    test = pallier_decrypt(encrypted10, key_n, key_n2, key_lambda, key_decryption)
    assert test == 10l, test
        
    #bytes_to_long check
    test = bytes_to_long(long_to_bytes(key_n, 128))
    assert test == key_n, test
    
    test = pallier_decrypt(bytes_to_long(long_to_bytes(encrypted0, 128)), key_n, key_n2, key_lambda, key_decryption)
    assert test == 0l, test
    
    test = pallier_decrypt(bytes_to_long(long_to_bytes(encrypted1, 128)), key_n, key_n2, key_lambda, key_decryption)
    assert test == 1l, test
    
    test = pallier_decrypt(bytes_to_long(long_to_bytes(encrypted2, 128)), key_n, key_n2, key_lambda, key_decryption)
    assert test == 2l, test
    
    test = pallier_decrypt(bytes_to_long(long_to_bytes(encrypted4, 128)), key_n, key_n2, key_lambda, key_decryption)
    assert test == 4l, test
    
    test = pallier_decrypt(bytes_to_long(long_to_bytes(encrypted10, 128)), key_n, key_n2, key_lambda, key_decryption)
    assert test == 10l, test