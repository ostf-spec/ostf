// SPDX-License-Identifier: Apache-2.0

// Package draft_test pins the 0.3 draft to its fixtures and to the simplicity
// budget of plan-agent-readiness.md, section 2.
package draft_test

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"net/url"
	"os"
	"path"
	"regexp"
	"slices"
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
		{"**F.1 Agent paragraph", "text", "fixtures/agent-paragraph.txt"},
		{"**F.2 Policy paragraph", "text", "fixtures/agent-policy.txt"},
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
	if p := read(t, "fixtures/agent-paragraph.txt"); !strings.HasPrefix(p, "OSTF agent paragraph 5. ") || !strings.Contains(p, "<tool> check") {
		t.Error("the agent paragraph lost its version line or its check command")
	}
	// Plan section 7: the normative paragraph stays under 120 words; policy goes in the paragraph after it.
	if words := len(strings.Fields(read(t, "fixtures/agent-paragraph.txt"))); words >= 120 {
		t.Errorf("the agent paragraph has %d words; it must stay under 120", words)
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
	// The YAML library refuses the 1.2 directive, though OSTF files are YAML 1.2 (OSTF-101).
	lines := strings.Split(text, "\n")
	for i, line := range lines {
		if line == "%YAML 1.2" {
			lines[i] = "%YAML 1.1"
		}
		if trimmed := strings.TrimSpace(line); trimmed != "" && !strings.HasPrefix(trimmed, "#") {
			break
		}
	}
	text = strings.Join(lines, "\n")
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
		{"trial fixture go-shop", "trace.schema.json", read(t, "trials/fixtures/go-shop/trace.yaml"), true},
		{"trial fixture go-shop requirements", "trace.schema.json", read(t, "trials/fixtures/go-shop/trace/requirements.yaml"), true},
		{"trial fixture go-shop design", "trace.schema.json", read(t, "trials/fixtures/go-shop/trace/design.yaml"), true},
		{"trial fixture go-shop threats", "trace.schema.json", read(t, "trials/fixtures/go-shop/trace/threats.yaml"), true},
		{"trial fixture ts-shop", "trace.schema.json", read(t, "trials/fixtures/ts-shop/trace.yaml"), true},
		{"trial fixture ts-shop requirements", "trace.schema.json", read(t, "trials/fixtures/ts-shop/trace/requirements.yaml"), true},
		{"trial fixture ts-shop design", "trace.schema.json", read(t, "trials/fixtures/ts-shop/trace/design.yaml"), true},
		{"trial fixture ts-shop threats", "trace.schema.json", read(t, "trials/fixtures/ts-shop/trace/threats.yaml"), true},
		{"tags opt-out", "trace.schema.json", "ostf: \"0.3\"\ntags: false\nitems: []\n", true},
		{"tags not boolean", "trace.schema.json", "ostf: \"0.3\"\ntags: \"yes\"\nitems: []\n", false},
		{"OSTF-121 profile example", "profile.schema.json", blocks(t, "**OSTF-121 Profiles", "yaml")[0], true},
		{"security profile", "profile.schema.json", read(t, "profiles/security.yaml"), true},
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

// cases holds the parts of conformance/cases.json that the Go checks read.
type cases struct {
	Checks []struct {
		ID     string            `json:"id"`
		Files  map[string]string `json:"files"`
		Expect struct {
			Codes []string `json:"codes"`
		} `json:"expect"`
	} `json:"checks"`
	Schemas []struct {
		ID     string `json:"id"`
		Schema string `json:"schema"`
		Input  any    `json:"input"`
		Valid  bool   `json:"valid"`
	} `json:"schemas"`
	Impacts []struct {
		ID     string `json:"id"`
		Expect struct {
			Impact any `json:"impact"`
		} `json:"expect"`
	} `json:"impacts"`
}

func readCases(t *testing.T) cases {
	t.Helper()
	var c cases
	if err := json.Unmarshal([]byte(read(t, "conformance/cases.json")), &c); err != nil {
		t.Fatal(err)
	}
	return c
}

func TestSchemaCases(t *testing.T) {
	for _, c := range readCases(t).Schemas {
		t.Run(c.ID, func(t *testing.T) {
			if err := validator(t, c.Schema).Validate(c.Input); (err == nil) != c.Valid {
				t.Fatalf("valid %v; want %v: %v", err == nil, c.Valid, err)
			}
		})
	}
}

// TestImpactCasesFitResultSchema checks every expected impact of the
// conformance cases against result.schema.json, so the hand-written
// expectations and the schema cannot drift apart.
func TestImpactCasesFitResultSchema(t *testing.T) {
	checked := 0
	for _, c := range readCases(t).Impacts {
		if c.Expect.Impact == nil {
			continue
		}
		result := map[string]any{"ostf": "0.3", "diagnostics": []any{}, "items": []any{}, "links": []any{}, "impact": c.Expect.Impact}
		if err := validator(t, "result.schema.json").Validate(result); err != nil {
			t.Errorf("%s: %v", c.ID, err)
		}
		checked++
	}
	if checked < 10 {
		t.Errorf("only %d impact cases checked", checked)
	}
}

// TestSchemasAcceptCaseFiles checks the schemas against the reader: in a check
// case that expects none of the codes below, the root, its profile and every
// item file the root includes must pass their schemas, so a schema never
// rejects what the specification accepts.
func TestSchemasAcceptCaseFiles(t *testing.T) {
	structural := map[string]bool{}
	for _, code := range strings.Fields("FORMAT_INVALID VERSION_UNSUPPORTED UNKNOWN_KEY PATH_INVALID FILE_TOO_LARGE PROFILE_INVALID " +
		"INVALID_ID INVALID_ALIAS INVALID_STATUS INVALID_ATTRIBUTE INVALID_EXTERNAL MISSING_TEXT ANCHOR_INVALID UNKNOWN_LINK_TYPE UNKNOWN_TYPE") {
		structural[code] = true
	}
	checked := 0
	for _, c := range readCases(t).Checks {
		if slices.ContainsFunc(c.Expect.Codes, func(code string) bool { return structural[code] }) {
			continue
		}
		root, _ := instance(t, c.Files["trace.yaml"]).(map[string]any)
		selected := map[string]string{"trace.yaml": "trace.schema.json"}
		if profile, ok := root["profile"].(string); ok {
			selected[profile] = "profile.schema.json"
		}
		include, _ := root["include"].([]any)
		for name := range c.Files {
			for _, glob := range include {
				if g, ok := glob.(string); ok && name != "trace.yaml" && covered(c.Files, name) && matchGlob(g, name) {
					selected[name] = "trace.schema.json"
				}
			}
		}
		for name, schema := range selected {
			if text, ok := c.Files[name]; ok {
				if err := validator(t, schema).Validate(instance(t, text)); err != nil {
					t.Errorf("%s: %s fails %s: %v", c.ID, name, schema, err)
				}
				checked++
			}
		}
	}
	if checked < 100 {
		t.Errorf("only %d case files checked", checked)
	}
}

// covered reports whether the root covers name: its path is valid (OSTF-105) and no directory between them
// holds a trace.yaml (OSTF-102).
func covered(files map[string]string, name string) bool {
	parts := strings.Split(name, "/")
	if strings.ContainsAny(name, "\\#\r\n") || strings.HasPrefix(name, "/") || slices.ContainsFunc(parts, func(p string) bool { return p == "" || p == "." || p == ".." }) {
		return false
	}
	for n := 1; n < len(parts); n++ {
		if _, ok := files[strings.Join(parts[:n], "/")+"/trace.yaml"]; ok {
			return false
		}
	}
	return true
}

// matchGlob matches an include glob (OSTF-102): * and ? within one component, ** for zero or more components.
func matchGlob(glob, name string) bool {
	var match func(g, n []string) bool
	match = func(g, n []string) bool {
		switch {
		case len(g) == 0:
			return len(n) == 0
		case g[0] == "**":
			for i := 0; i <= len(n); i++ {
				if match(g[1:], n[i:]) {
					return true
				}
			}
			return false
		case len(n) == 0:
			return false
		}
		return matchComponent([]rune(g[0]), []rune(n[0])) && match(g[1:], n[1:])
	}
	return match(strings.Split(glob, "/"), strings.Split(name, "/"))
}

// matchComponent matches one component with * and ? only; every other
// character, brackets and backslashes included, is literal (OSTF-102).
func matchComponent(g, n []rune) bool {
	gi, ni, star, mark := 0, 0, -1, 0
	for ni < len(n) {
		switch {
		case gi < len(g) && (g[gi] == '?' || g[gi] == n[ni]):
			gi, ni = gi+1, ni+1
		case gi < len(g) && g[gi] == '*':
			star, mark = gi, ni
			gi++
		case star >= 0:
			gi, mark = star+1, mark+1
			ni = mark
		default:
			return false
		}
	}
	for gi < len(g) && g[gi] == '*' {
		gi++
	}
	return gi == len(g)
}

// lockTokens are the tokens of the lock that revision 0.16 removed (plan,
// section 8): its header, its reasons and codes, a state written as a
// result value, and an algorithm prefix. They match tokens, never the words
// valid or suspect, which the text uses in other senses.
var lockTokens = regexp.MustCompile(`trace\.lock 1|\b(?:LINK_BROKEN|LINK_UNSTAMPED|UNKNOWN_ALGORITHM|ITEM_CHANGED|FILE_CHANGED|` +
	`DEFINITION_CHANGED|SIGNATURE_CHANGED|BODY_CHANGED|LOCK_MISSING|LOCK_INVALID|LOCK_DUPLICATE|STAMP_REFUSED)\b|` +
	`"state"\s*:|ostf\.state|\((?:valid|suspect|unstamped|broken)[,)]|\b(?:f1|go1|go2|ts1|ts2|py1|lf1):[A-Za-z0-9_-]`)

// TestNoLockTokens is the exit gate of the plan's section 8: no token of the
// lock is left where the format is defined or used, in ostf.md, the schemas,
// the conformance cases, the fixtures and the example, the reader's command,
// the Action and the READMEs. What keeps the lock as history is left out:
// Annex H, the retired markers, the conversion notes of the conformance
// README, the three vector files of 0.2, trials/, reviews/, the decision
// record and the plan.
func TestNoLockTokens(t *testing.T) {
	texts := map[string]string{}
	spec := read(t, "ostf.md")
	annexH, annexI := strings.Index(spec, "\n## Annex H "), strings.Index(spec, "\n## Annex I ")
	if annexH < 0 || annexI < annexH {
		t.Fatal("ostf.md has no Annex H before Annex I")
	}
	var kept []string
	for _, line := range strings.Split(spec[:annexH]+spec[annexI:], "\n") {
		if !strings.HasPrefix(line, `<a id="OSTF-`) { // a retired requirement's marker
			kept = append(kept, line)
		}
	}
	texts["ostf.md"] = strings.Join(kept, "\n")
	readme := read(t, "conformance/README.md")
	if i := strings.Index(readme, "\n## From "); i >= 0 { // the conversion notes, to the end
		readme = readme[:i]
	}
	texts["conformance/README.md"] = readme
	for _, name := range []string{"../../README.md", "../../action.yml", "conformance/cases.json", "conformance/reader.py",
		"example/README.md", "fixtures/README.md", "tools/README.md"} {
		texts[name] = read(t, name)
	}
	for _, dir := range []string{"schema", "fixtures", "example"} {
		if err := fs.WalkDir(os.DirFS(dir), ".", func(name string, entry fs.DirEntry, err error) error {
			if err == nil && !entry.IsDir() {
				texts[dir+"/"+name] = read(t, dir+"/"+name)
			}
			return err
		}); err != nil {
			t.Fatal(err)
		}
	}
	for name, text := range texts {
		for n, line := range strings.Split(text, "\n") {
			if found := lockTokens.FindString(line); found != "" {
				t.Errorf("%s:%d holds %q, a token of the lock", name, n+1, found)
			}
		}
	}
	if len(texts) < 20 {
		t.Errorf("only %d files read", len(texts))
	}
}
