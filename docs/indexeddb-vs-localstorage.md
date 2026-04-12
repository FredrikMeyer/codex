# IndexedDB vs localStorage

## Storage Limits

|                       | localStorage      | IndexedDB                                                 |
|-----------------------|-------------------|-----------------------------------------------------------|
| Limit                 | ~5 MiB per origin | Up to ~60% of disk (Chrome/Edge/Safari), 10 GiB (Firefox) |
| Check available space | Not available     | `navigator.storage.estimate()`                            |

Source: [MDN — Storage quotas and eviction criteria](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)

## Performance

- **localStorage is synchronous** and blocks the main thread on every read/write.
- **IndexedDB is fully asynchronous** — operations are non-blocking, safe for large datasets without UI jank.
- IndexedDB supports indexes for fast property-based lookups.

Source: [web.dev — Storage for the Web](https://web.dev/articles/storage-for-the-web)

> _"LocalStorage should be avoided because it is synchronous and will block the main thread."_ — web.dev

## API

- **localStorage**: Synchronous (`localStorage.setItem(key, value)`).
- **IndexedDB**: Async, event-based natively (verbose); commonly wrapped with the [`idb`](https://github.com/jakearchibald/idb) library for a clean Promise API. Available in Web Workers and Service Workers — localStorage is not.

Source: [MDN — IndexedDB API](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)

## Data Types

- **localStorage**: Strings only — objects require manual `JSON.stringify` / `JSON.parse`.
- **IndexedDB**: Any type supported by the Structured Clone Algorithm: objects, arrays, `Date`, `Blob`, `File`, `ArrayBuffer`, `Map`, `Set`, typed arrays. No serialisation step needed.

Source: [MDN — Structured clone algorithm](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Structured_clone_algorithm)

## Transactions

- **localStorage**: No transactions. Concurrent writes from multiple tabs can silently overwrite each other.
- **IndexedDB**: Full transaction model — `readonly`, `readwrite`, and `versionchange` modes. Transactions auto-commit when no more requests are queued, or abort on error.

Source: [web.dev — IndexedDB guide](https://web.dev/articles/indexeddb)

## Private Browsing / Incognito

Both APIs are available in private/incognito mode, but all data is wiped when the session ends. localStorage in private mode behaves like `sessionStorage` (cleared on tab close). IndexedDB quotas may also be lower in private mode.

Source: [MDN — Web Storage API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API)

## When to Use Each

**localStorage** is fine for:
- Tiny amounts of string-ish data (user preferences, feature flags, theme)
- Data comfortably within 5 MB
- Simple, synchronous reads at startup

**IndexedDB** is the right choice for:
- Structured data (event logs, cached API responses)
- Datasets exceeding a few MB
- Offline / Service Worker integration (PWAs)
- Concurrent-safe writes across tabs
- Avoiding main thread blocking
- Binary data (blobs, files)

## Relevance to This Project

`storage.js` currently wraps localStorage. The abstraction already isolates the storage layer from `app.js`, making an IndexedDB migration feasible without touching application logic. The main benefits for this app would be: larger quota for growing event logs, async non-blocking writes, and more reliable behaviour in private browsing.

## Sources

1. [MDN — IndexedDB API](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)
2. [MDN — Web Storage API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API)
3. [MDN — Storage quotas and eviction criteria](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
4. [web.dev — Storage for the Web](https://web.dev/articles/storage-for-the-web)
5. [web.dev — IndexedDB guide](https://web.dev/articles/indexeddb)
