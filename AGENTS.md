# Installation and maintenance contract

Read `README.md`, `docs/AI_INSTALL.md`, `docs/INSTALL.md`, `docs/SETUP.md`,
`docs/ACCEPTANCE.md`, and `SECURITY.md` before installing this project.
These instructions apply both to a Git checkout and to a release source archive.

## What the user's request authorizes

"Install this for me" authorizes preparation and reversible installation on the
user's identified, authorized equipment. Discover the existing state first.
Do not buy servers, accept paid renewals, format a disk, reboot a shared device,
replace an occupied service, or disconnect the user's only management path
without authorization covering that concrete action. Reuse prior authorization;
do not repeatedly ask about ordinary steps already approved.

## Required sequence

1. Inventory the control computer, router, two VPS roles, existing VPN/DNS,
   available access, and the user's desired scope. Record versions and architecture.
2. Protect private backups and establish a working recovery path.
3. Generate fresh credentials locally with `tools/render.py init`. Deploy the
   exit, then the entry. Never reuse example credentials or an author's profile.
4. Verify the entire chain with one client while the previous home VPN stays up.
5. Prepare Entware/XKeen and the generated router config with autostart off.
   Check current upstream instructions and the actual installed version.
6. Prepare and validate a rollback applicable to THIS user's original state.
   The bundled rollback is only for an existing OpenVPN + DNS53 migration.
7. Start a rollback timer, switch only the intended clients/network, and verify
   direct routing, selected routing, DNS, real applications, and load stability.
8. Persist the accepted state and verify startup in a separately authorized
   reboot window. Record which checks actually ran and any outstanding checks.

## Boundaries

- Never publish generated files, working profiles, credentials, QR codes,
  private backups, or raw logs. `.gitignore` is not an access-control mechanism.
- Keep secrets out of chat, command output, screenshots, public issues and git.
  Use authenticated SSH/SFTP, local protected files and known-host verification.
- Do not delete existing profiles, flush firewall tables or overwrite unrelated
  crontabs/services. Preserve the ISP default route for selective mode.
- Do not guess the router's disk, Entware SSH port, OpenVPN interface, DNS profile,
  RCI syntax, IPv6 behavior, service owner, core architecture or public endpoint.
- Keep the original VPN working until the new chain and rollback have been checked.
  Avoid two transparent interception systems running simultaneously.
- For unknown versions or a materially different topology, investigate and adapt
  before executing. Do not silently treat an example as a discovered fact.
- A core config test, open port, systemd status, HTTP 403, successful ping or a
  throughput peak does not establish end-user success. Use `docs/ACCEPTANCE.md`.
- If a check fails, keep the last working stage, collect a bounded comparison,
  and state the exact blocker. Do not buy another server as the default remedy.
- If the assistant cannot operate a terminal/browser/SSH, state that constraint
  and guide one command block at a time. Never invent actions or their results.

For repository changes: keep examples synthetic, document the reason in
`CHANGELOG.md`, run applicable tests, and run the publication scan after staging.
Do not move an already published release tag to a new commit.
