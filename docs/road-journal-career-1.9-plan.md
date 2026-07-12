# Road journal Career 1.9 activation

Current development publishes only delivery completion, official achievement
unlocks, and version 1 allowlisted profile snapshots. It does not publish
business, fleet, trailer, authority, inspection, route-history, or ownership
details beyond the current truck ownership status.

Career 1.9 activation requires a separate compatibility commit on that branch:

1. map each new field to a reliably persisted Career 1.9 model value;
2. add explicit client and server validators instead of passing save fragments;
3. add server feature gates and projections so inactive fields cannot reach a
   route, query, index, or rendered payload;
4. increment consent when the public disclosure changes and keep old consent
   inactive;
5. add migration/privacy tests before enabling any new event family;
6. activate labels and profile sections only after the corresponding publisher
   and privacy matrix pass.

No current-development code reads or displays the reserved future envelope.
