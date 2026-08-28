class TornLedger(UserWarning):
    """Warned when one record of a ledger cannot be read, and is skipped rather than raised.

    A ledger is a stream of independent records, so a record torn by a killed write,
    a full disk, or a truncated output costs exactly itself. Naming the condition as
    its own warning category is what lets a caller filter it, count it, or promote it
    to an error, instead of a whole host's evidence silently reading as absent.
    """
