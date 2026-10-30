# Email Delivery — Known Issue

**Status:** Active workaround.

## Context
Automated emails sent via `smtplib` from the `05_obras_report` notebook successfully reach the SMTP server (`250 OK`) but consistently land in the recipient's Spam/Junk folder. This is likely due to the `local_hostname` used in the `EHLO`/`HELO` handshake lacking a trusted sending reputation.

Background: in Fabric, `socket.getfqdn()` returns an invalid hostname, which made the handshake fail with `SMTPHeloError`. It is fixed by passing an explicit `local_hostname=` to `smtplib.SMTP()`. Both `"localhost"` and the sender's domain were tried; the emails are delivered but neither value fully fixes the Spam routing.

## Implemented Workaround
Recipients must manually mark the sender as "Not Junk" or add them to their Safe Senders list. Given the project's personal scale and low recipient count, configuring advanced Exchange mail flow rules or SPF/DKIM alignment is deferred as unnecessary overhead.

## Revisit Triggers
Investigate SPF/DKIM alignment or Exchange Online anti-spoofing rules only if:
- A new recipient is added and experiences the same routing issue.
- Emails start being silently dropped entirely rather than routed to the Spam folder.