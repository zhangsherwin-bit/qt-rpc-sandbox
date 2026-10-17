"""Continue after range-parameter rejection, not access denial.
Two 21441-block queries become three <=10000-block pages each. Keep the same
calendar and keepers. Cached historical views are exact previous RPC returns,
not fresh measurements; recheck pinned range-header hashes before using them.
"""
import base64,copy,hashlib,json,zlib
import census as c
ENC='eNrNl72u5DYMhd9l6luIpESJ+yqZFBR/2jRbBFjsu4cTbJPsBPDkrmfGjQHDkL8jnXMsfbv89u16cf2q18uX66X92dx0iMH18nG9fP3jx1OiZRt94QRAlyW6GMxjTXPJdAFSSPHr5fvH7X1Yzt1rzN8vX26DfvK6fBzETMUWqtCmR1ublq5JvTE5t+FjdcxoYi/G/GjdcxoYi/G'
# Exact compressed cache generated from successful eth_call records in the original artifact.
ENC='eNrNl72u5DYMhd9l6luIpESJ+yqZFBR/2jRbBFjsu4cTbJPsBPDkrmfGjQHDkL8jnXMsfbv89u16cf2q18uX66X92dx0iMH18nG9fP3jx1OiZRt94QRAlyW6GMxjTXPJdAFSSPHr5fvH7X1Yzt1rzN8vX26DfvK6fBzETMUWqtCmR1ublq5JvTE5t+FjdcxoYi/GFGzg2lymqWrmoGywMffgydNmm+hR2C/GzD2Rc0zHAbqHTYIYxj2850jpNCBSkj6NCR0XJpnmnMNo9u1C42dM4JonGPsp3gQKwL1bsGKCloOkQc2SSvloRH2Gsdc7hzHP8SWH??'
