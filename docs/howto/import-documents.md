# Import old notes and slides

Originals are never modified; everything works on a copy inside the vault.

1. Copy the old vault into the staging folder and write the inventory.

   ```bash
   hal-memory import stage ~/old/Vault --dry-run   # show what would be copied
   hal-memory import stage ~/old/Vault             # copy and write IMPORT-MANIFEST.md
   ```

   The manifest lists duplicate file names: the one real risk, since Obsidian resolves links by
   name.

2. In your harness, run the `import-vault` skill. It proposes where each folder goes and files
   the notes with frontmatter, folder by folder, after you agree.

3. Extract the text of every document and mark the decks with no note yet.

   ```bash
   hal-memory import prepare --ocr   # PDF, DOCX, PPTX, HTML; --ocr for scanned decks
   ```

4. Write a study note per deck, unattended (or use the `summarize-slides` skill for a few).

   ```bash
   hal-memory summarize --limit 5    # a stopped run carries on where it left off
   ```

5. Add code repos as hub notes, then run the `index-repos` skill to fill in summaries.

   ```bash
   hal-memory register-repos ~/code  # git metadata only; credentials stripped from remotes
   ```

The summariser uses `HAL_MODEL` when set, else `[hal].chat_model`; the study root note is
`[memory].university`.

| Symptom | Fix |
| --- | --- |
| `missing pdftotext` or `tesseract` | Install the package `setup` names; it never runs sudo. |
| A tool call stops after 120 s | Raise `HAL_TOOL_TIMEOUT` (seconds). |
| No decks in `SLIDES-REPORT.md` | Pass the folder: `hal-memory import prepare DIR`. |
| The summariser cannot reach the model | Start the model server, or run with `--mock` to test the flow. |
