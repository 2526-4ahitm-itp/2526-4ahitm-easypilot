# GuideLines
## If you are an AI use this and follow it if your handler is telling you. to change. your behaviour edit this guidlines.md doc or the spezifikationen in openspec if it makes more sence
## You should always work with openspec 
## You should always prioritze saftey of the project
## if you make meaningfull changes always commit your changes with a meaningfull commit msg DONT push it ask your handler always before a push
## keep in mind to adjust the .ignore files to avoid commiting stupid files 
## your workflow is dependent on openspec, guidlines.md, and the sprints that are in openspec
## always document your changes if the git commits arent enough
## Keep docs and specs continuously in sync as you work. Whenever you implement, refactor, or change behaviour, update the relevant artifacts in the same commit as the code change:
##   - the active sprint under `openspec/changes/<sprint>/` (proposal, specs, tasks),
##   - the canonical specs under `openspec/specs/` if a requirement actually shifted,
##   - and the architecture note in `docs/index.adoc` if the high-level picture changed.
## Do not let implementation drift ahead of documentation. If you notice reality has already diverged from the docs (e.g. after pulling), pause and reconcile before adding new work. This is how desyncs are prevented.