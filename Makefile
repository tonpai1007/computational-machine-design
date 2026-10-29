# Makefile for the MDIE Armchair Slide Pipeline
# ---------------------------------------------
# Targets:
#   make slides      – generate armchair_slides.html from markdown
#   make clean      – remove generated files
#   make publish     – (optional) push HTML to GitHub Pages gh‑pages branch
#
# Prerequisites:
#   - npm install revealjs/revealjs  (once, see README)
#   - marp-cli and marp-revealjs plugin installed globally or locally
#   - Git configured with a remote that has a gh‑pages branch (or you can skip 'publish')

.PHONY: slides clean publish

# ----------- slides ------------------------------------------------------
slides: .reveal.js/armchair_slides.html

.reveal.js/armchair_slides.html: Project/chair/armchair_slides.md
	@echo ">>> Ensuring reveal.js folder exists"
	@if not exist .\reveal.js (npm install revealjs/revealjs)
	@echo ">>> Building slides with marp-revealjs"
	marp --revealjs "Project/chair/armchair_slides.md" --output ".reveal.js/armchair_slides.html" --theme "white" --transition "fade"

# ----------- clean -------------------------------------------------------
clean:
	@echo ">>> Removing generated slide HTML"
	@if exist .\reveal.js\armchair_slides.html del .\reveal.js\armchair_slides.html
	@if exist .\Project\chair\armchair_slides.html del .\Project\chair\armchair_slides.html

# ----------- publish ----------------------------------------------------
publish: .reveal.js/armchair_slides.html
	@echo ">>> Copying HTML to gh‑pages branch (git work‑tree)"
	@git worktree add -B gh-pages origin/gh-pages 2>/dev/null || git worktree add gh-pages origin/gh-pages 2>/dev/null || (git checkout --orphan gh-pages && git rm -r . && git worktree add gh-pages)
	@copy .\reveal.js\armchair_slides.html gh-pages\
	@cd gh-pages && git add -A && git commit -m "Update armchair slides [skip ci]" && git push origin gh-pages
	@echo ">>> Done – slides are now on gh‑pages"