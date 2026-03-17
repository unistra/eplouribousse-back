# Changelog

## 1.0.9 - 17-03-2026

- 🩹 Fix collections displayed in "main_collection" & "participating_collections" for resulting PDF

## 1.0.8 - 04-03-2026

- ⬆️ Django 5.2.12
- 🐛 Add library name to report (di/eplouribousse/eplouribousse#216)
- ✉ Send email to controller (di/eplouribousse/eplouribousse#212)

## 1.0.7 - 12-02-2026

- 🌐 Fix typos
- 🐛 Change Resource title max_length to 2048 chars

## 1.0.6 - 05-02-2026

- ⬆️ Django 5.2.11

## 1.0.5 - 03-02-2026

- ⬆️ Django 5.2.10
- 🗑️ Remove and update configuration files (PAAS deployment)
- 📧 Update contact form email template
- 🔊 Refactor logging of user log in

## 1.0.4 - 20-01-2026

- 📊 Exclude single collections and single collection resources from all dashboard metrics via a shared helper/mixin
- 📧 Improve email notifications performances by opening single SMTP connections per email batch
- 👷 Improve CI/CD Docker image build
- 🔧 Refactor Saml2 configuration

## 1.0.3 - 13-01-2026

- 🔧 Refactor Sentry configuration

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
