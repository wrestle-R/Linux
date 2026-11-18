# Hyprland watchdog shutdown fix

Arch's Hyprland 0.57.2-1 watchdog can abort when SIGTERM or SIGINT lands on the thread waiting for Hyprland. The signal handler tries to join the same thread. This local package backports a fix to the launcher only. The handler writes to a nonblocking pipe, and the main thread handles the shutdown and joins the worker. The normal safe-mode restart and locked-session flag still work. [Upstream report](https://github.com/hyprwm/Hyprland/discussions/15531)

## Build and install

Run with Arch's base-devel tools installed. Build as your desktop user.

```sh
cd End-4/watchdog
makepkg
sudo pacman -U ./rdp-hyprland-watchdog-0.57.2-1-x86_64.pkg.tar.zst
```

The build checks upstream child-exit behavior, signal delivery to the process and worker thread, and crash recovery into locked safe mode. Use the usual **Hyprland** session in SDDM. The local desktop entry takes priority at the next login. The package leaves the Arch launcher in place and delegates to it automatically when the installed Hyprland package version changes.

Remove the local entry and launcher with `sudo pacman -R rdp-hyprland-watchdog`. SDDM picks up the stock entry at the next login.
