//go:build !windows

package main

import "os/exec"

func hideWindow(cmd *exec.Cmd) {}

func showError(msg string) {}

func openURL(u string) error {
	return exec.Command("xdg-open", u).Start()
}
