"""strings for use in OpenLocation.evidence fields

Enumerate all possible evidence strings here.
TODO: expand list beyond OA journal evidence
"""

oa_journal_prefix = u'oa journal'

oa_journal_observed = u'{} (via observed oa rate)'.format(oa_journal_prefix)
oa_journal_doaj = u'{} (via doaj)'.format(oa_journal_prefix)
oa_journal_publisher = u'{} (via publisher name)'.format(oa_journal_prefix)
oa_journal_manual = u'{} (via manual setting)'.format(oa_journal_prefix)