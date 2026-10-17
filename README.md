# Library Management System

A simple Python command-line library manager backed by SQLite. It can maintain a book catalog and member list, search books, record loans, and process returns. Data persists in `library.db` in the same folder as the program.

## Run

Requires Python 3.9 or newer. No third-party packages are needed.

```powershell
python library.py
```

Use the numbered menu to manage books and members. To borrow a book, first add a member and a book, then enter their IDs. To return a book, choose the active loan ID.
