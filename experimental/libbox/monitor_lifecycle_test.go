package libbox

import (
	"errors"
	"sync/atomic"
	"testing"

	"github.com/sagernet/sing-box/adapter"
	tun "github.com/sagernet/sing-tun"
	"github.com/sagernet/sing/common/control"
	"github.com/sagernet/sing/common/logger"
)

type monitorTestPlatform struct {
	PlatformInterface
	closeError     error
	startError     error
	onStart        func(InterfaceUpdateListener)
	starts, closes atomic.Int32
}

func (p *monitorTestPlatform) StartDefaultInterfaceMonitor(l InterfaceUpdateListener) error {
	p.starts.Add(1)
	if p.onStart != nil {
		p.onStart(l)
	}
	return p.startError
}
func (p *monitorTestPlatform) CloseDefaultInterfaceMonitor(InterfaceUpdateListener) error {
	p.closes.Add(1)
	return p.closeError
}
func (*monitorTestPlatform) GetInterfaces() (NetworkInterfaceIterator, error) {
	return newIterator([]*NetworkInterface{{Name: "successor", Index: 12}}), nil
}

type monitorTestManager struct {
	adapter.NetworkManager
	monitor         tun.DefaultInterfaceMonitor
	calls           atomic.Int32
	entered, resume chan struct{}
	finder          control.InterfaceFinder
}

func (m *monitorTestManager) InterfaceMonitor() tun.DefaultInterfaceMonitor { return m.monitor }
func (m *monitorTestManager) InterfaceFinder() control.InterfaceFinder      { return m.finder }
func (m *monitorTestManager) UpdateInterfaces() error {
	m.calls.Add(1)
	if m.entered != nil {
		close(m.entered)
		<-m.resume
	}
	return nil
}

type monitorTestFinder struct {
	control.InterfaceFinder
	value *control.Interface
}

func (f monitorTestFinder) ByIndex(int) (*control.Interface, error) { return f.value, nil }
func createBoundMonitor(t *testing.T, w *platformInterfaceWrapper, manager *monitorTestManager, start bool) *platformDefaultInterfaceMonitor {
	t.Helper()
	// Actual route.New -> box.New order: Create before Initialize.
	m := w.CreateDefaultInterfaceMonitor(logger.NOP()).(*platformDefaultInterfaceMonitor)
	manager.monitor = m
	if err := w.Initialize(manager); err != nil {
		t.Fatal(err)
	}
	if start {
		if err := m.Start(); err != nil {
			t.Fatal(err)
		}
	}
	return m
}
func successorMonitor(t *testing.T, w *platformInterfaceWrapper) (*platformDefaultInterfaceMonitor, *monitorTestManager, *control.Interface) {
	expected := &control.Interface{Name: "successor", Index: 12}
	manager := &monitorTestManager{finder: monitorTestFinder{value: expected}}
	m := createBoundMonitor(t, w, manager, true)
	m.UpdateDefaultInterface("successor", 12, true, true)
	manager.calls.Store(0)
	return m, manager, expected
}
func assertSuccessor(t *testing.T, w *platformInterfaceWrapper, m *platformDefaultInterfaceMonitor, b *monitorTestManager, expected *control.Interface) {
	t.Helper()
	if b.calls.Load() != 0 || m.DefaultInterface() != expected {
		t.Fatalf("old A changed B: calls=%d default=%v", b.calls.Load(), m.DefaultInterface())
	}
	projected, err := w.NetworkInterfaces()
	if err != nil {
		t.Fatal(err)
	}
	if len(projected) != 1 || !projected[0].Expensive || !projected[0].Constrained {
		t.Fatalf("successor projection changed: %+v", projected)
	}
}
func TestMonitorClosedAIsolatedFromReloadB(t *testing.T) {
	w := &platformInterfaceWrapper{iif: &monitorTestPlatform{}}
	a := &monitorTestManager{}
	old := createBoundMonitor(t, w, a, true)
	if err := old.Close(); err != nil {
		t.Fatal(err)
	}
	current, b, expected := successorMonitor(t, w)
	callbacks := 0
	current.RegisterCallback(func(*control.Interface, int) { callbacks++ })
	old.UpdateDefaultInterface("", -1, false, false)
	old.UpdateNetworkPath("old path")
	assertSuccessor(t, w, current, b, expected)
	if a.calls.Load() != 0 || callbacks != 0 {
		t.Fatal("sealed A delivered")
	}
}
func TestMonitorAlreadyDeliveringAIsolatedFromReloadB(t *testing.T) {
	for _, fixStack := range []bool{false, true} {
		t.Run(map[bool]string{false: "direct", true: "android-worker"}[fixStack], func(t *testing.T) {
			previous := sFixAndroidStack
			sFixAndroidStack = fixStack
			defer func() { sFixAndroidStack = previous }()
			w := &platformInterfaceWrapper{iif: &monitorTestPlatform{}}
			a := &monitorTestManager{entered: make(chan struct{}), resume: make(chan struct{})}
			old := createBoundMonitor(t, w, a, true)
			done := make(chan struct{})
			go func() { old.UpdateDefaultInterface("", -1, false, false); close(done) }()
			<-a.entered
			if err := old.Close(); err != nil {
				t.Fatal(err)
			}
			old.defaultInterfaceAccess.Lock()
			retained := old.inFlight
			old.defaultInterfaceAccess.Unlock()
			if retained != 1 {
				t.Fatalf("in-flight erased at close: %d", retained)
			}
			current, b, expected := successorMonitor(t, w)
			close(a.resume)
			<-done
			assertSuccessor(t, w, current, b, expected)
			if a.calls.Load() != 1 || old.inFlight != 0 {
				t.Fatal("actual-return accounting changed")
			}
		})
	}
}
func TestMonitorPartialConstructionCloseCannotDetachLive(t *testing.T) {
	w := &platformInterfaceWrapper{iif: &monitorTestPlatform{}}
	live, b, expected := successorMonitor(t, w)
	partial := createBoundMonitor(t, w, &monitorTestManager{}, false)
	if err := partial.Close(); err != nil {
		t.Fatal(err)
	}
	assertSuccessor(t, w, live, b, expected)
	if partial.Start() == nil {
		t.Fatal("late Start revived sealed monitor")
	}
	if w.Initialize(&monitorTestManager{monitor: live}) == nil {
		t.Fatal("second bind accepted")
	}
	if (&platformInterfaceWrapper{}).Initialize(&monitorTestManager{monitor: live}) == nil {
		t.Fatal("foreign wrapper bound")
	}
}
func TestMonitorCallbackSelfCloseAndFirstErrors(t *testing.T) {
	closeErr := errors.New("native close")
	platform := &monitorTestPlatform{closeError: closeErr}
	w := &platformInterfaceWrapper{iif: platform}
	m := createBoundMonitor(t, w, &monitorTestManager{}, true)
	var selfError error
	m.RegisterCallback(func(*control.Interface, int) { selfError = m.Close() })
	m.UpdateDefaultInterface("", -1, false, false)
	if selfError != closeErr || m.Close() != closeErr || platform.closes.Load() != 1 || m.inFlight != 0 {
		t.Fatal("close error/self-close changed")
	}
	startErr := errors.New("native start")
	platform = &monitorTestPlatform{startError: startErr, closeError: closeErr}
	w = &platformInterfaceWrapper{iif: platform}
	m = createBoundMonitor(t, w, &monitorTestManager{}, false)
	if m.Start() != startErr || w.activeMonitor != nil || !m.sealed || m.closeError != closeErr {
		t.Fatal("partial Start lost original error or remained live")
	}
}
func TestMonitorNativeIdentityAndSynchronousInitialUpdate(t *testing.T) {
	p := &monitorTestPlatform{onStart: func(l InterfaceUpdateListener) { l.UpdateDefaultInterface("", -1, false, false) }}
	w := &platformInterfaceWrapper{iif: p}
	a := &monitorTestManager{}
	first := createBoundMonitor(t, w, a, true)
	second := createBoundMonitor(t, w, &monitorTestManager{}, false)
	if a.calls.Load() != 1 {
		t.Fatal("synchronous initial callback was rejected")
	}
	if InterfaceUpdateListenerIdentity(first) == "" || InterfaceUpdateListenerIdentity(first) == InterfaceUpdateListenerIdentity(second) {
		t.Fatal("native identities reused")
	}
	var nilMonitor *platformDefaultInterfaceMonitor
	if InterfaceUpdateListenerIdentity(nil) != "" || InterfaceUpdateListenerIdentity(nilMonitor) != "" {
		t.Fatal("invalid identity accepted")
	}
}

type monitorForeignListener struct{}

func (monitorForeignListener) UpdateDefaultInterface(string, int32, bool, bool) {}
func (monitorForeignListener) UpdateNetworkPath(string)                         {}
func TestMonitorRejectForeignAndUnbound(t *testing.T) {
	if InterfaceUpdateListenerIdentity(monitorForeignListener{}) != "" {
		t.Fatal("foreign listener gained native identity")
	}
	w := &platformInterfaceWrapper{iif: &monitorTestPlatform{}}
	m := w.CreateDefaultInterfaceMonitor(logger.NOP()).(*platformDefaultInterfaceMonitor)
	if m.Start() == nil {
		t.Fatal("unbound monitor started")
	}
	if w.Initialize(&monitorTestManager{monitor: (*platformDefaultInterfaceMonitor)(nil)}) == nil {
		t.Fatal("typed nil monitor bound")
	}
}
