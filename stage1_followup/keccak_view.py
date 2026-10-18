"""Small dependency-free Keccak-256 for public ABI selectors/code fingerprints.
Not for signing, secret handling or production cryptography. Tested against
known empty, abc and ERC20-selector vectors by the companion tests.
"""
MASK = (1 << 64) - 1
ROT = ((0,36,3,41,18),(1,44,10,45,2),(62,6,43,15,61),
       (28,55,25,21,56),(27,20,39,8,14))
RC = (0x1,0x8082,0x800000000000808a,0x8000000080008000,
      0x808b,0x80000001,0x8000000080008081,0x8000000000008009,
      0x8a,0x88,0x80008009,0x8000000a,0x8000808b,0x800000000000008b,
      0x8000000000008089,0x8000000000008003,0x8000000000008002,
      0x8000000000000080,0x800a,0x800000008000000a,
      0x8000000080008081,0x8000000000008080,0x80000001,0x8000000080008008)

def rol(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & MASK if n else x

def permute(a: list[int]) -> None:
    for rc in RC:
        c = [a[x] ^ a[x+5] ^ a[x+10] ^ a[x+15] ^ a[x+20] for x in range(5)]
        d = [c[(x-1)%5] ^ rol(c[(x+1)%5],1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                a[x+5*y] ^= d[x]
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y+5*((2*x+3*y)%5)] = rol(a[x+5*y],ROT[x][y])
        for x in range(5):
            for y in range(5):
                a[x+5*y] = b[x+5*y] ^ ((~b[(x+1)%5+5*y]) & b[(x+2)%5+5*y])
        a[0] ^= rc

def keccak256(data: bytes) -> bytes:
    rate = 136
    padded = bytearray(data)
    padding = rate - len(padded) % rate
    padded += bytes([0x81]) if padding == 1 else b'\x01' + b'\x00'*(padding-2) + b'\x80'
    state = [0]*25
    for k in range(0,len(padded),rate):
        block = padded[k:k+rate]
        for j in range(rate//8):
            state[j] ^= int.from_bytes(block[8*j:8*j+8], 'little')
        permute(state)
    return b''.join(x.to_bytes(8,'little') for x in state)[:32]

def selector(signature: str) -> str:
    return '0x' + keccak256(signature.encode('ascii'))[:4].hex()
