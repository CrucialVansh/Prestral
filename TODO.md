# TODO

## Backend
- [x] Replace UUID with session code
- [x] Separate presenter and viewer modes (no hotspots for presenters)
- [ ] Fix positioning of context boxes
- [ ] Fix layering order of context boxes (chat should be prioritised, unless mouse is hovering over context box)
- [ ] Investigate and fix weird bug with chat that forces a refresh to see text
- [ ] Improve slow load times (likely caused by the model being used)
- [ ] Add Google Drive compatibility for file import/export

## Frontend
- [x] Separate presenter and viewer UI states
- [x] Landing page with Host/Join tabs
- [x] Display session code for presenters
- [ ] Ensure context boxes position correctly relative to hotspots
- [ ] Implement proper z-index layering for chat vs context boxes
- [ ] Debug chat text rendering issue requiring refresh
- [ ] Optimize rendering performance for faster load times
- [ ] Add Google Drive integration UI

## Infrastructure
- [ ] Review session management (UUID vs session code)
- [ ] Optimize API response times
- [ ] Add Google Drive OAuth flow
