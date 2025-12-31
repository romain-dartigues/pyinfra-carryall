# Pyinfra — tips and tricks

## incus/LXC connector

Originally suggested through https://github.com/pyinfra-dev/pyinfra/pull/1368.

Examples:

```sh
uv run pyinfra @incus debug-inventory

uv run pyinfra @incus/incus.example.net: fact server.LinuxName
```
