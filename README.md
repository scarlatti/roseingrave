# Roseingrave

Massively scalable musical source comparator.

See the
[documentation](https://github.com/scarlatti/roseingrave/blob/main/Documentation.md)
for detailed documentation.

## Installation

Install the package through pip (recommended to do in a virtual environment):

```bash
$ python3 -m pip install roseingrave
```

The package will be added as a top-level command:

```bash
$ roseingrave --help
```

Create a folder to store all your input/output files. In this folder, place your
OAuth credentials file (see
[Credentials](https://github.com/scarlatti/roseingrave#credentials))
and all required and optional input files.

See the
[documentation](https://github.com/scarlatti/roseingrave/blob/main/Documentation.md)
for customizing filepaths and the expected input file formats.

## Credentials

The package interacts with Google Sheets through the
[`gspread` package](https://docs.gspread.org/en/latest/).
You can enable an OAuth Client to create, access, and edit spreadsheets with
your email.

To enable the OAuth Client, follow these steps:

1. Go to the [Google Developers Console](https://console.cloud.google.com/).
2. Log in with the email account you want to use with the OAuth Client. All
   created spreadsheets will be owned by this account in Google Drive.
3. Create a new project.
4. Go to the [API Library](https://console.cloud.google.com/apis/library).
5. In the search bar, search for "Google Drive API", select it, and enable it.
6. Go back to the API library. In the search bar, search for "Google Sheets
   API", select it, and enable it.
7. Go to the
   [OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent)
   tab.
8. If prompted, select "External" for the User Type.
9. On the "App Information" page, enter an app name. Select your email address
   for the support email. Scroll down to the bottom and enter your email address
   for the developer contact information. Click "Save and Continue".
10. On the "Scopes" page, click "Save and Continue".
11. On the "Test Users" page, add your email address as a user. Click "Save and
    Continue".
12. On the summary page, scroll to the bottom and click "Back to Dashboard".
13. Go to the [Credentials](https://console.cloud.google.com/apis/credentials)
    tab.
14. At the top of the page, select "+ Create credentials" > "OAuth client ID".
15. For the application type, select "Desktop app". Name your credentials.
    Click "Create". Click "Ok" at the popup.
16. In the table labeled "OAuth 2.0 Client IDs", locate the credentials you just
    created. Click the download button at the end of the row.
17. Rename the file to `credentials.json` and place it in the root directory of
    where you'll be running the commands. (You can customize this in the
    [settings](https://github.com/scarlatti/roseingrave/blob/main/Documentation.md#settings-optional)
    file).

If you've never authorized the app or if your authorization has expired, you'll
be given a link in the console for you to visit in order to refresh or create
an authorization token. Go to the url, select your email, click "Continue",
allow access to your Drive files and Sheets spreadsheets, and click "Continue".
This should authenticate you, and the command should continue running.

Once the authorization is successful, the `authorized_user.json` file will be
created in the same directory as `"credentials"`.

## Basic Usage

Create the piece definitions and volunteer definitions files as explained in the
[documentation](https://github.com/scarlatti/roseingrave/blob/main/Documentation.md#input-files).
If desired, create the settings file and/or the template file. Save all the
files in the proper locations as defined by the
[default settings file](https://github.com/scarlatti/roseingrave/blob/main/src/roseingrave/defaults/roseingrave.json)
or by your own settings file.

Based on your definition files, create the volunteer spreadsheets:

```bash
$ roseingrave create_sheet
```

After volunteers have filled out their spreadsheets, export the data:

```bash
$ roseingrave volunteer_summary
```

Extract the data for each piece:

```bash
$ roseingrave piece_summary
```

Compile all the piece data into the summary file:

```bash
$ roseingrave compile_pieces
```

Create the master spreadsheets with the data from the summary file:

```bash
$ roseingrave import_master
```

Fill out the summary columns as appropriate, then export the master spreadsheet
into the summary file:

```bash
$ roseingrave export_master
```

See the
[commands documentation](https://github.com/scarlatti/roseingrave/blob/main/Documentation.md#commands)
for all commands and their arguments and options.
