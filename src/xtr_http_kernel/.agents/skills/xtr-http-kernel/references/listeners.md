# The listeners the bundle registers

Which ones join depends on what is installed and active. None of them needs to be listed: the
bundle registers them.

| Listener | Events | Active when | Does |
| --- | --- | --- | --- |
| `RequestIdListener` | `RequestEvent`, `ResponseEvent` | always | keeps a trusted incoming id or mints a `uuid4().hex`, puts it on `request.state.request_id`, binds it to the log context when logging is around, and echoes it on the response under `request_id_header` |
| `DisallowRobotsIndexingListener` | `ResponseEvent` | always | stamps `X-Robots-Tag: noindex` on every response, when `disallow_search_indexing` turns it on |
| `LogUnitListener` | `RequestEvent`, `TerminateEvent` | logging bundle active | opens a logging unit of work per request and closes it once all was sent |
| `ErrorLoggingListener` | `ExceptionEvent` | logging bundle active | writes every uncaught exception to `log_channel`, at `error` below a 500 status and `critical` otherwise, leaving the response to whoever answers it |
| `RateLimitHeadersListener` | `ResponseEvent` | rate limiter bundle active | writes the `X-RateLimit-*` headers of the limit that speaks for the response, and makes the response private |

The two logging listeners open and close the unit of work outside everything else, so every
record made while handling carries the request's id. The request id settles right after the unit
opens, for the same reason.

What this means for application code:

- Read the current id from `request.state.request_id`, or from the response's
  `request_id_header`. Do not mint your own.
- An uncaught exception is already logged with the request that caused it. An
  `ExceptionEvent` listener of your own should turn the failure into a response, not log it
  again.
- To keep every page out of a search index, set `disallow_search_indexing=True` rather than
  writing a `ResponseEvent` listener.
- To stop trusting an inbound id (a public edge), set `trust_request_id=False`.
