"""Medical report intake, validation, extraction contract and de-identification.

Isolated in its own package so the sensitive path is easy to locate, review and
reason about. Nothing here is imported by the scientific engines: a value taken
from a report cannot reach a calculation.
"""
