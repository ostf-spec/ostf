// SPDX-License-Identifier: Apache-2.0

// Package draft_test pins the 0.3 draft to its fixtures and to the simplicity
// budget of plan-agent-readiness.md, section 2.
package draft_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"path"
	"regexp"
	"strings"
	"testing"

	"github.com/google/jsonschema-go/jsonschema"
	"go.yaml.in/yaml/v3"
)

func read(t *testing.T, name string) string {
	t.Helper()
	data, err := os.ReadFile(name)
	if err != nil {
		t.Fatal(err)
	}
	return string(data)
}

// blocks returns the fenced code blocks of lang in the part of ostf.md that
// starts at the first line beginning with start and ends at the next heading
// of the same level.
func blocks(t *testing.T, start, lang string) []string {
	t.Helper()
	spec := read(t, "ostf.md")
	i := strings.Index(spec, "\n"+start)
	if i < 0 {
		t.Fatalf("ostf.md has no %q", start)
	}
	part := spec[i+1:]
	level := start[:strings.Index(start, " ")+1]
	if j := strings.Index(part[1:], "\n"+level); j >= 0 && strings.HasPrefix(level, "#") {
		part = part[:j+1]
	}
	var found []string
	for _, m := range regexp.MustCompile("(?s)```"+lang+"\n(.*?)```").FindAllStringSubmatch(part, -1) {
		found = append(found, m[1])
	}
	if len(found) == 0 {
		t.Fatalf("no %s block after %q", lang, start)
	}
	return found
}

func TestSpecMatchesFixtures(t *testing.T) {
	for _, c := range []struct{ start, lang, file string }{
		{"## 2. Overview", "yaml", "fixtures/minimal/trace.yaml"},
		{"## 2. Overview", "text", "fixtures/minimal/trace.lock"},
		{"**F.1 Agent paragraph", "text", "fixtures/agent-paragraph.txt"},
		{"## Annex J", "text", "example/expected/context.txt"},
	} {
		if got, want := blocks(t, c.start, c.lang)[0], read(t, c.file); got != want {
			t.Errorf("%s block under %q differs from %s:\n%s", c.lang, c.start, c.file, got)
		}
	}
}

func TestSimplicityBudget(t *testing.T) {
	ids := regexp.MustCompile(`\*\*(OSTF-\d{3}) `).FindAllStringSubmatch(read(t, "ostf.md"), -1)
	seen := map[string]bool{}
	for _, m := range ids {
		if seen[m[1]] {
			t.Errorf("%s is defined twice", m[1])
		}
		seen[m[1]] = true
	}
	if len(seen) > 35 {
		t.Errorf("Core has %d requirements; the budget is 35", len(seen))
	}
	// The minimal start: ostf, items, and one item with id, text and its links.
	if lines := strings.Count(read(t, "fixtures/minimal/trace.yaml"), "\n"); lines > 6 {
		t.Errorf("the minimal file has %d lines; it must not grow", lines)
	}
	if p := read(t, "fixtures/agent-paragraph.txt"); !strings.HasPrefix(p, "OSTF agent paragraph 1. ") || !strings.Contains(p, "<tool> check") {
		t.Error("the agent paragraph lost its version line or its check command")
	}
}

func validator(t *testing.T, name string) *jsonschema.Resolved {
	t.Helper()
	load := func(uri *url.URL) (*jsonschema.Schema, error) {
		if uri.Scheme != "https" || uri.Host != "ostf.dev" || path.Dir(uri.Path) != "/draft/0.3" {
			return nil, fmt.Errorf("schema reference is outside the local draft: %s", uri)
		}
		var schema jsonschema.Schema
		if err := json.Unmarshal([]byte(read(t, "schema/"+path.Base(uri.Path))), &schema); err != nil {
			return nil, err
		}
		return &schema, nil
	}
	uri, err := url.Parse("https://ostf.dev/draft/0.3/" + name)
	if err != nil {
		t.Fatal(err)
	}
	schema, err := load(uri)
	if err != nil {
		t.Fatal(err)
	}
	resolved, err := schema.Resolve(&jsonschema.ResolveOptions{Loader: load})
	if err != nil {
		t.Fatal(err)
	}
	return resolved
}

// instance decodes YAML or JSON text into the generic JSON value a validator expects.
func instance(t *testing.T, text string) any {
	t.Helper()
	var v any
	if err := yaml.Unmarshal([]byte(text), &v); err != nil {
		t.Fatal(err)
	}
	data, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	v = nil
	if err := json.Unmarshal(data, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func TestSchemas(t *testing.T) {
	impact := blocks(t, "**C.3 Impact", "json")[0]
	for _, c := range []struct {
		id, schema, text string
		valid            bool
	}{
		{"minimal fixture", "trace.schema.json", read(t, "fixtures/minimal/trace.yaml"), true},
		{"example", "trace.schema.json", read(t, "example/trace.yaml"), true},
		{"tags opt-out", "trace.schema.json", "ostf: \"0.3\"\ntags: false\nitems: []\n", true},
		{"tags not boolean", "trace.schema.json", "ostf: \"0.3\"\ntags: \"yes\"\nitems: []\n", false},
		{"OSTF-121 profile example", "profile.schema.json", blocks(t, "**OSTF-121 Profiles", "yaml")[0], true},
		{"C.2 result example", "result.schema.json", blocks(t, "**C.2 Result format", "json")[0], true},
		{"C.3 impact example", "result.schema.json", `{"ostf": "0.3", "diagnostics": [], "items": [], "links": [], "impact": ` + impact + `}`, true},
		{"expected check", "result.schema.json", read(t, "example/expected/check.json"), true},
		{"expected context", "result.schema.json", read(t, "example/expected/context.json"), true},
		{"result with unknown key", "result.schema.json", `{"ostf": "0.3", "diagnostics": [], "items": [], "links": [], "proposed": []}`, false},
		{"impact with unknown coverage", "result.schema.json", strings.Replace(`{"ostf": "0.3", "diagnostics": [], "items": [], "links": [], "impact": `+impact+`}`, `"direct"`, `"transitive"`, 1), false},
	} {
		t.Run(c.id, func(t *testing.T) {
			if err := validator(t, c.schema).Validate(instance(t, c.text)); (err == nil) != c.valid {
				t.Fatalf("valid %v; want %v: %v", err == nil, c.valid, err)
			}
		})
	}
}

func TestExpectedMatchesLock(t *testing.T) {
	lock := map[string]map[string]string{}
	for _, line := range strings.Split(strings.TrimSuffix(read(t, "example/trace.lock"), "\n"), "\n")[1:] {
		fields := strings.Fields(line)
		pairs := map[string]string{}
		for _, p := range fields[3:] {
			k, v, _ := strings.Cut(p, "=")
			pairs[k] = v
		}
		lock[strings.Join(fields[:3], " ")] = pairs
	}
	for _, name := range []string{"example/expected/check.json", "example/expected/context.json"} {
		var result struct {
			Links []struct {
				Source, Type, Target string
				Fingerprints         map[string]string
			}
		}
		if err := json.NewDecoder(bytes.NewReader([]byte(read(t, name)))).Decode(&result); err != nil {
			t.Fatal(err)
		}
		for _, l := range result.Links {
			id := l.Source + " " + l.Type + " " + l.Target
			if got, ok := lock[id]; !ok || fmt.Sprint(got) != fmt.Sprint(l.Fingerprints) {
				t.Errorf("%s: %s fingerprints %v; lock has %v", name, id, l.Fingerprints, got)
			}
		}
		if name == "example/expected/check.json" && len(result.Links) != len(lock) {
			t.Errorf("check.json has %d links; the lock has %d", len(result.Links), len(lock))
		}
	}
}
