# Daglige gjøremål (Daily chores)

> **Built with AI:** The code in this project was written by [Claude Code](https://claude.com/claude-code), Anthropic's AI coding assistant. My part was describing what the app should do, deciding on the features and design through prompts, and testing the result.

A simple web app that turns a fixed weekly cleaning plan into a checklist for each shift. It shows what needs to be done today, lets staff tick off chores and leave comments, and prints the weekly plan as a PDF with signature boxes.

All it needs is Python and a web browser. The server uses only Python's standard library, so there is nothing to install and no database.

The interface is in Norwegian. Button names below are shown as they appear in the app.

## Features

- **Today's chores** for each shift: *Dag* (day), *Kveld* (evening) and *Natt* (night). The current shift is selected automatically from the time of day.
- **Day and week views** (*Dag* / *Uke*). ‹ › move between days or weeks, and **↺ I dag** jumps back to today.
- **Tick off chores** and **comment** on them, for example to explain why something wasn't done.
- **Name per shift**: record who is working the day, evening or night shift.
- **Rotating chores** (*Rullerende gjøremål*): each Tuesday day shift gets one extra chore from a separate pool. For each chore you set roughly how many times a year it should happen and in which seasons (spring, summer, fall, winter). The app spreads them evenly over the year. The numbers work as weights: every Tuesday always gets one chore, so they only match the real count when they add up to about 52. The menu shows how many times each chore will actually come up this year.
- **Edit the fixed chores** in the app. The last 10 edits are kept and can be undone.
- **Separate TODO lists** (*Lag en TODO*), not part of the weekly plan, with ticking and comments.
- **PDF export**:
  - The weekly plan prints one A4 page per week with a *Sign.* column, styled like the original paper sheet.
  - TODO lists print with checkboxes, comments and a signature column.

  The PDFs are made by the browser's own print function: the app opens the print dialog, and you choose **Save as PDF** (or *Microsoft Print to PDF*) as the printer. Printing has been tested in Chrome. Edge is built on the same engine and should behave the same.

## Getting started

1. Install [Python 3.9 or newer](https://www.python.org/downloads/).
2. Put the weekly plan as a `.csv` file in the `data/` folder (see below).
3. Start the app from the project folder:

   ```
   python app.py
   ```

4. Your browser opens at <http://localhost:8000>. Press **Ctrl+C** in the terminal to stop the app.

## The weekly plan (CSV file)

The `data/` folder is **not included in the repository** (see `.gitignore`). It holds the workplace's weekly plan, and the app also stores names and comments there. Create the folder yourself and add the plan:

```
data/
└── <weekly-plan>.csv
```

In Excel, use **Save As → CSV UTF-8**. With Norwegian regional settings, Excel then separates the columns with semicolons, which is what the app expects. Don't use the plain *CSV (semicolon delimited)* option: it doesn't save as UTF-8, so æ, ø and å break and the app won't start. The app uses the first `.csv` file it finds in `data/` and reads these columns:

| Column | Content |
|---|---|
| B | Weekday (`Mandag` … `Søndag`). Only filled in on the day's first row. |
| C | Shift (`Dag`, `Kveld` or `Natt`). Only filled in on the shift's first row. |
| D | The chore. Each row gets one signature box on the printout. |

A row whose column C starts with `Ved behov:` ("as needed") becomes the list of as-needed chores. Everything below that row is ignored.

## Where data is stored

Everything is stored as files in `data/`. They are created automatically the first time they are needed:

| File | Content |
|---|---|
| `rullerende.json` | The rotating chores |
| `kommentarer.json` | Comments on chores, per date |
| `vakter.json` | Who is working which shift |
| `plan.json` | The fixed chores after someone edits them in the app. The CSV file itself is never changed. |
| `plan_historikk.json` | The last 10 edits to the fixed chores |
| `todo.json` | The separate TODO lists |

Everyone using the app sees the same data. The one exception is **ticks in the weekly plan**, which are saved only in the browser of the person who ticked them.

**Note:** the server only listens on `localhost`, so the app can only be used on the computer it runs on. Other phones or PCs on the network can't connect to it.

To go back to the original CSV after editing, use **Tilbakestill alt til original** ("reset everything to the original") in the menu.

## Project structure

```
app.py              Server (Python): reads the weekly plan and stores data
static/index.html   The entire user interface (HTML, CSS and JavaScript)
data/               Weekly plan and saved data (not in the repository)
```
