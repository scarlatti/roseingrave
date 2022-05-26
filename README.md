# roseingrave

Massively scalable musical source comparator

## Commands

Here is the list of commands that can be run from the command line.

- `create_sheet [EMAIL]`

  - creates a volunteer spreadsheet for a given volunteer email
    - if no email provided, creates spreadsheets for all volunteers in `volunteer_definition.json`
    - if volunteer email already exists in `spreadsheets.json`, skip (don't create another sheet)
  - requires `piece_definition.json`, `volunteer_definition.json`, and `template_definition.json`
  - updates `spreadsheets.json` with a mapping from volunteer email to spreadsheet link

- `volunteer_summary [EMAIL]`

  - creates a volunteer JSON file for a given volunteer email
    - if no email provided, creates JSONs for all volunteers
  - requires `spreadsheets.json` to find the spreadsheet link
    - error if not found
  - outputs `volunteers/<email>.json`

- `piece_summary [PIECE]`

  - creates a piece JSON file for a given piece
    - if no piece provided, creates JSONs for all pieces found​
  - reads the existing files in the `volunteers/` subdirectory and compiles info from them
    - for accurate summary, run `volunteer_summary` first
  - outputs `pieces/<piece>.json`

- `compile_pieces` (open to name suggestions)
  - compiles all piece JSON files into a single file for importing to the master spreadsheet
  - reads the existing files in the `pieces/` subdirectory
    - for accurate summary, run `piece_summary` first
  - outputs `summary.json` (open to name suggestions) - the format for this file will be a little different from `<piece>.json`, for ease of importing/exporting from the master spreadsheet - for example, will include a "summary" field (defaults to `""`) for each source
    ​
- `import_master`

  - updates the master spreadsheet, or creates it if it doesn't exist in `spreadsheets.json`
  - requires `summary.json` and `template_definition.json`
    - for accurate sheet, run `compile_pieces` first
  - if created the sheet, updates `spreadsheets.json` with a "MASTER" key and the link

- `export_master`
  - exports the master spreadsheet to a JSON file
  - requires `spreadsheets.json` (for the spreadsheet link)
  - outputs/replaces `summary.json` (same as `compile_pieces`)

## Template Definitions

The `template_definitions.json` file defines the names of rows or columns in the created spreadsheets.

Required:

- `"owner"`: the email of the person to give ownership of each created spreadsheet

Optional with defaults:

- `"title"`, `"tempo"`, `"key"`, `"keySig"`, `"timeSig"`, `"barCount"`, `"compass"`, `"comments"`

In the future, there will be additional fields for customizing font, font size, font weight, etc.
