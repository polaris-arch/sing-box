package libbox

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/sagernet/sing-box/log"
	"github.com/sagernet/sing-box/service/oomkiller"
	"github.com/sagernet/sing-box/service/powerreport"
	"github.com/sagernet/sing/service"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/emptypb"
)

type transientTestPlatform struct{ PlatformInterface }

func (transientTestPlatform) LocalDNSTransport() LocalDNSTransport        { return nil }
func (transientTestPlatform) UseProcFS() bool                             { return false }
func (transientTestPlatform) UsePlatformAutoDetectInterfaceControl() bool { return false }
func (transientTestPlatform) UnderNetworkExtension() bool                 { return false }
func (transientTestPlatform) GetInterfaces() (NetworkInterfaceIterator, error) {
	return newIterator([]*NetworkInterface{}), nil
}
func (transientTestPlatform) StartDefaultInterfaceMonitor(InterfaceUpdateListener) error { return nil }
func (transientTestPlatform) CloseDefaultInterfaceMonitor(InterfaceUpdateListener) error { return nil }

func transientTestSetup(t *testing.T) {
	t.Helper()
	base, work, temp, power, maxLines, uid, gid := sBasePath, sWorkingPath, sTempPath, sPowerReportEnabled, sLogMaxLines, sUserID, sGroupID
	sBasePath = t.TempDir()
	sWorkingPath = sBasePath
	sTempPath = sBasePath
	sPowerReportEnabled = true
	sLogMaxLines = 32
	sUserID, sGroupID = os.Getuid(), os.Getgid()
	t.Cleanup(func() {
		sBasePath, sWorkingPath, sTempPath, sPowerReportEnabled, sLogMaxLines, sUserID, sGroupID = base, work, temp, power, maxLines, uid, gid
	})
}

func TestTransientCommandServerPreservesSharedState(t *testing.T) {
	transientTestSetup(t)
	paths := []string{"configuration.json", "command.sock", filepath.Join(oomkiller.DraftDirectoryName, "metadata.json"), filepath.Join(powerreport.DraftDirectoryName, "metadata.json")}
	marker := []byte(`{"appVersion":"","appMarketingVersion":""}`)
	for _, path := range paths {
		full := filepath.Join(sBasePath, path)
		if err := os.MkdirAll(filepath.Dir(full), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(full, marker, 0o600); err != nil {
			t.Fatal(err)
		}
	}
	server, err := NewTransientCommandServer(nil, transientTestPlatform{})
	if err != nil {
		t.Fatal(err)
	}
	if server.oomRecorder != nil || service.FromContext[*oomkiller.Recorder](server.ctx) != nil || server.powerManager.Recorder() != nil {
		t.Fatal("transient host created a shared diagnostics recorder")
	}
	if err := server.Start(); err == nil {
		t.Fatal("transient host accepted command listener start")
	}
	if _, err := server.managedService.TriggerOOMReport(context.Background(), &emptypb.Empty{}); status.Code(err) != codes.Unavailable {
		t.Fatalf("transient OOM report must be unavailable: %v", err)
	}
	if err := server.StartOrReloadService("invalid json", &OverrideOptions{}); err == nil {
		t.Fatal("invalid configuration accepted")
	}
	defaultLogger := log.StdLogger()
	if err := server.StartOrReloadService(`{}`, &OverrideOptions{}); err != nil {
		t.Fatal(err)
	}
	if log.StdLogger() != defaultLogger {
		t.Fatal("transient service replaced the process default logger")
	}
	if err := server.StartOrReloadService(`{}`, &OverrideOptions{}); err != nil {
		t.Fatal(err)
	}
	if err := server.CloseService(); err != nil {
		t.Fatal(err)
	}
	server.Close()
	if log.StdLogger() != defaultLogger {
		t.Fatal("transient close changed the process default logger")
	}
	for _, path := range paths {
		content, err := os.ReadFile(filepath.Join(sBasePath, path))
		if err != nil || !bytes.Equal(content, marker) {
			t.Fatalf("shared state changed at %s: %v", path, err)
		}
	}
	for _, path := range []string{oomkiller.ReportsDirectoryName, powerreport.ReportsDirectoryName} {
		if _, err := os.Stat(filepath.Join(sBasePath, path)); !os.IsNotExist(err) {
			t.Fatalf("transient created reports at %s: %v", path, err)
		}
	}
}

func TestCommandServerRetainsSharedDiagnostics(t *testing.T) {
	transientTestSetup(t)
	sPowerReportEnabled = false
	server, err := NewCommandServer(nil, transientTestPlatform{})
	if err != nil {
		t.Fatal(err)
	}
	defer server.Close()
	if server.transient || server.oomRecorder == nil || service.FromContext[*oomkiller.Recorder](server.ctx) == nil {
		t.Fatal("normal host lost OOM diagnostics")
	}
	config := "invalid primary configuration"
	if err := server.StartOrReloadService(config, &OverrideOptions{}); err == nil {
		t.Fatal("invalid configuration accepted")
	}
	content, err := os.ReadFile(configSnapshotPath())
	if err != nil || string(content) != config {
		t.Fatalf("normal host did not save configuration snapshot: %v", err)
	}
	if err := server.Start(); err != nil {
		t.Fatal(err)
	}
	if server.listener == nil {
		t.Fatal("normal host did not start command listener")
	}
}

func TestTransientCommandServerCloseKeepsPrimaryService(t *testing.T) {
	transientTestSetup(t)
	sPowerReportEnabled = false
	defaultLogger := log.StdLogger()
	t.Cleanup(func() { log.SetStdLogger(defaultLogger) })
	primary, err := NewCommandServer(nil, transientTestPlatform{})
	if err != nil {
		t.Fatal(err)
	}
	defer func() { primary.CloseService(); primary.Close() }()
	if err := primary.StartOrReloadService(`{"experimental":{"cache_file":{"path":"primary-cache.db"}}}`, &OverrideOptions{}); err != nil {
		t.Fatal(err)
	}
	primaryInstance := primary.Instance()
	primaryLogger := log.StdLogger()
	if primaryLogger == defaultLogger {
		t.Fatal("normal service did not retain default logger replacement")
	}
	transient, err := NewTransientCommandServer(nil, transientTestPlatform{})
	if err != nil {
		t.Fatal(err)
	}
	if err := transient.StartOrReloadService(`{"experimental":{"cache_file":{"path":"transient-cache.db"}}}`, &OverrideOptions{}); err != nil {
		transient.Close()
		t.Fatal(err)
	}
	if err := transient.CloseService(); err != nil {
		t.Fatal(err)
	}
	transient.Close()
	if primary.Instance() != primaryInstance || primaryInstance.Box() == nil {
		t.Fatal("transient close changed the primary service instance")
	}
	if log.StdLogger() != primaryLogger {
		t.Fatal("transient lifecycle changed the primary default logger")
	}
}
