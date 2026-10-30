# GitHub Actions account-lock report (draft; not sent)

Subject: Public repository standard Actions runners blocked by account billing lock

Hello GitHub Support,

My public repository is https://github.com/ash9201/enam_finn.
I want to use only free standard GitHub-hosted Ubuntu runners, with a $0 paid-spending
budget and Stop usage when budget limit is reached enabled.

After changing the repository from private to public, both manually dispatched
workflows create jobs but fail before runner assignment or any checkout/build steps.
The check annotations say:

> The job was not started because your account is locked due to a billing issue.

Examples:
- CI: https://github.com/ash9201/enam_finn/actions/runs/41086319600
- Source sync: https://github.com/ash9201/enam_finn/actions/runs/41086326494

Both jobs request only `ubuntu-latest`; no larger runners are configured. Their
`runner_name` and `runner_group_name` are empty and no steps execute.
The repository is public and Actions/workflows are enabled. My usage view showed
no usage for October 2026. I temporarily tried a $1 budget, then restored $0.

Please identify the account-level restriction and the steps needed to unlock free
public-repository standard-runner usage. I do not wish to enable paid overages.

Thank you.

---
Review the account/payment history yourself and edit this draft if needed. Submit it
through https://support.github.com/contact; this file has not been sent to anyone.
Do not treat the failed runs as successful CI or source-ingestion checks.
