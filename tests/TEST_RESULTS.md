# CineTagIt – Pytest Results Summary

> **Run date:** 2026-03-05  
> **Python:** 3.14.3  
> **pytest:** 9.0.2  
> **pytest-cov:** 7.0.0

---

## Overall Result

| Metric | Value |
|--------|-------|
| **Status** | ✅ All tests passed |
| **Total tests** | 30 |
| **Passed** | 30 |
| **Failed** | 0 |
| **Errors** | 0 |
| **Duration** | ~3.3 s |

---

## Tests by Module

### `tests/routes/test_auth.py` (6 tests)

| Test | Result |
|------|--------|
| `test_registration_flow` | ✅ PASSED |
| `test_registration_honeypot` | ✅ PASSED |
| `test_login_logout_flow` | ✅ PASSED |
| `test_login_invalid_credentials` | ✅ PASSED |
| `test_email_confirmation` | ✅ PASSED |
| `test_password_reset_flow` | ✅ PASSED |

### `tests/services/test_image_service.py` (10 tests)

| Test | Result |
|------|--------|
| `test_get_image_base_path` | ✅ PASSED |
| `test_get_image_base_path_creates_directory` | ✅ PASSED |
| `test_get_tmdb_image_base_url` | ✅ PASSED |
| `test_get_tmdb_image_url` | ✅ PASSED |
| `test_get_image_url` | ✅ PASSED |
| `test_fetch_image` | ✅ PASSED |
| `test_resize_image` | ✅ PASSED |
| `test_ensure_image_exists_already_present` | ✅ PASSED |
| `test_ensure_image_exists_triggers_resize` | ✅ PASSED |
| `test_ensure_image_exists_triggers_fetch_and_resize` | ✅ PASSED |

### `tests/services/test_movie_deletion.py` (1 test)

| Test | Result |
|------|--------|
| `test_movie_deletion_on_404` | ✅ PASSED |

### `tests/services/test_movie_service.py` (4 tests)

| Test | Result |
|------|--------|
| `test_get_region_infos` | ✅ PASSED |
| `test_get_lang_infos` | ✅ PASSED |
| `test_get_region_infos_empty` | ✅ PASSED |
| `test_get_lang_infos_empty` | ✅ PASSED |

### `tests/services/test_tmdb_service.py` (6 tests)

| Test | Result |
|------|--------|
| `test_fetch_new_languages` | ✅ PASSED |
| `test_update_regions` | ✅ PASSED |
| `test_save_movie_list` | ✅ PASSED |
| `test_sync_upcoming_movies` | ✅ PASSED |
| `test_sort_objects` | ✅ PASSED |

### `tests/services/test_user_service.py` (2 tests)

| Test | Result |
|------|--------|
| `test_name_filter_with_pagination` | ✅ PASSED |
| `test_name_filter_with_other_filters` | ✅ PASSED |

### `tests/test_email_background.py` (2 tests)

| Test | Result |
|------|--------|
| `test_send_queued_emails_with_server_name` | ✅ PASSED |
| `test_send_queued_emails_fails_without_server_name` | ✅ PASSED |

---

## Code Coverage

Coverage was measured with `pytest-cov` (`--cov=app --cov-report=term-missing`).

| Module | Stmts | Miss | Cover |
|--------|------:|-----:|------:|
| `app/cli.py` | 31 | 12 | 61% |
| `app/config.py` | 63 | 2 | 97% |
| `app/create_app.py` | 68 | 5 | 93% |
| `app/errors.py` | 13 | 2 | 85% |
| `app/extensions.py` | 40 | 2 | 95% |
| `app/models/allowed_refresh_token.py` | 52 | 24 | 54% |
| `app/models/misc_data.py` | 21 | 10 | 52% |
| `app/models/movie.py` | 59 | 29 | 51% |
| `app/models/movie_language_info.py` | 39 | 22 | 44% |
| `app/models/movie_region_info.py` | 25 | 10 | 60% |
| `app/models/notification.py` | 23 | 0 | **100%** |
| `app/models/notification_channel.py` | 22 | 4 | 82% |
| `app/models/send_confirmation_mails.py` | 7 | 0 | **100%** |
| `app/models/tmdb_genre.py` | 24 | 3 | 88% |
| `app/models/tmdb_language.py` | 23 | 11 | 52% |
| `app/models/tmdb_region.py` | 25 | 11 | 56% |
| `app/models/user.py` | 25 | 0 | **100%** |
| `app/models/user_calendar.py` | 29 | 0 | **100%** |
| `app/models/user_email.py` | 6 | 0 | **100%** |
| `app/models/user_movie.py` | 13 | 0 | **100%** |
| `app/routes/api.py` | 217 | 176 | 19% |
| `app/routes/html.py` | 580 | 383 | 34% |
| `app/scheduler.py` | 46 | 28 | 39% |
| `app/services/image_service.py` | 46 | 3 | 93% |
| `app/services/maintenance_service.py` | 33 | 24 | 27% |
| `app/services/movie_service.py` | 6 | 0 | **100%** |
| `app/services/tmdb_service.py` | 384 | 216 | 44% |
| `app/services/user_service.py` | 245 | 79 | 68% |
| `app/utils/auth.py` | 156 | 81 | 48% |
| `app/utils/email.py` | 74 | 21 | 72% |
| `app/utils/ics.py` | 24 | 21 | 12% |
| `app/utils/notifications.py` | 136 | 114 | 16% |
| `app/utils/profiler.py` | 69 | 11 | 84% |
| `app/utils/tmdb.py` | 96 | 53 | 45% |
| `app/utils/webpush.py` | 73 | 56 | 23% |
| **TOTAL** | **2793** | **1413** | **49%** |

### Coverage highlights

- **100% coverage:** `notification`, `send_confirmation_mails`, `user`, `user_calendar`, `user_email`, `user_movie`, `movie_service`
- **High coverage (≥ 85%):** `config` (97%), `create_app` (93%), `image_service` (93%), `extensions` (95%), `tmdb_genre` (88%), `errors` (85%)
- **Low coverage (< 30%):** `routes/api` (19%), `utils/notifications` (16%), `utils/ics` (12%), `utils/webpush` (23%), `services/maintenance_service` (27%)

---

## How to Reproduce

```bash
# From the repository root, using the project virtual environment
.venv/bin/python -m pytest -v --cov=app --cov-report=term-missing
```

See [`tests/README.md`](README.md) for full instructions, including the Docker-based workflow.
