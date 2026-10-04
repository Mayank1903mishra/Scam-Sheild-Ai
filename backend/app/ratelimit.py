from slowapi import Limiter
from slowapi.util import get_remote_address

# key_style="function" keys limits by endpoint function name, so path
# parameters (e.g. /scans/{scan_id}/feedback) cannot create a fresh
# rate-limit bucket per id.
limiter = Limiter(key_func=get_remote_address, key_style="function")
