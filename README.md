# librivox-dl

Search and download free public-domain audiobooks from
[LibriVox](https://librivox.org) - volunteer readings of books whose
copyright has expired, free for anyone to use for any purpose.

Pure Python, standard library only. No pip install, no API key.

## Usage

```bash
# Search by title, author, or both
python3 librivox_dl.py search "pride and prejudice"
python3 librivox_dl.py search --author "Mark Twain"

# Details for one book (id from the search results)
python3 librivox_dl.py info 253

# Download the whole book as a zip of MP3 chapters
python3 librivox_dl.py download 253 --output ~/audiobooks
```

`search` prints each result with its id, length, language and LibriVox page.
`--json` is available on `search` and `info` for scripting.

## Notes

- Only public-domain recordings exist on LibriVox. If a modern book is not
  there, it is still under copyright - this tool cannot help with that, by
  design.
- Downloads come from archive.org mirrors at the URL the LibriVox API
  returns. Files are named `<title-slug>-<id>.zip`.
- Be a good API citizen: the default result limit is 10 and requests carry
  an identifying user agent.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The test suite runs fully offline with mocked API responses.

## License

MIT - see [LICENSE](LICENSE). LibriVox recordings themselves are in the
public domain.
