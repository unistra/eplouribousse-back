# Changelog

## Next release
 
- 🔧 Refactor Sentry config

## 1.0.2 - 07-01-2026

- 🐛 Fix exclusion reasons not being translated at project initialization
- 📝 Remove date from email signatures

## 1.0.1 - 12-12-2025

- ✨ Update resource exclusion logic: resources are now also excluded if all their collections are excluded (#122)
- 📊 Refactor dashboard data, keys are no more lazy translated, computed_at key is only provided when data are cached (
  #141)
- 🐛 Fix publication_history and numbering not imported from CSV (#131, #172)
- ⬆️ Django 4.2.27, upgrade dependencies
- 🔒️ Add tenant id to cache keys
- 🔊 Record an ActionLog when adding or removing invitations and when creating a user account.
- ✨ URLs in emails now redirect directly to the modal where the user must perform an action on the project.
- 🐛 Fix various bugs and typos in emails

## 1.0.0 - 02-12-2025

- 🎉 Initial release
