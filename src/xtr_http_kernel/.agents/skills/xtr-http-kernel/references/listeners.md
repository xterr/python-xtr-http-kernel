# The listeners the bundle registers

Which ones join depends on what is installed and active. None of them needs to be listed: the
bundle registers them.

| Listener | Events | Active when | Does |
| --- | --- | --- | --- |
| `RequestIdListener` | `RequestEvent`, `ResponseEvent` | always | mints a `uuid4().hex` — or keeps a well-formed incoming id, where `trust_request_id` says to — puts it on `request.state.request_id`, binds it to the log context when logging is around, and echoes it on the response under `request_id_header` |
| `DisallowRobotsIndexingListener` | `ResponseEvent` | always | stamps `X-Robots-Tag: noindex` on every response, when `disallow_search_indexing` turns it on |
| `ErrorLoggingListener` | `ExceptionEvent` | logging bundle active | writes every uncaught exception to `log_channel`, at `info` for a cancellation, an interrupt or an exit and for a status below 500, `critical` otherwise, leaving the response to whoever answers it |
| `RateLimitHeadersListener` | `ResponseEvent` | rate limiter bundle active | writes the `X-RateLimit-*` headers of the limit that speaks for the response, and makes the response private |

The per-request logging unit is not a listener: the logging bundle's `LogUnitParticipant` opens
it with the request's unit of work and closes it with that unit, so every record made while
handling carries the request's id.

What this means for application code:

- Read the current id from `request.state.request_id`, or from the response's
  `request_id_header`. Do not mint your own.
- An uncaught exception is already logged with the request that caused it. An
  `ExceptionEvent` listener of your own should turn the failure into a response, not log it
  again.
- To keep every page out of a search index, set `disallow_search_indexing=True` rather than
  writing a `ResponseEvent` listener.
- An inbound id is not trusted: every request gets a fresh one. Set `trust_request_id=True`
  only behind a proxy you control that sets the header itself and strips the caller's.
