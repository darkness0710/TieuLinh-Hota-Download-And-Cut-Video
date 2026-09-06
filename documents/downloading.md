# Downloading

`Start.cmd` route 1 asks yt-dlp for 1080p60 H.264 plus AAC and warns if what
arrives is not 1920x1080 — every overlay coordinate in `config.py` assumes
1080p, so a 720p file would produce a confidently wrong cut.

Two external programs make this fast, and `Install.cmd` installs both per-user
with no administrator rights. Neither is required: without them the download
still works, just slowly.

| | why | without it |
|---|---|---|
| **deno** | yt-dlp runs YouTube's own JavaScript with it, to solve the `n` parameter of a stream URL | ~165 KB/s |
| **aria2c** | holds several connections open for one download | ~1 MB/s |

## The n parameter

Without a JavaScript runtime, yt-dlp cannot solve `n`, falls back to a player
client whose URLs carry no solved value, and googlevideo answers with about
10 MiB per request and then stalls for the best part of a minute. Measured on a
6.16 GiB VOD: **165 KB/s against 11 MiB/s** — ten hours instead of ten minutes.
Nothing errors. The download simply runs fifty times slower.

deno is the runtime to install: yt-dlp enables only deno by default, only deno
and bun have a solver script vendored inside yt-dlp, and node is rejected below
v22. `tlh/jsruntime.py` finds it.

## One connection is capped

googlevideo serves a single connection at about **1 MiB/s** — roughly twice
playback rate, and dead steady, so it is a cap rather than congestion. The cap
is per connection: measured with plain range requests on the same line,

| connections | throughput |
|---|---|
| 1 | 0.97 MiB/s |
| 8 | 7.67 MiB/s |
| 16 | 11.5 MiB/s (the line itself) |

A progressive URL cannot be split, so there are two ways to hold more than one
slot, and `tlh/fetch.py` prefers the first:

1. **aria2c** opens `ARIA2_CONNECTIONS` connections once and keeps them, each
   streaming a large contiguous range: eight for the whole download.
2. **yt-dlp's fragment pool** (`formats=dashy`) asks the extractor for the
   DASH-shaped view of the same stream, whose fragments are range requests, and
   fetches `PARALLEL` of them at a time. It works — and opens a new connection
   per 10 MiB fragment, about 600 for one VOD.

That churn is why aria2c is preferred. After a quarter of an hour of roughly a
connection a second, a home line stopped answering new ones: `[WinError 10060]
A connection attempt failed`, SYNs unanswered rather than refused, which is
what a CGNAT session limit or an anti-abuse filter looks like. Measured
mid-download, four fragment workers managed 0.50 MiB/s between them while a
brand new connection got 0.96 on its own — the fleet was sitting in connect
timeouts. `PARALLEL` is 4 for that reason, and `socket_timeout` is 15 s so a
stuck worker recovers in half the time.

Sixteen connections is not the answer on such a line: aria2c opened all
sixteen and transferred nothing at all, the same wall reached from the other
side.

## Video and audio are separate downloads

YouTube keeps them apart, so one VOD is two downloads and the header says so:

```
  Size        6.16 GiB
  Streams     video 299.mp4 5.97 GiB, then audio 140.m4a 194 MiB
```

googlevideo paces each stream at about twice **its own** bitrate, so the audio
is not slower in any meaningful sense — it has 31x less data and gets 31x less
bandwidth, and both streams take the same wall-clock time. Measured: video
4071 kbps at 7.51 MiB/s in 13:33, audio 129 kbps at 244 KiB/s in 13:20. The
consequence is that **half the download time goes on 3% of the bytes**, and
that picking a lower-bitrate audio format saves nothing: it would be paced
proportionally slower and take just as long.

## Interrupted downloads

Leftovers in `input/` are what a resume picks up from, and each downloader
leaves its own kind: `.part`, `.ytdl`, `.part-FragNN` (fragment pool) and
`.part.aria2` (aria2c's control file). `fetch.is_partial()` knows all of them
— it has to, because `already_have()` would otherwise hand a 10 MiB fragment
back as a finished video and the pipeline would sit down to cut it.

One leftover carries no marker at all: `NAME.f299.mp4`, one half of the pair
downloaded whole and waiting for the other. It ends in `.mp4`, so before it
was added to `is_partial()` all three readers of `input/` took it for a
finished video — `already_have()` returned it and the audio was never
fetched again, `run.py` cut it, and the web page offered it with a Run button.
Measured on the leftovers of a real failure: 7.33 GiB of silent video, called
finished by all three.

A failed URL does not fall back on the library either. `run.py` given `--url`
processes what it downloaded and nothing else, including when that is nothing:
otherwise a link dying at 87% starts an hour of work on whatever happens to be
sitting in `input/`.

Resume does not cross a change of downloader: aria2c cannot continue a
fragment-pool `.part`, and starts that stream again.

## The route going away

A download is restarted `fetch.ATTEMPTS` times, thirty seconds apart, before
it is called a failure. Measured: an audio stream an hour in died with all
eight of its connections reporting `unreachable host` in the same second,
which is a route that went away rather than a server saying no — aria2c's own
`--max-tries` cannot help with that, and it says as much on the way out:
*aria2 will resume download if the transfer is restarted.*

A restart costs nothing. Everything on disk is kept, and it re-signs the
googlevideo URLs, which expire anyway (`expire=` in the query is a few hours
out).

Worth checking when this happens often: whether the connection is leaving over
IPv6. The `ip=` field in the failing URL is the address YouTube saw, and if it
is a v6 address on a tunnel or a VPN, that is the leg that keeps dropping.

## Bot checks

Enough requests from one address and YouTube answers `HTTP 429` and
`Sign in to confirm you're not a bot`, at which point extraction fails before
any download starts. It clears on its own, in minutes to hours. A VPN whose
exit address is not rate-limited also clears it immediately — and on one
measured evening, moving to a clean route was the difference between 0.67 and
7.7 MiB/s on the same line with the same code.

## A missing fragment is worse than a failure

yt-dlp's default is to skip a fragment it cannot fetch and carry on. These
fragments are byte ranges of one continuous mp4, appended in order, so a
skipped one does not leave a gap in the video: every byte after it lands at the
wrong offset and the file is broken from there to the end, while still arriving
looking like a finished download. `skip_unavailable_fragments` is therefore off
— the download aborts instead, and the pieces already on disk are kept so
running it again resumes.

Worth checking after a long download: the stream file should be exactly the
size the header promised.
