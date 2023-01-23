# Version History

## v0.10.1 (2023-01-23)

- Display error for a missing spreadsheets index file for commands that must
  read from it (`volunteer_summary` and `export_master`)
  (https://github.com/josephlou5/roseingrave/issues/14)
- Change OAuth authentication flow from deprecated console flow
  (https://github.com/josephlou5/roseingrave/issues/8)

## v0.10.0 (2022-11-06)

_Current version_

- Protect first row and column of non-master sheets so volunteers do not
  accidentally edit them (https://github.com/josephlou5/roseingrave/issues/13)
- Add `--export-known-only` option to `volunteer_summary` and `export_master`
  commands (https://github.com/josephlou5/roseingrave/issues/12)

## v0.9.1 (2022-11-03)

- Fixed bug relating to incorrectly exporting regular sheets as master sheets
  (https://github.com/josephlou5/roseingrave/issues/11)

## v0.9.0 (2022-06-29)

- Initial release
