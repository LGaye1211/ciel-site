# theme-tools: checks for the Dawn Dropship theme

Claude runs these before every push to the `shopify-theme` branch. You can run them too. They need the theme branch checked out as a folder, plus Python 3.9+ and Node 18+.

```
git worktree add ../theme shopify-theme     # the theme branch as a sibling folder
cd shop/store/theme-tools
npm install                                 # once: Theme Check and LiquidJS, versions pinned

python validate_theme.py ../../../../theme
node run_theme_check.js ../../../../theme
node render_sections.test.js ../../../../theme
```

Adjust the path to wherever the theme folder is.

| Script | Checks | Clean result |
|---|---|---|
| `validate_theme.py` | Required folders and files. Every JSON file parses (comments allowed, as Shopify allows). Every template and section group against the schema of each section it uses: setting ids, select options, ranges, block types, color schemes. Snippets and assets that are referenced exist. Saved settings exist in `config/settings_schema.json`. | prints `ok:` and exits 0 |
| `run_theme_check.js` | Shopify's Theme Check, the engine behind `shopify theme check`. | no errors. The 9 warnings that remain are the same 9 stock Dawn 16.0.0 produces. |
| `render_sections.test.js` | Renders the custom sections with LiquidJS against filled, empty and edge-case Store facts: singular and plural days, swapped delivery ends, empty fields hidden, line breaks in the address, no stray `undefined`. | `all render checks passed` |

LiquidJS is close to Shopify's Liquid but not identical. These scripts catch logic, schema and typo errors. They do not replace a preview in the store. Sections that change need matching checks in `render_sections.test.js`.

`../build_theme_zip.py` builds the manual-upload zip. Its tests run with the rest of the store tests: `cd .. && python -m unittest`.
