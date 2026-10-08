package adapter

import (
	"context"
	"errors"
	"testing"

	"github.com/sagernet/sing-box/log"
)

func TestDeferConstructionCleanupRegistersInScope(t *testing.T) {
	scope := NewScope(context.Background(), log.NewNOPFactory().Logger())
	ctx := ContextWithConstructionScope(context.Background(), scope)
	failure := errors.New("synthetic cleanup failure")
	var order []int
	err := DeferConstructionCleanup(ctx, func() error {
		order = append(order, 1)
		return failure
	})
	if err != nil {
		t.Fatalf("DeferConstructionCleanup = %v, want nil", err)
	}
	scope.Add(func() error {
		order = append(order, 2)
		return nil
	})
	if len(order) != 0 {
		t.Fatal("cleanup ran before the scope was closed")
	}
	err = scope.Close()
	if !errors.Is(err, failure) {
		t.Fatalf("scope.Close() = %v, want cleanup failure", err)
	}
	if len(order) != 2 || order[0] != 2 || order[1] != 1 {
		t.Fatalf("cleanup order = %v, want [2 1]", order)
	}
	err = scope.Close()
	if err != nil || len(order) != 2 {
		t.Fatalf("second scope.Close() = %v, order %v", err, order)
	}
}

func TestDeferConstructionCleanupRunsImmediatelyWithoutScope(t *testing.T) {
	failure := errors.New("synthetic cleanup failure")
	calls := 0
	err := DeferConstructionCleanup(context.Background(), func() error {
		calls++
		return failure
	})
	if !errors.Is(err, failure) || calls != 1 {
		t.Fatalf("DeferConstructionCleanup = %v after %d calls, want cleanup failure after 1", err, calls)
	}
}

func TestDeferConstructionCleanupRunsImmediatelyAfterScopeClosed(t *testing.T) {
	scope := NewScope(context.Background(), log.NewNOPFactory().Logger())
	ctx := ContextWithConstructionScope(context.Background(), scope)
	err := scope.Close()
	if err != nil {
		t.Fatal(err)
	}
	failure := errors.New("synthetic cleanup failure")
	calls := 0
	err = DeferConstructionCleanup(ctx, func() error {
		calls++
		return failure
	})
	if !errors.Is(err, failure) || calls != 1 {
		t.Fatalf("DeferConstructionCleanup = %v after %d calls, want cleanup failure after 1", err, calls)
	}
	err = scope.Close()
	if err != nil || calls != 1 {
		t.Fatalf("closed scope retained the cleanup: %v, %d calls", err, calls)
	}
}
