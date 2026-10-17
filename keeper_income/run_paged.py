"""Range correction; same historical window, no access bypass or profit filters."""
import base64,copy,hashlib,json,zlib
import census as c
ENC='eNrNl72u5DYMhd9l6luIpESJ+yqZFBR/2jRbBFjsu4cTbJPsBPDkrmfGjQHDkL8jnXMsfbv89u16cf2q18cy?'
# Filled with exact base64 at build time; fail closed if not the recorded cache.
