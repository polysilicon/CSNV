package main

import (
	"os"
	"testing"
)

// TestWriteSmokeESM writes the synthetic FalloutNV.esm to $CSNV_SMOKE_ESM for a manual end-to-end run.
func TestWriteSmokeESM(t *testing.T) {
	out := os.Getenv("CSNV_SMOKE_ESM")
	if out == "" {
		t.Skip("set CSNV_SMOKE_ESM to write the synthetic ESM")
	}
	b, err := os.ReadFile(fakeESM(t))
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(out, b, 0o644); err != nil {
		t.Fatal(err)
	}
}
