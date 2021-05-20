"""strings for use in OpenLocation.evidence fields

Enumerate all possible evidence strings here.
TODO: expand list beyond OA journal evidence
"""

oa_journal_prefix = 'oa journal'

oa_journal_observed = '{} (via observed oa rate)'.format(oa_journal_prefix)
oa_journal_doaj = '{} (via doaj)'.format(oa_journal_prefix)
oa_journal_publisher = '{} (via publisher name)'.format(oa_journal_prefix)
oa_journal_manual = '{} (via manual setting)'.format(oa_journal_prefix)