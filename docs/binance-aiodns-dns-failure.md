# Binance download blocked by `aiodns` DNS resolution

Date: 2026-04-22

## Symptom

`.\.venv\Scripts\python.exe prepare.py` fails while loading Binance markets:

`ClientConnectorDNSError: Cannot connect to host api.binance.com:443 ssl:default [Could not contact DNS servers]`

## Attempts

1. Re-ran `prepare.py` after initial failure.
2. Verified OS/network path separately:
   - `Resolve-DnsName api.binance.com` returned `198.18.0.251`
   - `Invoke-WebRequest https://api.binance.com/api/v3/exchangeInfo` returned `200`
3. Re-ran `prepare.py` after connectivity check; same failure.
4. Isolated Python network stacks:
   - `requests.get(...)` from the same venv returned `200`
   - `aiodns.DNSResolver().gethostbyname('api.binance.com', 0)` failed with `DNSError: Could not contact DNS servers`
   - plain `aiohttp.ClientSession()` failed with the same DNS error
   - `aiohttp.ClientSession(connector=aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver()))` succeeded with `200`

## Evidence

- OS resolver works.
- Synchronous Python HTTP works.
- `aiodns` resolver fails in isolation.
- `aiohttp` succeeds when forced onto `ThreadedResolver`, which bypasses `aiodns`/`pycares`.

## Hypothesis

`aiodns`/`pycares` is incompatible with the current Windows DNS environment, while the system resolver is fine. Because `aiohttp` auto-selects the async resolver when `aiodns` is installed, Freqtrade/CCXT inherits the broken path.

## Next step

Remove `aiodns` (and likely `pycares`) from the virtual environment so `aiohttp` falls back to the working threaded/system resolver, then retry `prepare.py`.
