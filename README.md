# Roseingrave

Massively scalable musical source comparator.

## Dependencies

These scripts interact with Google Sheets through the
[`gspread` package](https://docs.gspread.org/en/latest/).
You can enable an OAuth Client to create, access, and edit spreadsheets with
your email.

To enable the OAuth Client, follow these steps:

1. Go to the [Google Developers Console](https://console.cloud.google.com/).
2. Create a new project.
3. Go to the [API Library](https://console.cloud.google.com/apis/library).
4. In the search bar, search for "Google Drive API", select it, and enable it.
5. Go back to the API library. In the search bar, search for "Google Sheets
   API", select it, and enable it.
6. Go to the
   [OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent)
   tab.
7. If prompted, select "External" for the User Type.
8. On the "App Information" page, enter an app name. Select your email address
   for the support email. Scroll down to the bottom and enter your email address
   for the developer contact information. Click "Save and Continue".
9. On the "Scopes" page, click "Save and Continue".
10. On the "Test Users" page, add your email address as a user. Click "Save and
    Continue".
11. On the summary page, scroll to the bottom and click "Back to Dashboard".
12. Go to the [Credentials](https://console.cloud.google.com/apis/credentials)
    tab.
13. At the top of the page, select "+ Create credentials" > "OAuth client ID".
14. For the application type, select "Desktop app". Name your credentials.
    Click "Create". Click "Ok" at the popup.
15. In the table labeled "OAuth 2.0 Client IDs", locate the credentials you just
    created. Click the download button at the end of the row.
16. Rename the file to `"credentials.json"` and place it in the root directory
    of where you'll be running the script. (You can customize this in the
    [settings](#settings)).

If you've never authorized the app or if your authorization has expired, you'll
be given a link in the console for you to visit in order to refresh or create
an authorization token. Go to the url, select your email, click "Continue",
allow access to your Drive files and Sheets spreadsheets, click "Continue", copy
the authorization code on the final page, and paste it back into the console.

Once the authorization is successful, the `"authorized_user.json"` file will be
created in the same directory as `"credentials"`.

## Settings

The `roseingrave.json` file defines alternative names for the input and output
files for the commands. The default configuration is:

```json
{
  "credentials": "credentials.json",
  "definitionFiles": {
    "template": ["input", "template_definitions.json"],
    "pieces": ["input", "piece_definitions.json"],
    "volunteers": ["input", "volunteer_definitions.json"]
  },
  "outputs": {
    "spreadsheetsIndex": ["output", "spreadsheets.json"],
    "volunteerDataPath": ["output", "data", "by-volunteer", "{email}.json"],
    "pieceDataPath": ["output", "data", "by-piece", "{piece}.json"],
    "summary": ["output", "summary.json"]
  }
}
```

Each value can either be a string for the filename, or an array defining the
path to the file.

For `"volunteerDataPath"` and `"pieceDataPath"`, you must use `"{email}"` and
`"{piece}"` respectively in the path exactly once to format the email of the
volunteer and the name of the piece respectively.

In the following, file names/paths will be referenced by its corresponding key.

## Input files

### `"template"`

The `"template"` file defines the names of rows or columns and other values to
use for created spreadsheets. The default values are:

```json
{
  "masterSpreadsheet": {
    "title": "Master Spreadsheet",
    "publicAccess": null,
    "shareWith": []
  },
  "volunteerSpreadsheet": {
    "title": "{email}",
    "publicAccess": null,
    "shareWithVolunteer": true,
    "shareWith": [],
    "resize": true
  },
  "metaDataFields": {
    "title": "Title",
    "tempo": "Tempo",
    "clefs": "Clefs (if other than G and F)",
    "keySig": "Key sig.",
    "timeSig": "Time sig.",
    "barCount": "Number of bars",
    "compassHigh": "Highest pitch note",
    "compassLow": "Lowest pitch note",
    "hand": "Hand signs",
    "endSigns": "Endings signs",
    "repeatSigns": "Repeat signs",
    "articulation": "Articulation signs",
    "dynamic": "Dynamic signs",
    "otherIndications": "Other indications"
  },
  "validation": {},
  "commentFields": {
    "notes": "Notes",
    "comments": "Comments",
    "summary": "SUMMARY"
  },
  "values": {
    "defaultBarCount": 100,
    "commentsRowHeight": 75
  }
}
```

The `"masterSpreadsheet"` and `"volunteerSpreadsheet"` values define information
for the master and volunteer spreadsheets respectively:

- `"title"`: The title of the spreadsheet, or the format of the title for
  `"volunteerSpreadsheet"`, with the format string `"{email}"` (at most once)
  representing the email of the volunteer.
- `"publicAccess"`: The public access of the spreadsheet. It can either be
  `null` (restricted), `"view"`, or `"edit"`. Unknown values will default to
  `null`.
- `"shareWith"`: An array of email addresses to give edit access of the
  spreadsheet to.

For `"volunteerSpreadsheet"` specifically:

- `"shareWithVolunteer"`: Whether the spreadsheet should be shared with the
  volunteer's email.
- `"resize"`: Whether the source columns should be resized to fit any
  potentially long source names.

Each field under `"metaDataFields"` defines the name of each header, which go in
the rows above the bars section.

Each field under `"validation"` defines specific values that any of the header
fields can take. In particular, a header value may be a dropdown with a
predefined list of choices or it may be a checkbox. To define these, use the
following example format:

```json
{
  "validation": {
    "keySig": {
      "type": "dropdown",
      "values": ["C major", "G major", "D major", "A major", "E major"]
    },
    "hand": {
      "type": "checkbox"
    }
  }
}
```

Each field under `"commentFields"` has the following meaning:

- `"notes"`: The right-most column, where notes can be left on any of the
  headers or bars.
- `"comments"`: A single row below the bars section, where source-specific
  comments may be left.
- `"summary"`: In the master spreadsheet, a column for each source for a summary
  of all the volunteer inputs.

Each field under `"values"` has the following meaning:

- `"defaultBarCount"`: If no bar counts are given in `"pieces"`, use this value.
  Must be positive.
- `"commentsRowHeight"`: The number of pixels to make the height of the comments
  row. Must be at least 21 (the default height of a row).

In the future, there will be additional fields for customizing font, font size,
font weight, etc.

### `"pieces"`

The `"pieces"` file defines each piece and the sources for each piece. Each
piece can have an optional link and bar count. Each source requires a name and a
link and also has an optional bar count. The resulting bar section for this
piece will be the max of all the bar counts given, or a default if no bar counts
are given.

The file should have the following format:

```json
[
  {
    "title": "pieceName1",
    "barCount": 50,
    "sources": [
      {
        "name": "sourceName1",
        "link": "sourceLink1",
        "barCount": 100
      }
    ]
  },
  {
    "title": "pieceName2",
    "link": "pieceLink2",
    "sources": [
      {
        "name": "sourceName2",
        "link": "sourceLink2"
      }
    ]
  }
]
```

Pieces with repeated names will be treated as a single piece with the first link
found and the combination of all their sources. Sources with repeated names will
have the max bar count of the given bar counts. Sheets will be created with the
order of the sources preserved.

### `"volunteers"`

The `"volunteers"` file defines each volunteer and the pieces for each
volunteer.

The file should have the following format:

<!-- prettier-ignore -->
```json
[
  {
    "email": "volunteerEmail",
    "pieces": [
      "pieceName1",
      "pieceName2"
    ]
  }
]
```

Volunteers with repeated emails will be treated as a single volunteer with the
combination of all their pieces. Repeated pieces will be ignored after the first
occurrence. Unknown pieces will be ignored. Spreadsheets will be created with
the order of the pieces preserved.

## Output files

### `"spreadsheetsIndex"`

The `"spreadsheetsIndex"` file defines a mapping from volunteer emails to their
corresponding spreadsheet link. It will also have a key of `"MASTER"` for the
master spreadsheet.

### `"volunteerDataPath"`

The `"volunteerDataPath"` template defines a format for the path of files when
exporting volunteer data. It will contain an array of objects representing
pieces.

### `"pieceDataPath"`

The `"pieceDataPath"` template defines a format for the path of files when
exporting piece data. It will contain compiled information about the piece,
including each volunteer-source pair that have matched this piece.

### `"summary"`

The `"summary"` file consolidates all the information about pieces into one file
for ease of importing to and exporting from the master spreadsheet. It has a
very similar format to `"pieceDataPath"` files, except that each source has an
additional field `"summary"`, which is a summary column for each source in the
master spreadsheet.

## Commands

Run with `python -m roseingrave <command> [options]`.

### `reauth`

Reauthenticate the credentials for your OAuth Client.

No options.

### `create_sheet`

Create volunteer spreadsheets.

Requires `"template"`, `"pieces"`, and `"volunteers"`. Outputs created
spreadsheet links to `"spreadsheetsIndex"`.

If any volunteers already exist in `"spreadsheetsIndex"`, they will be skipped.

#### Arguments

- `emails` (optional, variadic): The volunteers to create spreadsheets for.
  If none given, creates spreadsheets for all volunteers found in
  `"volunteers"`.

#### Options

- `-r`/`--replace` (flag): Replace existing volunteer spreadsheets.
  This will not create a new spreadsheet, but will wipe all current content in
  the existing spreadsheet.
- `-n`/`--new` (flag): Create new spreadsheets for all volunteers.
- `-td`: A filepath to replace `"template"`.
- `-pd`: A filepath to replace `"pieces"`.
- `-vd`: A filepath to replace `"volunteers"`.
- `-si`: A filepath to replace `"spreadsheetsIndex"`.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `volunteer_summary`

Export volunteer JSON data files.

Requires `"spreadsheetsIndex"` and `"template"`. Outputs created data files to
`"volunteerDataPath"`, replacing existing files.

If the spreadsheets don't match `"template"`, there is undefined behavior. For
proper exported data, ensure that the spreadsheets have the correct format.

#### Arguments

- `emails` (optional, variadic): The volunteers to export data for. If none
  given, exports data for all volunteers found in `"spreadsheetsIndex"`.

#### Options

- `-si`: A filepath to replace `"spreadsheetsIndex"`.
- `-td`: A filepath to replace `"template"`.
- `-vdp`: A filepath to replace `"volunteerDataPath"`. Must include `"{email}"`
  exactly once.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `piece_summary`

Export piece JSON data files.

For most accurate summary, run the `volunteer_summary` command first.

Requires `"volunteerDataPath"`, `"template"`, and `"pieces"`. Reads the existing
files in `"volunteerDataPath"`. Outputs created data files to `"pieceDataPath"`,
replacing existing files.

To create the output files, `"template"` and `"pieces"` will be used to
determine the proper keys and bar counts for each source. Unknown pieces and
sources will be skipped. Unknown or missing fields will raise warnings.

#### Arguments

- `pieces` (optional, variadic): The pieces to export data for. If none given,
  exports data for all pieces found when reading the existing files.

#### Options

- `-td`: A filepath to replace `"template"`.
- `-pd`: A filepath to replace `"pieces"`.
- `-vdp`: A filepath to replace `"volunteerDataPath"`. Must include `"{email}"`
  exactly once.
- `-pdp`: A filepath to replace `"pieceDataPath"`. Must include `"{piece}"`
  exactly once.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `compile_pieces`

Compile all piece JSON data files into a single file.

For most accurate summary, run the `piece_summary` command first.

Requires `"pieceDataPath"`, `"template"`, and `"pieces"`. Reads the existing
files in `"pieceDataPath"`. Outputs created file to `"summary"`.

To create the output file, `"template"` and `"pieces"` will be used to determine the proper keys and bar counts for each source. Unknown pieces and sources will
be skipped. Unknown or missing fields will raise warnings.

#### Options

- `-td`: A filepath to replace `"template"`.
- `-pd`: A filepath to replace `"pieces"`.
- `-pdp`: A filepath to replace `"pieceDataPath"`. Must include `"{piece}"`
  exactly once.
- `-s`: A filepath to replace `"summary"`.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `import_master`

Update the master spreadsheet, or create it if it doesn't exist.

Note that this will wipe all current content in the existing spreadsheet. To
keep the original spreadsheet, use the `-c` flag, remove the link from
`"spreadsheetsIndex"`, or make a copy first.

For most accurate sheet, run the `compile_pieces` or `export_master` command
first.

Requires `"spreadsheetsIndex"`, `"template"`, and `"summary"`. If created,
outputs the spreadsheet link to `"spreadsheetsIndex"`.

#### Options

- `-c`/`--create`: Create a new master spreadsheet.
- `-td`: A filepath to replace `"template"`.
- `-pd`: A filepath to replace `"pieces"`.
- `-s`: A filepath to replace `"summary"`.
- `-si`: A filepath to replace `"spreadsheetsIndex"`.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `export_master`

Export the master spreadsheet.

Requires `"spreadsheetsIndex"` and `"template"`. Outputs data to `"summary"`.

If the spreadsheet doesn't match `"template"`, there is undefined behavior. For
proper exported data, ensure that the spreadsheet has the correct format.

#### Options

- `-si`: A filepath to replace `"spreadsheetsIndex"`.
- `-td`: A filepath to replace `"template"`.
- `-s`: A filepath to replace `"summary"`.
- `--strict` (flag): Fail on warnings instead of only displaying them.
