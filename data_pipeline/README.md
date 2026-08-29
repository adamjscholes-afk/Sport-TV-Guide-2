# Free Sport TV Guide data pipeline

The pipeline builds a clean 72-hour sports-only guide from public/open EPG sources.

## Sources

1. Freeview-EPG: https://github.com/dp247/Freeview-EPG
2. Rytec UK sources: https://github.com/oe-alliance/EPGImport-Sources/blob/main/rytec.sources.xml

Initial adapters live in `scripts/`. The pipeline is deliberately source-independent: each adapter produces the same normalised programme shape, after which channel filtering, sports classification, deduplication and validation are applied.

## Output

`data/guide.json` contains the next 72 hours of normalised listings. All timestamps are UTC; the app converts them to Europe/Zurich by default.

## Reliability rules

- Never publish an empty or obviously truncated source.
- Keep the last known-good output if a source fails.
- Use multiple mirrors where available.
- Record source health in `data/health.json`.
- Keep parsers isolated so a change in one source cannot break the others.

## Next adapters

Add targeted adapters for missing premium/streaming destinations only after measuring the coverage of the open feeds. Do not scrape a site unless its public schedule is legally suitable for republication.