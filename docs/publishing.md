# Publish this checkout to GitHub

This project has been imported into the existing local clone of:

https://github.com/haoranyoung09-sys/contextbridge-handoff

The original clone's `.git` directory and origin remote are preserved. Import
does not stage files, create commits, or push. Review all public files first.

1. Run local checks from the repository root:

   ```console
   python -m pip install -e ".[dev]"
   python -m pytest
   python -m build
   git status --short
   ```

2. Review the MIT attribution, README, and generated benign examples. Never
   stage real snapshots, credentials, or personal notes. `.gitignore` excludes
   generated handoffs, build output, caches, and virtual environments.

3. Review and create the initial commit yourself:

   ```console
   git add .
   git diff --cached --stat
   git diff --cached
   git commit -m "feat: add offline agent handoff MVP"
   ```

4. Verify that origin is your intended repository before publishing:

   ```console
   git remote -v
   git push -u origin main
   ```

   Origin already exists in this clone; do not add a second origin or replace
   the `.git` directory. Configure your own commit identity if Git requests it.

5. Confirm the GitHub Actions matrix succeeds, then tag the reviewed commit as
   `v0.1.0` and create a release if desired. Wheel/source archives are generated
   locally by `python -m build` and are not committed.

PyPI publication is separate. The distribution name `contextbridge-handoff`
remains provisional and has not been checked for availability. This project
does not configure publishing credentials or automated releases.
