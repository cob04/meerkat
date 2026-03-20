# Meerkat

A meerkat stands on its hind legs, head on a swivel, scanning the horizon while the rest of the colony goes about its day. The moment something changes, it calls it out.

That is this project.

Meerkat watches your database for inventory changes and keeps your search index in sync. A drug gets dispensed, a shipment arrives, a batch expires. Meerkat spots it and updates the search index before anyone has to ask "is this still in stock?"

**The problem:** inventory records live in a database. Staff search for stock through a search index. The two drift apart. Search says "available," the shelf says otherwise.

**The fix:** Change Data Capture (CDC) streams every insert, update, and delete from the database into the search index in near-realtime. No polling. No scheduled rebuilds. No stale results.

Meerkat never blinks.
