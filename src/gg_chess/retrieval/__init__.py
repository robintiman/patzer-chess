"""Position retrieval — puzzle bank, opening book, endgame tablebase.

Each submodule exposes both:
  - an indexer/setup function (run-once, populates SQLite or downloads files)
  - LLM tool functions (cheap lookups used at coaching time)
"""
