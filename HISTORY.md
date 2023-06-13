# Version History

## v1.1.0 (unreleased)

- Added `"values"."sourcesColumnWidth"` field to template file
- Increased default width of column 1 to 285
- Added all editors of spreadsheet (except volunteer) to protected range
- Added `--version` option

## v1.0.0 (2023-03-03)

- Removed any mention of the "master" spreadsheet or "master" commands
  (https://github.com/scarlatti/roseingrave/issues/17)
- Removed hard-coded `"metaDataFields"` values from defaults file
  (https://github.com/scarlatti/roseingrave/issues/21)
  - This forces the `"template"` file to be required for the user, which is a
    non-backward compatible change.

## v0.12.1 (2023-02-28)

- Fixed bug of using the only sheet as a temp sheet without renaming it (leading
  to possible title conflicts when adding new piece sheets)
  (https://github.com/scarlatti/roseingrave/issues/20)
- Fixed bug of plain text formatting not allowing checkboxes to render
  (https://github.com/scarlatti/roseingrave/issues/22)

## v0.12.0 (2023-02-20)

- Deprecated any mention of the "master" spreadsheet
  (https://github.com/scarlatti/roseingrave/issues/17)
  - Users should use "summary" instead
  - This will be fully removed in v1.0.0

## v0.11.0 (2023-02-16)

- Added `--extend` option to `create_sheet` command to extend a volunteer
  spreadsheet with missing pieces
  (https://github.com/scarlatti/roseingrave/issues/19)

## v0.10.2 (2023-02-15)

- Moved repo to [`scarlatti` organization](https://github.com/scarlatti)
- Fixed protected range bug: specify emails of editors (which is only the owner)
  (https://github.com/scarlatti/roseingrave/issues/13)
- Added text wrapping and disable automatic number formatting for any cells with
  user input (https://github.com/scarlatti/roseingrave/issues/16
  https://github.com/scarlatti/roseingrave/issues/18)

## v0.10.1 (2023-01-23)

- Added error for a missing spreadsheets index file for commands that must read
  from it (`volunteer_summary` and `export_master`)
  (https://github.com/scarlatti/roseingrave/issues/14)
- Changed OAuth authentication flow from deprecated console flow
  (https://github.com/scarlatti/roseingrave/issues/8)

## v0.10.0 (2022-11-06)

- Added protected ranges to first row and column of non-master sheets so
  volunteers do not accidentally edit them
  (https://github.com/scarlatti/roseingrave/issues/13)
- Added `--export-known-only` option to `volunteer_summary` and `export_master`
  commands (https://github.com/scarlatti/roseingrave/issues/12)

## v0.9.1 (2022-11-03)

- Fixed bug relating to incorrectly exporting regular sheets as master sheets
  (https://github.com/scarlatti/roseingrave/issues/11)

## v0.9.0 (2022-06-29)

- Initial release
