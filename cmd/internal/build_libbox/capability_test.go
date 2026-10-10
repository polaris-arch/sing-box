package main

import (
	"os"
	"strings"
	"testing"
)

func TestPolarisGVisorBuildEntrypoints(t *testing.T) {
	if !strings.Contains(","+strings.Join(sharedTags, ",")+",", ",with_gvisor,") {
		t.Fatal("Android/Apple helper omits gVisor")
	}
	for _, name := range []string{"DEFAULT_BUILD_TAGS", "DEFAULT_BUILD_TAGS_WINDOWS"} {
		data, err := os.ReadFile("../../../release/" + name)
		if err != nil {
			t.Fatal(err)
		}
		tags := "," + strings.TrimSpace(string(data)) + ","
		for _, required := range []string{"with_gvisor", "with_naive_outbound"} {
			if !strings.Contains(tags, ","+required+",") {
				t.Errorf("%s omits %s", name, required)
			}
		}
		if name == "DEFAULT_BUILD_TAGS_WINDOWS" && !strings.Contains(tags, ",with_purego,") {
			t.Fatal("Windows Cronet requires purego independently of gVisor")
		}
	}
}
