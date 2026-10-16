# Architecture decisions

Short records of decisions that are not obvious from the code. Newest first.

## National and regional feeds (#37)

**GDACS client: `aio-georss-gdacs`.** Home Assistant's own `gdacs` integration uses this
maintained library, and it accepts the shared aiohttp session. The provider calls
`GdacsFeed.update()` directly and does not use the feed manager, because the manager reports
every entry as removed when a fetch fails. The library returns `OK_NO_DATA` for a document it
cannot parse, so that status counts as an outage, not as an empty feed. The requirement is a
lower bound (`>=0.10`, the version Home Assistant pins) so it cannot conflict with core.

**BoM products over FTP with `ftplib` in the executor.** JATWC tsunami, heatwave and UV
forecast products are published on `ftp://ftp.bom.gov.au/anon/gen/fwo/`. aiohttp cannot use
FTP, and an extra `aioftp` dependency is not justified for a few small files. Each refresh opens
one anonymous connection, lists only the needed name patterns (`NLST IDY68*`), and downloads
only the matching files. An empty listing means "not issued" (a confirmed all-clear). A
connection or listing failure raises `ProviderUnavailableError`.

**National data is kept out of `hazards`.** GDACS alerts, hotspots, heatwave, UV and tsunami
status are stored in their own `DisasterCoordinatorData` fields. Hazards drive counts, the
highest warning level, the emergency binary sensor, polling, map pins and the card. Regional
context or a satellite heat detection must not change those. The national provider sets
`provides_hazards = False`, so the coordinator skips its hazard fetch and it cannot count as a
healthy hazard feed when every real feed is down.

**`None` means undetermined.** Each national feed has its own `FeedCache` with a refresh
interval and a maximum stale age. A failed refresh returns the last good value until that age,
then `None`. The matching entity is unavailable while its value is `None`. An empty list or
`"none"` is a confirmed all-clear.

**Opt-in.** Every feed is off by default (options step `national_feeds`), so existing
entries make no new requests and get no new entities.
