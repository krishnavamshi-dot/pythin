# Job search agent (v0.1)

Pipeline: **Discovery -> dedup -> Screening -> SQLite tracker -> digest**, driven by
`config/profile.yaml` (you, work authorization, preferences) and `config/roles.yaml`
(one config block per role; one shared pipeline).

```
pip install requests pyyaml
python -m jobagent.pipeline run        # fetch, screen, store, print ranked digest
python -m jobagent.pipeline digest     # re-print the digest
python -m jobagent.pipeline mark --key remotive:123 --status applied
python -m pytest tests
```

Sources (official/public feeds only): Remotive, Arbeitnow, plus Greenhouse/Lever boards for
companies listed in `config/companies.yaml`. Outbound hosts must be allowed in the environment.

Rules baked in: full-time ranks above CPT/internship, remote gets a boost, senior titles and
"no sponsorship"/citizenship-only postings are rejected, non-US locations are rejected.

Next: Tailoring (resume per role + truthfulness check), Outreach, Tracker email sync, Interview prep.
Nothing is ever sent to an employer without your approval.
