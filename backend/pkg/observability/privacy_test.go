package observability

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"pentagi/pkg/config"
	"sync/atomic"
	"testing"
)

func TestReportingDisabledIgnoresConfiguredEndpoints(t *testing.T) {
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls.Add(1) }))
	defer server.Close()
	cfg := &config.Config{LangfuseBaseURL: server.URL, TelemetryEndpoint: server.Listener.Addr().String()}
	if _, err := NewLangfuseClient(context.Background(), cfg); !errors.Is(err, ErrNotConfigured) {
		t.Fatalf("Langfuse not disabled: %v", err)
	}
	if _, err := NewTelemetryClient(context.Background(), cfg); !errors.Is(err, ErrNotConfigured) {
		t.Fatalf("OTel not disabled: %v", err)
	}
	if calls.Load() != 0 {
		t.Fatal("disabled reporting contacted collector")
	}
}
