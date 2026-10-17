"""A small, persistent command-line library management system.

Run with ``python library.py``. Data is stored in ``library.db`` beside this file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).with_name("library.db")


class Library:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                isbn TEXT UNIQUE,
                copies INTEGER NOT NULL DEFAULT 1 CHECK(copies >= 0)
            );
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id),
                member_id INTEGER NOT NULL REFERENCES members(id),
                borrowed_on TEXT NOT NULL DEFAULT (date('now')),
                returned_on TEXT
            );
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def add_book(self, title: str, author: str, isbn: Optional[str], copies: int) -> int:
        if not title.strip() or not author.strip():
            raise ValueError("Title and author are required.")
        if copies < 1:
            raise ValueError("Copies must be at least 1.")
        cur = self.db.execute(
            "INSERT INTO books(title, author, isbn, copies) VALUES (?, ?, ?, ?)",
            (title.strip(), author.strip(), isbn.strip() or None if isbn else None, copies),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def add_member(self, name: str, email: Optional[str]) -> int:
        if not name.strip():
            raise ValueError("Member name is required.")
        cur = self.db.execute(
            "INSERT INTO members(name, email) VALUES (?, ?)",
            (name.strip(), email.strip() or None if email else None),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def books(self, query: str = "") -> list[sqlite3.Row]:
        term = f"%{query.strip()}%"
        return list(self.db.execute(
            "SELECT b.id, b.title, b.author, b.isbn, b.copies - "
            "(SELECT COUNT(*) FROM loans l WHERE l.book_id=b.id AND l.returned_on IS NULL) AS available, "
            "b.copies FROM books b WHERE b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ? "
            "ORDER BY b.title COLLATE NOCASE", (term, term, term)
        ))

    def members(self) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT id, name, email FROM members ORDER BY name COLLATE NOCASE"))

    def borrow(self, book_id: int, member_id: int) -> int:
        book = self.db.execute("SELECT copies FROM books WHERE id=?", (book_id,)).fetchone()
        if not book:
            raise ValueError("Book not found.")
        if not self.db.execute("SELECT 1 FROM members WHERE id=?", (member_id,)).fetchone():
            raise ValueError("Member not found.")
        active = self.db.execute(
            "SELECT COUNT(*) FROM loans WHERE book_id=? AND returned_on IS NULL", (book_id,)
        ).fetchone()[0]
        if active >= book["copies"]:
            raise ValueError("No copies are currently available.")
        cur = self.db.execute("INSERT INTO loans(book_id, member_id) VALUES (?, ?)", (book_id, member_id))
        self.db.commit()
        return int(cur.lastrowid)

    def return_book(self, loan_id: int) -> None:
        cur = self.db.execute(
            "UPDATE loans SET returned_on=date('now') WHERE id=? AND returned_on IS NULL", (loan_id,)
        )
        if cur.rowcount == 0:
            raise ValueError("Active loan not found (it may already be returned).")
        self.db.commit()

    def active_loans(self) -> list[sqlite3.Row]:
        return list(self.db.execute(
            "SELECT l.id, b.title, m.name, l.borrowed_on FROM loans l "
            "JOIN books b ON b.id=l.book_id JOIN members m ON m.id=l.member_id "
            "WHERE l.returned_on IS NULL ORDER BY l.borrowed_on, l.id"
        ))


def show_books(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("No books found.")
        return
    print("\nID | Title | Author | ISBN | Available/Total")
    for row in rows:
        print(f"{row['id']} | {row['title']} | {row['author']} | {row['isbn'] or '-'} | {row['available']}/{row['copies']}")


def prompt_int(label: str) -> int:
    try:
        return int(input(label).strip())
    except ValueError as exc:
        raise ValueError("Please enter a valid number.") from exc


def main() -> None:
    library = Library()
    actions = {
        "1": "List/search books", "2": "Add a book", "3": "Add a member",
        "4": "List members", "5": "Borrow a book", "6": "Return a book",
        "7": "Show active loans", "0": "Exit",
    }
    try:
        while True:
            print("\n=== Library Management System ===")
            for key, label in actions.items():
                print(f"{key}. {label}")
            choice = input("Choose an option: ").strip()
            try:
                if choice == "1":
                    show_books(library.books(input("Search title, author, or ISBN (blank for all): ")))
                elif choice == "2":
                    book_id = library.add_book(input("Title: "), input("Author: "), input("ISBN (optional): "), prompt_int("Number of copies: "))
                    print(f"Book added with ID {book_id}.")
                elif choice == "3":
                    member_id = library.add_member(input("Member name: "), input("Email (optional): "))
                    print(f"Member added with ID {member_id}.")
                elif choice == "4":
                    for member in library.members():
                        print(f"{member['id']} | {member['name']} | {member['email'] or '-'}")
                elif choice == "5":
                    show_books(library.books())
                    loan_id = library.borrow(prompt_int("Book ID: "), prompt_int("Member ID: "))
                    print(f"Loan created with ID {loan_id}.")
                elif choice == "6":
                    for loan in library.active_loans():
                        print(f"Loan {loan['id']} | {loan['title']} | {loan['name']} | borrowed {loan['borrowed_on']}")
                    library.return_book(prompt_int("Loan ID to return: "))
                    print("Book returned.")
                elif choice == "7":
                    loans = library.active_loans()
                    if not loans:
                        print("There are no active loans.")
                    for loan in loans:
                        print(f"Loan {loan['id']} | {loan['title']} | {loan['name']} | borrowed {loan['borrowed_on']}")
                elif choice == "0":
                    print("Goodbye.")
                    break
                else:
                    print("Choose one of the listed options.")
            except (ValueError, sqlite3.IntegrityError) as exc:
                print(f"Error: {exc}")
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye.")
    finally:
        library.close()


if __name__ == "__main__":
    main()
