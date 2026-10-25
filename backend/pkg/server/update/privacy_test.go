package update

import (
	"pentagi/pkg/config"
	"pentagi/pkg/database"
	"testing"
	"time"
)

func TestReportingOptInRequiredBeforeClientConstruction(t *testing.T) {
	// Deliberately malformed endpoint and missing installation id: disabled mode
	// must exit before constructing the network client or inspecting the database.
	cfg := &config.Config{UpdateCheckInterval: time.Hour, UpdateServerHost: "invalid endpoint"}
	service, err := New(cfg, &database.Queries{})
	if service != nil || err == nil || err.Error() != "update reporting is disabled" {
		t.Fatalf("unexpected result: %v %v", service, err)
	}
}
